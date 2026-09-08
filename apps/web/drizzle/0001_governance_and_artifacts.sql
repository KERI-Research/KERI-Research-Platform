ALTER TABLE "uploads" ADD COLUMN IF NOT EXISTS "object_key" text;
--> statement-breakpoint
ALTER TABLE "uploads" ADD COLUMN IF NOT EXISTS "finalized_at" timestamp with time zone;
--> statement-breakpoint
ALTER TABLE "uploads" ADD COLUMN IF NOT EXISTS "retention_until" timestamp with time zone;
--> statement-breakpoint
ALTER TABLE "datasets" ADD COLUMN IF NOT EXISTS "object_key" text;
--> statement-breakpoint
ALTER TABLE "datasets" ADD COLUMN IF NOT EXISTS "validation_status" text DEFAULT 'PENDING' NOT NULL;
--> statement-breakpoint
ALTER TABLE "datasets" ADD COLUMN IF NOT EXISTS "retention_until" timestamp with time zone;
--> statement-breakpoint
ALTER TABLE "jobs" ADD COLUMN IF NOT EXISTS "config_hash" text;
--> statement-breakpoint
ALTER TABLE "jobs" ADD COLUMN IF NOT EXISTS "analysis_locked_at" timestamp with time zone;
--> statement-breakpoint
ALTER TABLE "jobs" ADD COLUMN IF NOT EXISTS "result_write_prefix" text;
--> statement-breakpoint
ALTER TABLE "jobs" ADD COLUMN IF NOT EXISTS "retention_until" timestamp with time zone;
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "uploads_retention_until_idx" ON "uploads" ("retention_until");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "datasets_retention_until_idx" ON "datasets" ("retention_until");
--> statement-breakpoint
CREATE INDEX IF NOT EXISTS "jobs_retention_until_idx" ON "jobs" ("retention_until");
--> statement-breakpoint
CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_log records are append-only';
END;
$$;
--> statement-breakpoint
DROP TRIGGER IF EXISTS audit_log_immutable ON "audit_log";
--> statement-breakpoint
CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON "audit_log"
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_mutation();
--> statement-breakpoint
CREATE OR REPLACE FUNCTION prevent_locked_job_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD."analysis_locked_at" IS NOT NULL AND (
    NEW."dataset_id" IS DISTINCT FROM OLD."dataset_id" OR
    NEW."config" IS DISTINCT FROM OLD."config" OR
    NEW."config_hash" IS DISTINCT FROM OLD."config_hash" OR
    NEW."analysis_locked_at" IS DISTINCT FROM OLD."analysis_locked_at"
  ) THEN
    RAISE EXCEPTION 'locked job configuration is immutable';
  END IF;
  RETURN NEW;
END;
$$;
--> statement-breakpoint
DROP TRIGGER IF EXISTS jobs_locked_config_immutable ON "jobs";
--> statement-breakpoint
CREATE TRIGGER jobs_locked_config_immutable
BEFORE UPDATE ON "jobs"
FOR EACH ROW EXECUTE FUNCTION prevent_locked_job_mutation();