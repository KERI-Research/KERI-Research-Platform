import { completeUpload } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";
import type { UploadCompleteRequest, UploadCompleteResponse } from "@/types/orama";

function isMetadataRecord(value: unknown): value is Record<string, string | number | boolean | null> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return false;
  }

  return Object.values(value).every(
    (entry) => entry === null || typeof entry === "string" || typeof entry === "number" || typeof entry === "boolean",
  );
}

function isValidBody(body: unknown): body is UploadCompleteRequest {
  return (
    typeof body === "object" &&
    body !== null &&
    typeof (body as UploadCompleteRequest).uploadId === "string" &&
    isMetadataRecord((body as UploadCompleteRequest).metadata)
  );
}

export async function POST(request: Request) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const body: unknown = await request.json().catch(() => null);

  if (!isValidBody(body)) {
    return Response.json({ error: "Invalid upload completion payload." }, { status: 400 });
  }

  const response = await completeUpload(body);

  if (!response) {
    return Response.json({ error: "Unknown uploadId." }, { status: 404 });
  }

  return Response.json(response satisfies UploadCompleteResponse, { status: 201 });
}
