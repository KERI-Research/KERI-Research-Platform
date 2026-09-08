import type { UploadInitiateRequest, UploadInitiateResponse } from "@/types/orama";
import { initiateUpload } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";

function isValidBody(body: unknown): body is UploadInitiateRequest {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as UploadInitiateRequest).filename === "string" &&
    (typeof (body as UploadInitiateRequest).contentType === "string" || typeof (body as UploadInitiateRequest).contentType === "undefined") &&
    typeof (body as UploadInitiateRequest).size === "number" &&
    Number.isFinite((body as UploadInitiateRequest).size) &&
    (body as UploadInitiateRequest).size >= 0
  );
}

export async function POST(request: Request) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid upload initiation payload." }, { status: 400 });
  }

  const response: UploadInitiateResponse = await initiateUpload(body);
  return Response.json(response, { status: 201 });
}
