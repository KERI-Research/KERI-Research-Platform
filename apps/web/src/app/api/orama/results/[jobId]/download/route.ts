import { getReportArtifactDownloadUrl } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";

interface DownloadRouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(request: Request, context: DownloadRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { jobId } = await context.params;

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  const downloadUrl = await getReportArtifactDownloadUrl(jobId);
  if (!downloadUrl) {
    return Response.json({ error: "No completed report artifact is available for this job." }, { status: 404 });
  }

  return Response.redirect(downloadUrl, 307);
}
