import { config } from "dotenv";
import type { Config } from "drizzle-kit";

config({ path: ".env.local" });

if (!process.env.ORAMA_DATABASE_URL_UNPOOLED) {
  throw new Error("ORAMA_DATABASE_URL_UNPOOLED must be set for Drizzle migrations.");
}

export default {
  schema: "./src/lib/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  dbCredentials: { url: process.env.ORAMA_DATABASE_URL_UNPOOLED },
} satisfies Config;
