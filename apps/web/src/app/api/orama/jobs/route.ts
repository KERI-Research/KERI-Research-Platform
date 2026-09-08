import { createJob, listJobs, queueJobForWorker } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";
import type { AnalysisConfig, CreateJobRequest, CreateJobResponse, JobsListResponse } from "@/types/orama";

function isAnalysisConfig(config: unknown): config is AnalysisConfig {
  return (
    typeof config === "object" &&
    config !== null &&
    Array.isArray((config as AnalysisConfig).horizons) &&
    (config as AnalysisConfig).horizons.every((value) => Number.isInteger(value) && value > 0 && value <= 3650) &&
    Number.isInteger((config as AnalysisConfig).min_history_days) &&
    (config as AnalysisConfig).min_history_days >= 0 &&
    (config as AnalysisConfig).min_history_days <= 3650 &&
    Number.isInteger((config as AnalysisConfig).min_observations_per_variable) &&
    (config as AnalysisConfig).min_observations_per_variable >= 1 &&
    (config as AnalysisConfig).min_observations_per_variable <= 100 &&
    Number.isInteger((config as AnalysisConfig).prediction_gap_days) &&
    (config as AnalysisConfig).prediction_gap_days >= 0 &&
    (config as AnalysisConfig).prediction_gap_days <= 3650
  );
}

function isValidBody(body: unknown): body is CreateJobRequest {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as CreateJobRequest).datasetId === "string" &&
    isAnalysisConfig((body as CreateJobRequest).config)
  );
}

export async function GET(request: Request) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const response: JobsListResponse = {
    jobs: await listJobs(),
  };

  return Response.json(response);
}

export async function POST(request: Request) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid job creation payload." }, { status: 400 });
  }

  const createdJob = await createJob(body.datasetId, body.config);
  const job = await queueJobForWorker(createdJob);

  const response: CreateJobResponse = {
    jobId: job.jobId,
    status: job.status,
    createdAt: job.createdAt,
  };

  return Response.json(response, { status: 201 });
}
