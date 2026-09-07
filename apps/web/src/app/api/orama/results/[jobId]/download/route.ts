import { getJob } from "@/lib/orama-store";

interface DownloadRouteContext {
  params: Promise<{
    jobId: string;
  }>;
}

export async function GET(_request: Request, context: DownloadRouteContext) {
  const { jobId } = await context.params;

  if (!jobId) {
    return Response.json({ error: "jobId is required." }, { status: 400 });
  }

  const job = await getJob(jobId);

  if (!job?.result) {
    return Response.json({ error: "No completed mock report is available for this job." }, { status: 404 });
  }

  // TODO: Stream the finalized report artifact from private object storage rather than generating inline JSON.
  const payload = JSON.stringify(
    {
      jobId: job.jobId,
      datasetId: job.datasetId,
      status: job.status,
      report: job.result.report,
      cohortExclusions: job.result.cohortExclusions,
      comparison: job.result.comparison,
      warnings: job.result.warnings,
    },
    null,
    2,
  );

  return new Response(payload, {
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Content-Disposition": `attachment; filename="orama-report-${jobId}.json"`,
    },
  });
}
