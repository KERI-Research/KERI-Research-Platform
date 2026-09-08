import { getDatasetValidationResult } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";
import type { ValidationResult } from "@/types/orama";

interface DatasetRouteContext {
  params: Promise<{
    datasetId: string;
  }>;
}

async function buildResponse(request: Request, context: DatasetRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { datasetId } = await context.params;

  if (!datasetId) {
    return Response.json({ error: "datasetId is required." }, { status: 400 });
  }

  const result = await getDatasetValidationResult(datasetId);

  if (!result) {
    return Response.json({ error: "Dataset not found." }, { status: 404 });
  }

  return Response.json(result satisfies ValidationResult);
}

export async function GET(request: Request, context: DatasetRouteContext) {
  return buildResponse(request, context);
}

export async function POST(request: Request, context: DatasetRouteContext) {
  return buildResponse(request, context);
}
