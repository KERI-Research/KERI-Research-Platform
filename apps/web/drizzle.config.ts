import type { Config } from "drizzle-kit";

export default {
  schema: "./src/lib/schema.ts",
  out: "./drizzle",
  dialect: "postgresql",
  // drizzle-kit push uses the ws driver automatically for Neon URLs.
  // The neon-http driver (used at runtime) cannot perform DDL and must not
  // be specified here — leaving driver unset lets drizzle-kit choose correctly.
  dbCredentials: { url: process.env.ORAMA_DATABASE_URL! },
} satisfies Config;
