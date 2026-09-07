import "server-only";

import { buildMockJobResult } from "@/lib/orama-mocks";
import type {
  AnalysisConfig,
  JobCallbackRequest,
  JobRecord,
  UploadCompleteRequest,
  UploadInitiateRequest,
} from "@/types/orama";

interface UploadRecord {
  uploadId: string;
  filename: string;
  contentType: string;
  size: number;
  createdAt: string;
}

interface DatasetRecord {
  datasetId: string;
  uploadId: string;
  metadata: UploadCompleteRequest["metadata"];
  createdAt: string;
}

type OramaGlobals = typeof globalThis & {
  __oramaJobs__?: Map<string, JobRecord>;
  __oramaUploads__?: Map<string, UploadRecord>;
  __oramaDatasets__?: Map<string, DatasetRecord>;
};

const globalForOrama = globalThis as OramaGlobals;

const jobs = globalForOrama.__oramaJobs__ ?? new Map<string, JobRecord>();
const uploads = globalForOrama.__oramaUploads__ ?? new Map<string, UploadRecord>();
const datasets = globalForOrama.__oramaDatasets__ ?? new Map<string, DatasetRecord>();

globalForOrama.__oramaJobs__ = jobs;
globalForOrama.__oramaUploads__ = uploads;
globalForOrama.__oramaDatasets__ = datasets;

function createId(prefix: string): string {
  return `${prefix}_${Math.random().toString(36).slice(2, 10)}`;
}

function cloneJob(job: JobRecord): JobRecord {
  return JSON.parse(JSON.stringify(job)) as JobRecord;
}

export function initiateUpload(payload: UploadInitiateRequest) {
  const uploadId = createId("upl");
  const record: UploadRecord = {
    uploadId,
    filename: payload.filename,
    contentType: payload.contentType ?? "application/octet-stream",
    size: payload.size,
    createdAt: new Date().toISOString(),
  };

  uploads.set(uploadId, record);

  return {
    uploadId,
    uploadUrl: "TODO-private-object-storage",
    expiresAt: new Date(Date.now() + 15 * 60 * 1000).toISOString(),
  };
}

export function completeUpload(payload: UploadCompleteRequest) {
  const upload = uploads.get(payload.uploadId);

  if (!upload) {
    return null;
  }

  const datasetId = createId("dataset");

  datasets.set(datasetId, {
    datasetId,
    uploadId: payload.uploadId,
    metadata: payload.metadata,
    createdAt: new Date().toISOString(),
  });

  return {
    datasetId,
    recordedAt: new Date().toISOString(),
  };
}

export function createJob(datasetId: string, config: AnalysisConfig): JobRecord {
  const now = new Date().toISOString();
  const job: JobRecord = {
    jobId: createId("job"),
    datasetId,
    status: "QUEUED",
    createdAt: now,
    updatedAt: now,
    pollCount: 0,
    config,
  };

  jobs.set(job.jobId, job);
  return cloneJob(job);
}

export function listJobs(): JobRecord[] {
  return Array.from(jobs.values())
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
    .map(cloneJob);
}

export function getJob(jobId: string): JobRecord | null {
  const job = jobs.get(jobId);
  return job ? cloneJob(job) : null;
}

export function getAndAdvanceJob(jobId: string): JobRecord | null {
  const job = jobs.get(jobId);

  if (!job) {
    return null;
  }

  if (job.status === "QUEUED" || job.status === "RUNNING") {
    job.pollCount += 1;
    job.updatedAt = new Date().toISOString();

    if (job.pollCount >= 2) {
      job.status = "RUNNING";
    }

    if (job.pollCount >= 4) {
      job.status = "SUCCEEDED";
      job.result ??= buildMockJobResult(job.jobId);
    }
  }

  jobs.set(jobId, job);
  return cloneJob(job);
}

export function applyJobCallback(jobId: string, payload: JobCallbackRequest): JobRecord | null {
  const job = jobs.get(jobId);

  if (!job) {
    return null;
  }

  job.status = payload.status;
  job.updatedAt = new Date().toISOString();
  job.errorMessage = payload.errorMessage;
  job.result = payload.result ?? job.result ?? (payload.status === "SUCCEEDED" ? buildMockJobResult(jobId) : undefined);

  jobs.set(jobId, job);
  return cloneJob(job);
}
