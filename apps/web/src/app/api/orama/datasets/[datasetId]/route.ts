import { deleteDataset } from "@/lib/orama-store";
import { requireResearchAccess } from "@/lib/research-access";

interface DatasetRouteContext {
  params: Promise<{
    datasetId: string;
  }>;
}

export async function DELETE(request: Request, context: DatasetRouteContext) {
  const accessFailure = requireResearchAccess(request);
  if (accessFailure) {
    return accessFailure;
  }

  const { datasetId } = await context.params;
  if (!datasetId) {
    return Response.json({ error: "datasetId is required." }, { status: 400 });
  }

  try {
    const deleted = await deleteDataset(datasetId);
    if (!deleted) {
      return Response.json({ error: "Dataset not found." }, { status: 404 });
    }
    return Response.json(deleted);
  } catch {
    return Response.json(
      { error: "Dataset deletion is unavailable while it has active jobs or private storage cannot be updated." },
      { status: 409 },
    );
  }
}