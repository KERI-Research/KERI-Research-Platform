import { createJob, listJobs } from "@/lib/orama-store";
import type { AnalysisConfig, CreateJobRequest, CreateJobResponse, JobsListResponse } from "@/types/orama";

function isAnalysisConfig(config: unknown): config is AnalysisConfig {
  return (
    typeof config === "object" &&
    config !== null &&
    Array.isArray((config as AnalysisConfig).horizons) &&
    (config as AnalysisConfig).horizons.every((value) => typeof value === "number" && Number.isFinite(value) && value > 0) &&
    typeof (config as AnalysisConfig).min_history_days === "number" &&
    typeof (config as AnalysisConfig).min_observations_per_variable === "number" &&
    typeof (config as AnalysisConfig).prediction_gap_days === "number"
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

export async function GET() {
  const response: JobsListResponse = {
    jobs: listJobs(),
  };

  return Response.json(response);
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid job creation payload." }, { status: 400 });
  }

  const job = createJob(body.datasetId, body.config);

  // TODO: Replace this in-memory queue with a real database record, then trigger the worker via
  // process.env.ORAMA_WORKER_URL using a server-side Authorization or x-orama-worker-secret header
  // derived from process.env.ORAMA_WORKER_SHARED_SECRET. Never expose that secret to the client bundle.
  const response: CreateJobResponse = {
    jobId: job.jobId,
    status: job.status,
    createdAt: job.createdAt,
  };

  return Response.json(response, { status: 201 });
}
