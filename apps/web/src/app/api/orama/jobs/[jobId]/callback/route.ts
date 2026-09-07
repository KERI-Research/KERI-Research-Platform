import { applyJobCallback } from "@/lib/orama-store";
import type { JobCallbackRequest, JobStatusResponse } from "@/types/orama";

interface JobCallbackContext {
  params: Promise<{
    jobId: string;
  }>;
}

function isValidBody(body: unknown): body is JobCallbackRequest {
  const validStatuses = ["SUCCEEDED", "FAILED", "NOT_EVALUABLE"];

  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as JobCallbackRequest).status === "string" &&
    validStatuses.includes((body as JobCallbackRequest).status)
  );
}

export async function POST(request: Request, context: JobCallbackContext) {
  const { jobId } = await context.params;
  const body: unknown = await request.json().catch(() => null);

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid job callback payload." }, { status: 400 });
  }

  const workerSecretHeader = request.headers.get("x-orama-worker-secret");
  void workerSecretHeader;

  // TODO: Enforce comparison of x-orama-worker-secret against process.env.ORAMA_WORKER_SHARED_SECRET
  // before accepting a real worker callback. The mock scaffold only documents the expected header shape.
  const job = applyJobCallback(jobId, body);

  if (!job) {
    return Response.json({ error: "Job not found." }, { status: 404 });
  }

  const response: JobStatusResponse = { job };
  return Response.json(response);
}
