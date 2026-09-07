import "server-only";

import { randomUUID } from "node:crypto";
import { desc, eq } from "drizzle-orm";

import { getDb } from "@/lib/db";
import { buildMockJobResult } from "@/lib/orama-mocks";
import { datasets, jobs, uploads } from "@/lib/schema";
import type {
  AnalysisConfig,
  JobCallbackRequest,
  JobRecord,
  UploadCompleteRequest,
  UploadInitiateRequest,
} from "@/types/orama";

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
    result: (row.result as JobRecord["result"] | null) ?? undefined,
    errorMessage: row.errorMessage ?? undefined,
  };
}

export async function initiateUpload(payload: UploadInitiateRequest) {
  const db = getDb();
  const uploadId = createId("upl");

  await db.insert(uploads).values({
    uploadId,
    filename: payload.filename,
    contentType: payload.contentType ?? "application/octet-stream",
    size: payload.size,
  });

  return {
    uploadId,
    uploadUrl: "TODO-private-object-storage",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
  };
}

export async function completeUpload(payload: UploadCompleteRequest) {
  const db = getDb();
  const [upload] = await db.select().from(uploads).where(eq(uploads.uploadId, payload.uploadId)).limit(1);

  if (!upload) {
    return null;
  }

  const datasetId = createId("dataset");

  await db.insert(datasets).values({
    datasetId,
    uploadId: payload.uploadId,
    metadata: payload.metadata,
  });

  return {
    datasetId,
    recordedAt: new Date().toISOString(),
  };
}

export async function createJob(datasetId: string, config: AnalysisConfig): Promise<JobRecord> {
  const db = getDb();
  const jobId = createId("job");

  const [row] = await db
    .insert(jobs)
    .values({
      jobId,
      datasetId,
      status: "QUEUED",
      config,
      pollCount: 0,
    })
    .returning();

  return toJobRecord(row);
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

export async function getAndAdvanceJob(jobId: string): Promise<JobRecord | null> {
  const db = getDb();
  const [row] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);

  if (!row) {
    return null;
  }

  if (row.status !== "QUEUED" && row.status !== "RUNNING") {
    return toJobRecord(row);
  }

  const pollCount = row.pollCount + 1;
  let status = row.status;
  let result = row.result;

  if (pollCount >= 2) {
    status = "RUNNING";
  }

  if (pollCount >= 4) {
    status = "SUCCEEDED";
    result = result ?? buildMockJobResult(row.jobId);
  }

  const [updated] = await db
    .update(jobs)
    .set({
      pollCount,
      status,
      result,
      updatedAt: new Date(),
    })
    .where(eq(jobs.jobId, jobId))
    .returning();

  return toJobRecord(updated);
}

export async function applyJobCallback(jobId: string, payload: JobCallbackRequest): Promise<JobRecord | null> {
  const db = getDb();
  const [row] = await db.select().from(jobs).where(eq(jobs.jobId, jobId)).limit(1);

  if (!row) {
    return null;
  }

  const result =
    payload.result ?? row.result ?? (payload.status === "SUCCEEDED" ? buildMockJobResult(jobId) : undefined);

  const [updated] = await db
    .update(jobs)
    .set({
      status: payload.status,
      errorMessage: payload.errorMessage ?? null,
      result,
      updatedAt: new Date(),
    })
    .where(eq(jobs.jobId, jobId))
    .returning();

  return toJobRecord(updated);
}
