import { buildMockValidationResult } from "@/lib/orama-mocks";
import type { ValidationResult } from "@/types/orama";

interface DatasetRouteContext {
  params: Promise<{
    datasetId: string;
  }>;
}

async function buildResponse(context: DatasetRouteContext) {
  const { datasetId } = await context.params;

  if (!datasetId) {
    return Response.json({ error: "datasetId is required." }, { status: 400 });
  }

  // TODO: Call the real validation worker or validation microservice and return its structured findings.
  const result: ValidationResult = buildMockValidationResult(datasetId);
  return Response.json(result);
}

export async function GET(_request: Request, context: DatasetRouteContext) {
  return buildResponse(context);
}

export async function POST(_request: Request, context: DatasetRouteContext) {
  return buildResponse(context);
}
