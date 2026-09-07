import "server-only";

import { neon } from "@neondatabase/serverless";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "@/lib/schema";

let db: ReturnType<typeof drizzle> | undefined;

export function getDb() {
  if (!db) {
    const databaseUrl = process.env.ORAMA_DATABASE_URL;

    if (!databaseUrl) {
      throw new Error("ORAMA_DATABASE_URL must be set before using the database.");
    }

    const sql = neon(databaseUrl);
    db = drizzle(sql, { schema });
  }

  return db;
}
