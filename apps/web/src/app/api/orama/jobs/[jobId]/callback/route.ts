import { createHash, timingSafeEqual } from "node:crypto";
import { applyJobCallback } from "@/lib/orama-store";
import type { JobCallbackRequest, JobStatusResponse } from "@/types/orama";

interface JobCallbackContext {
  params: Promise<{
    jobId: string;
  }>;
}

interface WorkerCallbackPayload {
  status: JobCallbackRequest["status"];
  worker_result?: unknown;
  error_message?: unknown;
}

function isValidBody(body: unknown): body is WorkerCallbackPayload {
  const validStatuses = ["SUCCEEDED", "FAILED", "NOT_EVALUABLE"];

  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as WorkerCallbackPayload).status === "string" &&
    validStatuses.includes((body as WorkerCallbackPayload).status)
  );
}

export async function POST(request: Request, context: JobCallbackContext) {
  const { jobId } = await context.params;

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  const expectedWorkerSecret = process.env.ORAMA_WORKER_SHARED_SECRET;

  if (!expectedWorkerSecret) {
    return Response.json(
      { error: "Worker shared secret is not configured." },
      { status: 503 },
    );
  }

  const workerSecretHeader = request.headers.get("x-orama-worker-secret");
  const expectedSecretHash = createHash("sha256").update(expectedWorkerSecret).digest();
  const providedSecretHash = createHash("sha256").update(workerSecretHeader ?? "").digest();

  // This is a real server-side secret check now; ORAMA_WORKER_SHARED_SECRET stays server-only in app/api.
  if (!workerSecretHeader || !timingSafeEqual(providedSecretHash, expectedSecretHash)) {
    return Response.json({ error: "Invalid worker shared secret." }, { status: 401 });
  }

  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid job callback payload." }, { status: 400 });
  }

  const job = await applyJobCallback(jobId, {
    status: body.status,
    workerResult: body.worker_result,
    errorMessage: typeof body.error_message === "string" ? body.error_message : undefined,
  });

  if (!job) {
    return Response.json({ error: "Job not found." }, { status: 404 });
  }

  const response: JobStatusResponse = { job };
  return Response.json(response);
}
