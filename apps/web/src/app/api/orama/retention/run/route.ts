import { createHash, timingSafeEqual } from "node:crypto";

import { purgeExpiredDatasets } from "@/lib/orama-store";

function isAuthorized(request: Request) {
  const expected = process.env.ORAMA_RETENTION_CRON_SECRET ?? process.env.CRON_SECRET;
  const provided = request.headers.get("authorization")?.replace(/^Bearer\s+/, "") ?? "";
  if (!expected) {
    return null;
  }
  const expectedHash = createHash("sha256").update(expected).digest();
  const providedHash = createHash("sha256").update(provided).digest();
  return timingSafeEqual(expectedHash, providedHash);
}

export async function POST(request: Request) {
  const authorized = isAuthorized(request);
  if (authorized === null) {
    return Response.json({ error: "Retention cron secret is not configured." }, { status: 503 });
  }
  if (!authorized) {
    return Response.json({ error: "Invalid retention authorization." }, { status: 401 });
  }

  return Response.json(await purgeExpiredDatasets());
}