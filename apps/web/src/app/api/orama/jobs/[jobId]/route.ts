import { getAndAdvanceJob } from "@/lib/orama-store";
import type { JobStatusResponse } from "@/types/orama";

interface JobRouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(_request: Request, context: JobRouteContext) {
  const { jobId } = await context.params;

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  const job = getAndAdvanceJob(jobId);

  if (!job) {
    return Response.json({ error: "Job not found." }, { status: 404 });
  }

  const response: JobStatusResponse = { job };
  return Response.json(response);
}
