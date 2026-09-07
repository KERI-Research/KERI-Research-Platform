import type { UploadInitiateRequest, UploadInitiateResponse } from "@/types/orama";
import { initiateUpload } from "@/lib/orama-store";

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
  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid upload initiation payload." }, { status: 400 });
  }

  // TODO: Replace this mock target with a presigned private object-storage URL
  // (S3, GCS, or Azure Blob) generated server-side so file bytes never transit the client bundle.
  const response: UploadInitiateResponse = initiateUpload(body);
  return Response.json(response, { status: 201 });
}
