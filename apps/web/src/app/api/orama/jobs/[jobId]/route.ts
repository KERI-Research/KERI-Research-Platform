import { deleteJob, refreshJobFromWorker, retryJob } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";
import type { JobStatusResponse } from "@/types/orama";

interface JobRouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(request: Request, context: JobRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { jobId } = await context.params;

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  const job = await refreshJobFromWorker(jobId);

  if (!job) {
    return Response.json({ error: "Job not found." }, { status: 404 });
  }

  const response: JobStatusResponse = { job };
  return Response.json(response);
}

export async function POST(request: Request, context: JobRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { jobId } = await context.params;
  const body: unknown = await request.json().catch(() => null);
  if (!jobId || !body || typeof body !== "object" || (body as { action?: unknown }).action !== "retry") {
    return Response.json({ error: "A retry action and jobId are required." }, { status: 400 });
  }

  const replacement = await retryJob(jobId);
  if (!replacement) {
    return Response.json({ error: "Only a failed job can be retried." }, { status: 409 });
  }
  return Response.json({ job: replacement }, { status: 201 });
}

export async function DELETE(request: Request, context: JobRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { jobId } = await context.params;
  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  try {
    const deleted = await deleteJob(jobId);
    if (!deleted) {
      return Response.json({ error: "Job not found." }, { status: 404 });
    }
    return Response.json(deleted);
  } catch {
    return Response.json({ error: "Only terminal jobs with removable artifacts can be deleted." }, { status: 409 });
  }
}
