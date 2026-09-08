import "server-only";

import { createHash, randomUUID } from "node:crypto";
import { desc, eq, lt } from "drizzle-orm";

import { getDb } from "@/lib/db";
import { auditLog, datasets, jobs, uploads } from "@/lib/schema";
import type {
  AnalysisConfig,
  JobCallbackRequest,
  JobRecord,
  UploadCompleteRequest,
  UploadInitiateRequest,
  ValidationIssue,
} from "@/types/orama";

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asValidationIssues(value: unknown, fallbackCode: string): ValidationIssue[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.flatMap((item) => {
    const issue = asRecord(item);
    if (!issue || typeof issue.message !== "string") {
      return [];
    }
    return [{
      code: typeof issue.code === "string" ? issue.code : fallbackCode,
      field: typeof issue.field === "string" ? issue.field : undefined,
      message: issue.message,
      suggestion: typeof issue.suggestion === "string" ? issue.suggestion : undefined,
    }];
  });
}

function asJobStatus(value: unknown): JobRecord["status"] | null {
  return value === "QUEUED" || value === "RUNNING" || value === "SUCCEEDED" || value === "FAILED" || value === "NOT_EVALUABLE"
    ? value
    : null;
}

function isTerminalStatus(status: JobRecord["status"]) {
  return status === "SUCCEEDED" || status === "FAILED" || status === "NOT_EVALUABLE";
}

function retentionDeadline() {
  const configuredDays = Number(process.env.ORAMA_RETENTION_DAYS ?? 30);
  const retentionDays = Number.isFinite(configuredDays)
    ? Math.min(Math.max(Math.trunc(configuredDays), 1), 3650)
    : 30;
  return new Date(Date.now() + retentionDays * 24 * 60 * 60 * 1000);
}

function freezeAnalysisConfig(config: AnalysisConfig): AnalysisConfig {
  return {
    horizons: [...new Set(config.horizons)].sort((left, right) => left - right),
    min_history_days: config.min_history_days,
    min_observations_per_variable: config.min_observations_per_variable,
    prediction_gap_days: config.prediction_gap_days,
  };
}

function configurationHash(config: AnalysisConfig) {
  const frozenConfig = freezeAnalysisConfig(config);
  return createHash("sha256")
    .update(JSON.stringify({
      analysis_locked: true,
      horizons: frozenConfig.horizons,
      min_history_days: frozenConfig.min_history_days,
      min_observations_per_variable: frozenConfig.min_observations_per_variable,
      prediction_gap_days: frozenConfig.prediction_gap_days,
      random_state: 42,
      test_size: 0.25,
    }))
    .digest("hex");
}

function normalizeWorkerResult(jobId: string, value: unknown): JobRecord["result"] {
  const workerResult = asRecord(value);
  const reportPayload = asRecord(workerResult?.report_json);
  const horizonResults = asRecord(reportPayload?.metrics_per_model_horizon);

  if (!workerResult || !reportPayload || !horizonResults) {
    return undefined;
  }

  const cohortFlow = asRecord(reportPayload.cohort_flow);
  const cohortSizes = asRecord(cohortFlow?.eligible_cohort_size_by_horizon);
  const exclusionsByHorizon = asRecord(cohortFlow?.exclusions_by_horizon);
  const cohortExclusions = Object.entries(exclusionsByHorizon ?? {}).flatMap(([horizon, rawExclusions]) => {
    const exclusions = asRecord(rawExclusions) ?? {};
    const cohortSize = asNumber(cohortSizes?.[horizon]) ?? 0;

    return Object.entries(exclusions)
      .map(([reason, count]) => {
        const numericCount = asNumber(count);
        if (numericCount === null) {
          return null;
        }

        return {
          reason: `${horizon} days: ${reason.replaceAll("_", " ")}`,
          count: numericCount,
          percent: cohortSize > 0 ? (numericCount / cohortSize) * 100 : 0,
        };
      })
      .filter((row): row is NonNullable<typeof row> => row !== null);
  });

  const comparison = Object.entries(horizonResults).flatMap(([horizon, rawHorizonResult]) => {
    const horizonResult = asRecord(rawHorizonResult);
    const modelResults = asRecord(horizonResult?.model_results);
    const staticMetrics = asRecord(asRecord(modelResults?.M1)?.metrics);
    const staticAuprc = asNumber(staticMetrics?.auprc);
    if (staticAuprc === null) {
      return [];
    }

    return [
      { modelName: "M2", label: "Static + trajectory" },
      { modelName: "M5", label: "Trajectory-only" },
    ].flatMap(({ modelName, label }) => {
      const trajectoryAuprc = asNumber(asRecord(asRecord(modelResults?.[modelName])?.metrics)?.auprc);
      if (trajectoryAuprc === null) {
        return [];
      }

      return [{
        measure: `${label} AUPRC @ ${horizon} days`,
        staticModel: staticAuprc,
        trajectoryModel: trajectoryAuprc,
        delta: trajectoryAuprc - staticAuprc,
      }];
    });
  });

  const feasibility = String(workerResult.feasibility_conclusion ?? "NOT_EVALUABLE");
  const decisionReasons = asStringArray(reportPayload.decision_reasons);
  const artifactReferences = asStringArray(workerResult.report_references);
  const limitations = Array.isArray(reportPayload.limitations)
    ? reportPayload.limitations.filter((item): item is string => typeof item === "string")
    : [];
  const disclaimer = typeof reportPayload.disclaimer === "string"
    ? reportPayload.disclaimer
    : "Research use only. Synthetic data only. Non-diagnostic.";

  return {
    cohortExclusions,
    comparison,
    warnings: limitations,
    feasibilityDecision: feasibility,
    decisionReasons,
    artifactReferences,
    report: {
      executiveSummary: `Worker job ${jobId} completed with the research feasibility conclusion ${feasibility}.`,
      metrics: comparison.map((row) => ({
        name: row.measure,
        value: `Static ${row.staticModel.toFixed(3)}; trajectory ${row.trajectoryModel.toFixed(3)}`,
        note: `Incremental AUPRC: ${row.delta >= 0 ? "+" : ""}${row.delta.toFixed(3)}`,
      })),
      limitations,
      disclaimer,
      generatedAt: new Date().toISOString(),
    },
  };
}

async function updateJobStatus(
  jobId: string,
  status: JobRecord["status"],
  options: { errorMessage?: string | null; result?: JobRecord["result"] } = {},
) {
  const db = getDb();
  const [existing] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);
  if (!existing) {
    return null;
  }

  const existingStatus = asJobStatus(existing.status) ?? "FAILED";
  if (isTerminalStatus(existingStatus) && existingStatus !== status) {
    return toJobRecord(existing);
  }

  const [updated] = await db
    .update(jobs)
    .set({
      status,
      updatedAt: new Date(),
      ...(options.errorMessage !== undefined ? { errorMessage: options.errorMessage } : {}),
      ...(options.result !== undefined ? { result: options.result } : {}),
    })
    .where(eq(jobs.jobId, jobId))
    .returning();

  return updated ? toJobRecord(updated) : null;
}

async function recordAuditEvent(eventType: string, entityId: string, payload: Record<string, unknown>) {
  const db = getDb();
  await db.insert(auditLog).values({
    id: createId("audit"),
    eventType,
    entityId,
    actorId: process.env.ORAMA_RESEARCH_ACTOR_ID ?? "researcher-session",
    payload,
  });
}

function workerConfiguration() {
  const workerUrl = process.env.ORAMA_WORKER_URL;
  const workerSecret = process.env.ORAMA_WORKER_SHARED_SECRET;
  const workerHfToken = process.env.ORAMA_WORKER_HF_TOKEN;
  const appUrl = process.env.ORAMA_APP_URL ?? process.env.NEXT_PUBLIC_APP_URL;

  if (!workerUrl || !workerSecret || !appUrl) {
    throw new Error("ORAMA_WORKER_URL, ORAMA_WORKER_SHARED_SECRET, and ORAMA_APP_URL must be configured.");
  }

  const normalizedWorkerUrl = workerUrl.replace(/\/$/, "");
  const workerHostname = new URL(normalizedWorkerUrl).hostname;
  const requiresHfAuthorization = workerHostname.endsWith(".hf.space");
  if (requiresHfAuthorization && !workerHfToken) {
    throw new Error("ORAMA_WORKER_HF_TOKEN must be configured for a private Hugging Face Space worker.");
  }

  return {
    workerUrl: normalizedWorkerUrl,
    workerSecret,
    workerAuthorization: requiresHfAuthorization ? `Bearer ${workerHfToken}` : undefined,
    appUrl: appUrl.replace(/\/$/, ""),
  };
}

function workerHeaders(configuration: ReturnType<typeof workerConfiguration>) {
  return {
    "X-Orama-Worker-Secret": configuration.workerSecret,
    ...(configuration.workerAuthorization ? { Authorization: configuration.workerAuthorization } : {}),
  };
}

async function requestUploadUrl(uploadId: string, filename: string, contentType: string) {
  const worker = workerConfiguration();
  const response = await fetch(`${worker.workerUrl}/internal/storage/presign-upload`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...workerHeaders(worker),
    },
    body: JSON.stringify({ upload_id: uploadId, filename, content_type: contentType }),
    signal: AbortSignal.timeout(10000),
  });
  const payload = (await response.json().catch(() => null)) as { upload_url?: unknown; object_key?: unknown } | null;
  if (!response.ok || typeof payload?.upload_url !== "string" || typeof payload.object_key !== "string") {
    throw new Error("The storage signer could not create an upload URL.");
  }
  return { uploadUrl: payload.upload_url, objectKey: payload.object_key };
}

async function verifyUploadedObject(uploadId: string, filename: string) {
  const worker = workerConfiguration();
  const url = new URL(`${worker.workerUrl}/internal/storage/uploads/${encodeURIComponent(uploadId)}/exists`);
  url.searchParams.set("filename", filename);
  const response = await fetch(url, {
    headers: workerHeaders(worker),
    signal: AbortSignal.timeout(10000),
  });
  const payload = (await response.json().catch(() => null)) as { exists?: unknown } | null;
  const objectKey = typeof (payload as { object_key?: unknown } | null)?.object_key === "string"
    ? (payload as { object_key: string }).object_key
    : null;
  if (!response.ok || payload?.exists !== true || !objectKey) {
    throw new Error("The uploaded object was not found in private storage.");
  }
  return objectKey;
}

async function requestArtifactDownloadUrl(objectKey: string) {
  const worker = workerConfiguration();
  const response = await fetch(`${worker.workerUrl}/internal/storage/presign-download`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...workerHeaders(worker),
    },
    body: JSON.stringify({ object_key: objectKey }),
    signal: AbortSignal.timeout(10000),
  });
  const payload = (await response.json().catch(() => null)) as { download_url?: unknown } | null;
  if (!response.ok || typeof payload?.download_url !== "string") {
    throw new Error("The worker could not create an artifact download URL.");
  }
  return payload.download_url;
}

async function deleteWorkerUpload(uploadId: string, filename: string) {
  const worker = workerConfiguration();
  const url = new URL(`${worker.workerUrl}/internal/storage/uploads/${encodeURIComponent(uploadId)}`);
  url.searchParams.set("filename", filename);
  const response = await fetch(url, {
    method: "DELETE",
    headers: workerHeaders(worker),
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error("The worker could not delete the raw upload object.");
  }
}

async function deleteWorkerArtifacts(jobId: string) {
  const worker = workerConfiguration();
  const response = await fetch(`${worker.workerUrl}/internal/storage/jobs/${encodeURIComponent(jobId)}/artifacts`, {
    method: "DELETE",
    headers: workerHeaders(worker),
    signal: AbortSignal.timeout(20000),
  });
  if (!response.ok) {
    throw new Error("The worker could not delete the job artifacts.");
  }
}

async function validateStoredDataset(objectKey: string, filename: string) {
  const worker = workerConfiguration();
  const response = await fetch(`${worker.workerUrl}/internal/datasets/validate`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...workerHeaders(worker),
    },
    body: JSON.stringify({ dataset_object_key: objectKey, dataset_filename: filename }),
    signal: AbortSignal.timeout(20000),
  });
  const payload = asRecord(await response.json().catch(() => null));
  if (!response.ok || !payload) {
    throw new Error("The worker validation service is unavailable.");
  }
  return {
    summary: asRecord(payload.summary) ?? {},
    errors: asValidationIssues(payload.errors, "SCHEMA-001"),
    warnings: asValidationIssues(payload.warnings, "SCHEMA-WARN-001"),
  };
}

async function dispatchToWorker(job: JobRecord) {
  try {
    const dataset = await getDataset(job.datasetId);
    const metadata = asRecord(dataset?.metadata);
    const filename = typeof metadata?.filename === "string" ? metadata.filename : null;
    const resultWritePrefix = job.resultWritePrefix ?? `results/${job.jobId}`;

    if (!dataset?.objectKey || !filename) {
      throw new Error("The dataset has no finalized private storage object.");
    }

    const worker = workerConfiguration();
    const response = await fetch(`${worker.workerUrl}/internal/jobs/run`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...workerHeaders(worker),
      },
      body: JSON.stringify({
        job_id: job.jobId,
        dataset_id: job.datasetId,
        dataset_object_key: dataset.objectKey,
        dataset_filename: filename,
        result_write_prefix: resultWritePrefix,
        config_hash: job.configHash,
        callback_url: `${worker.appUrl}/api/orama/jobs/${encodeURIComponent(job.jobId)}/callback`,
        analysis_config: {
          horizons: job.config.horizons,
          min_history_days: job.config.min_history_days,
          min_observations_per_variable: job.config.min_observations_per_variable,
          prediction_gap_days: job.config.prediction_gap_days,
          test_size: 0.25,
          random_state: 42,
          analysis_locked: true,
        },
      }),
      signal: AbortSignal.timeout(20000),
    });

    if (!response.ok) {
      return (await updateJobStatus(job.jobId, "FAILED", {
        errorMessage: `Worker rejected the job with HTTP ${response.status}.`,
      })) ?? job;
    }

    const workerStatus = (await response.json().catch(() => null)) as {
      status?: unknown;
      error?: unknown;
      result?: unknown;
    } | null;
    const nextStatus = asJobStatus(workerStatus?.status) ?? "QUEUED";
    const updatedJob = nextStatus === "QUEUED"
      ? await getJob(job.jobId)
      : await updateJobStatus(job.jobId, nextStatus, {
          errorMessage: typeof workerStatus?.error === "string" ? workerStatus.error : undefined,
          result: normalizeWorkerResult(job.jobId, workerStatus?.result),
        });
    await recordAuditEvent("job.dispatched", job.jobId, {
      datasetId: job.datasetId,
      resultWritePrefix,
      configHash: job.configHash ?? null,
    });
    return updatedJob ?? job;
  } catch {
    return (await updateJobStatus(job.jobId, "FAILED", {
      errorMessage: "The worker could not be reached to start this research job.",
    })) ?? job;
  }
}

function createId(prefix: string): string {
  return `${prefix}_${randomUUID()}`;
}

function toJobRecord(row: typeof jobs.$inferSelect): JobRecord {
  return {
    jobId: row.jobId,
    datasetId: row.datasetId,
    status: row.status as JobRecord["status"],
    createdAt: row.createdAt.toISOString(),
    updatedAt: row.updatedAt.toISOString(),
    pollCount: row.pollCount,
    config: row.config as AnalysisConfig,
    configHash: row.configHash ?? undefined,
    analysisLockedAt: row.analysisLockedAt?.toISOString(),
    resultWritePrefix: row.resultWritePrefix ?? undefined,
    retentionUntil: row.retentionUntil?.toISOString(),
    result: (row.result as JobRecord["result"] | null) ?? undefined,
    errorMessage: row.errorMessage ?? undefined,
  };
}

export async function initiateUpload(payload: UploadInitiateRequest) {
  const db = getDb();
  const uploadId = createId("upl");
  const contentType = payload.contentType ?? "application/octet-stream";
  const retentionUntil = retentionDeadline();

  await db.insert(uploads).values({
    uploadId,
    filename: payload.filename,
    contentType,
    size: payload.size,
    retentionUntil,
  });

  const session = await requestUploadUrl(uploadId, payload.filename, contentType);
  await db
    .update(uploads)
    .set({ objectKey: session.objectKey })
    .where(eq(uploads.uploadId, uploadId));
  await recordAuditEvent("upload.initiated", uploadId, {
    filename: payload.filename,
    size: payload.size,
    retentionUntil: retentionUntil.toISOString(),
  });

  return {
    uploadId,
    uploadUrl: session.uploadUrl,
    expiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
  };
}

export async function getDataset(datasetId: string) {
  const db = getDb();
  const [row] = await db.select().from(datasets).where(eq(datasets.datasetId, datasetId)).limit(1);
  return row ?? null;
}

export async function completeUpload(payload: UploadCompleteRequest) {
  const db = getDb();
  const [upload] = await db.select().from(uploads).where(eq(uploads.uploadId, payload.uploadId)).limit(1);

  if (!upload) {
    return null;
  }

  const [existingDataset] = await db.select().from(datasets).where(eq(datasets.uploadId, upload.uploadId)).limit(1);
  if (existingDataset) {
    return {
      datasetId: existingDataset.datasetId,
      recordedAt: existingDataset.createdAt.toISOString(),
    };
  }

  const objectKey = await verifyUploadedObject(upload.uploadId, upload.filename);
  if (upload.objectKey && upload.objectKey !== objectKey) {
    throw new Error("The verified object key does not match the original upload session.");
  }

  const datasetId = createId("dataset");
  const retentionUntil = upload.retentionUntil ?? retentionDeadline();
  const metadata = {
    ...payload.metadata,
    filename: upload.filename,
    size: upload.size,
    contentType: upload.contentType,
  };

  await db.insert(datasets).values({
    datasetId,
    uploadId: payload.uploadId,
    objectKey,
    metadata,
    validationStatus: "PENDING",
    retentionUntil,
  });
  await db
    .update(uploads)
    .set({ objectKey, finalizedAt: new Date(), retentionUntil })
    .where(eq(uploads.uploadId, upload.uploadId));
  await recordAuditEvent("upload.completed", datasetId, {
    uploadId: payload.uploadId,
    filename: upload.filename,
    objectKey,
  });

  return {
    datasetId,
    recordedAt: new Date().toISOString(),
  };
}

export async function getDatasetValidationResult(datasetId: string) {
  const db = getDb();
  const dataset = await getDataset(datasetId);

  if (!dataset) {
    return null;
  }

  const uploadMetadata = (dataset.metadata as Record<string, unknown>) ?? {};
  const filename = String(uploadMetadata.filename ?? "dataset.bin");
  const extension = filename.includes(".") ? filename.slice(filename.lastIndexOf(".")).toLowerCase() : "";
  const size = Number(uploadMetadata.size ?? 0);
  const contentType = String(uploadMetadata.contentType ?? "application/octet-stream");

  const errors = [] as ValidationIssue[];
  const warnings = [] as ValidationIssue[];

  if (![".csv", ".parquet", ".zip"].includes(extension)) {
    errors.push({
      code: "FMT-001",
      field: "filename",
      message: `Unsupported extension ${extension || "(none)"}. Only CSV, Parquet, and ZIP files are accepted.`,
      suggestion: "Re-export the dataset as one of the supported research file formats.",
    });
  }

  if (size <= 0) {
    errors.push({
      code: "SIZE-001",
      field: "size",
      message: "The uploaded file has no measurable payload size.",
      suggestion: "Verify the file was uploaded and the browser supplied a valid content length.",
    });
  }

  if (!contentType || contentType === "application/octet-stream") {
    warnings.push({
      code: "META-002",
      field: "contentType",
      message: "The browser did not provide a precise MIME type for this upload.",
      suggestion: "Check that the file was generated by the expected export process and recorded with the correct MIME type.",
    });
  }

  if (extension === ".csv") {
    warnings.push({
      code: "CSV-001",
      field: "filename",
      message: "CSV imports are supported for synthetic previews, but Parquet or ZIP datasets are preferred for production research data.",
      suggestion: "Prefer a Parquet or partitioned dataset when the file is intended for model training or feasibility analysis.",
    });
  }

  let workerSummary: Record<string, unknown> = {};
  if (errors.length === 0 && dataset.objectKey) {
    try {
      const workerValidation = await validateStoredDataset(dataset.objectKey, filename);
      workerSummary = workerValidation.summary;
      errors.push(...workerValidation.errors);
      warnings.push(...workerValidation.warnings);
    } catch {
      errors.push({
        code: "WORKER-001",
        message: "Private dataset schema validation could not be completed.",
        suggestion: "Confirm the worker is reachable and retry validation before creating a job.",
      });
    }
  } else if (!dataset.objectKey) {
    errors.push({
      code: "STORE-001",
      message: "The dataset does not have a finalized private object.",
      suggestion: "Restart the upload flow so the object can be verified before validation.",
    });
  }

  const validationStatus = errors.length > 0 ? "FAILED" : "READY";
  await db
    .update(datasets)
    .set({ validationStatus })
    .where(eq(datasets.datasetId, datasetId));

  return {
    datasetId,
    generatedAt: new Date().toISOString(),
    summary: {
      errorCount: errors.length,
      warningCount: warnings.length,
      participantsSheet: asNumber(workerSummary.participants) !== null || (extension !== ".zip" && !!uploadMetadata.participants),
      observationsSheet: asNumber(workerSummary.observations) !== null || (extension !== ".zip" && !!uploadMetadata.observations),
      outcomesSheet: asNumber(workerSummary.outcomes) !== null || (extension !== ".zip" && !!uploadMetadata.outcomes),
      encountersSheet: asNumber(workerSummary.encounters) !== null || (extension !== ".zip" && !!uploadMetadata.encounters),
      dataDictionarySheet: asNumber(workerSummary.data_dictionary) !== null || (extension !== ".zip" && !!uploadMetadata.data_dictionary),
    },
    errors,
    warnings,
  };
}

export async function createJob(datasetId: string, config: AnalysisConfig): Promise<JobRecord> {
  const db = getDb();
  const dataset = await getDataset(datasetId);
  if (!dataset?.objectKey) {
    throw new Error("Dataset must be finalized in private storage before creating a job.");
  }

  const validation = await getDatasetValidationResult(datasetId);
  if (!validation || validation.errors.length > 0) {
    throw new Error("Dataset must pass validation before creating a job.");
  }

  const jobId = createId("job");
  const lockedConfig = freezeAnalysisConfig(config);
  const lockedAt = new Date();
  const configHash = configurationHash(lockedConfig);
  const retentionUntil = dataset.retentionUntil ?? retentionDeadline();

  const [row] = await db
    .insert(jobs)
    .values({
      jobId,
      datasetId,
      status: "QUEUED",
      config: lockedConfig,
      configHash,
      analysisLockedAt: lockedAt,
      resultWritePrefix: `results/${jobId}`,
      pollCount: 0,
      retentionUntil,
    })
    .returning();

  await recordAuditEvent("job.created", jobId, {
    datasetId,
    configHash,
    analysisLockedAt: lockedAt.toISOString(),
  });

  return toJobRecord(row);
}

export async function queueJobForWorker(job: JobRecord): Promise<JobRecord> {
  const scheduled = await dispatchToWorker(job);
  return scheduled ?? job;
}

export async function retryJob(jobId: string): Promise<JobRecord | null> {
  const db = getDb();
  const existing = await getJob(jobId);
  if (!existing || existing.status !== "FAILED") {
    return null;
  }

  const retryJobId = createId("job");
  const lockedConfig = freezeAnalysisConfig(existing.config);
  const [row] = await db
    .insert(jobs)
    .values({
      jobId: retryJobId,
      datasetId: existing.datasetId,
      status: "QUEUED",
      config: lockedConfig,
      configHash: existing.configHash ?? configurationHash(lockedConfig),
      analysisLockedAt: new Date(),
      resultWritePrefix: `results/${retryJobId}`,
      pollCount: 0,
      retentionUntil: existing.retentionUntil ? new Date(existing.retentionUntil) : retentionDeadline(),
    })
    .returning();

  const replacement = toJobRecord(row);
  await recordAuditEvent("job.retried", retryJobId, {
    previousJobId: jobId,
    datasetId: replacement.datasetId,
    configHash: replacement.configHash ?? null,
  });
  return queueJobForWorker(replacement);
}

export async function deleteJob(jobId: string): Promise<{ jobId: string } | null> {
  const db = getDb();
  const existing = await getJob(jobId);
  if (!existing) {
    return null;
  }
  if (!isTerminalStatus(existing.status)) {
    throw new Error("Only terminal jobs can be deleted.");
  }

  await deleteWorkerArtifacts(jobId);
  await db.delete(jobs).where(eq(jobs.jobId, jobId));
  await recordAuditEvent("job.deleted", jobId, {
    datasetId: existing.datasetId,
    status: existing.status,
  });
  return { jobId };
}

export async function listJobs(): Promise<JobRecord[]> {
  const db = getDb();
  const rows = await db.select().from(jobs).orderBy(desc(jobs.createdAt));
  return rows.map(toJobRecord);
}

export async function getJob(jobId: string): Promise<JobRecord | null> {
  const db = getDb();
  const [row] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);
  return row ? toJobRecord(row) : null;
}

export async function getReportArtifactDownloadUrl(jobId: string): Promise<string | null> {
  const job = await getJob(jobId);
  if (!job?.result || !isTerminalStatus(job.status)) {
    return null;
  }

  const expectedReference = `storage:results/${jobId}/report.json`;
  const reportReference = job.result.artifactReferences?.find((reference) => reference === expectedReference);
  if (!reportReference) {
    return null;
  }

  return requestArtifactDownloadUrl(reportReference.slice("storage:".length));
}

export async function deleteDataset(datasetId: string, reason: "manual" | "retention" = "manual") {
  const db = getDb();
  const [dataset] = await db.select().from(datasets).where(eq(datasets.datasetId, datasetId)).limit(1);
  if (!dataset) {
    return null;
  }

  const jobRows = await db.select().from(jobs).where(eq(jobs.datasetId, datasetId));
  if (jobRows.some((job) => job.status === "QUEUED" || job.status === "RUNNING")) {
    throw new Error("A dataset with queued or running jobs cannot be deleted.");
  }

  const [upload] = await db.select().from(uploads).where(eq(uploads.uploadId, dataset.uploadId)).limit(1);
  for (const job of jobRows) {
    await deleteWorkerArtifacts(job.jobId);
  }
  if (upload) {
    await deleteWorkerUpload(upload.uploadId, upload.filename);
  }

  await db.delete(jobs).where(eq(jobs.datasetId, datasetId));
  await db.delete(datasets).where(eq(datasets.datasetId, datasetId));
  if (upload) {
    await db.delete(uploads).where(eq(uploads.uploadId, upload.uploadId));
  }
  await recordAuditEvent("dataset.deleted", datasetId, {
    reason,
    deletedJobCount: jobRows.length,
  });

  return { datasetId, deletedJobCount: jobRows.length };
}

export async function purgeExpiredDatasets() {
  const db = getDb();
  const expiredDatasets = await db
    .select({ datasetId: datasets.datasetId })
    .from(datasets)
    .where(lt(datasets.retentionUntil, new Date()));

  const result = { deletedCount: 0, skippedCount: 0 };
  for (const dataset of expiredDatasets) {
    try {
      const deleted = await deleteDataset(dataset.datasetId, "retention");
      if (deleted) {
        result.deletedCount += 1;
      }
    } catch {
      result.skippedCount += 1;
    }
  }
  return result;
}

export async function refreshJobFromWorker(jobId: string): Promise<JobRecord | null> {
  const db = getDb();
  const [row] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);

  if (!row) {
    return null;
  }

  const currentStatus = asJobStatus(row.status) ?? "FAILED";
  if (isTerminalStatus(currentStatus)) {
    return toJobRecord(row);
  }

  const pollCount = row.pollCount + 1;
  try {
    const worker = workerConfiguration();
    const response = await fetch(`${worker.workerUrl}/internal/jobs/${encodeURIComponent(jobId)}`, {
      headers: workerHeaders(worker),
      signal: AbortSignal.timeout(10000),
    });
    if (response.status === 404) {
      const missingWorkerJob = await updateJobStatus(jobId, "FAILED", {
        errorMessage: "The worker no longer has this job, likely because its runtime restarted. This run has stopped. Retry creates a new run with the same locked configuration, or delete this failed run.",
      });
      await recordAuditEvent("job.worker_missing", jobId, {
        workerStatus: 404,
        pollCount,
      });
      return missingWorkerJob ?? toJobRecord(row);
    }
    if (!response.ok) {
      throw new Error("Worker status is unavailable.");
    }

    const workerStatus = (await response.json().catch(() => null)) as {
      status?: unknown;
      error?: unknown;
      result?: unknown;
    } | null;
    const nextStatus = asJobStatus(workerStatus?.status);
    if (!nextStatus) {
      throw new Error("Worker returned an invalid status.");
    }

    const normalizedResult = normalizeWorkerResult(jobId, workerStatus?.result);
    const [updated] = await db
      .update(jobs)
      .set({
        pollCount,
        status: nextStatus,
        updatedAt: new Date(),
        ...(typeof workerStatus?.error === "string" ? { errorMessage: workerStatus.error } : {}),
        ...(normalizedResult ? { result: normalizedResult } : {}),
      })
      .where(eq(jobs.jobId, jobId))
      .returning();

    return toJobRecord(updated);
  } catch {
    const [updated] = await db
      .update(jobs)
      .set({ pollCount, updatedAt: new Date() })
      .where(eq(jobs.jobId, jobId))
      .returning();
    return toJobRecord(updated);
  }
}

export async function applyJobCallback(jobId: string, payload: JobCallbackRequest): Promise<JobRecord | null> {
  const db = getDb();
  const [row] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);

  if (!row) {
    return null;
  }

  const currentStatus = asJobStatus(row.status) ?? "FAILED";
  if (isTerminalStatus(currentStatus) && currentStatus !== payload.status) {
    return toJobRecord(row);
  }

  const normalizedResult = normalizeWorkerResult(jobId, payload.workerResult);
  const result = normalizedResult ?? payload.result ?? row.result;

  const [updated] = await db
    .update(jobs)
    .set({
      status: payload.status,
      errorMessage: payload.errorMessage ?? null,
      updatedAt: new Date(),
      ...(result ? { result } : {}),
    })
    .where(eq(jobs.jobId, jobId))
    .returning();

  await recordAuditEvent(`job.${payload.status.toLowerCase()}`, jobId, {
    datasetId: row.datasetId,
    configHash: row.configHash ?? null,
  });
  return toJobRecord(updated);
}
