CREATE UNIQUE INDEX IF NOT EXISTS "datasets_upload_id_unique_idx" ON "datasets" ("upload_id");
--> statement-breakpoint
CREATE OR REPLACE FUNCTION prevent_terminal_job_status_regression()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF OLD."status" IN ('SUCCEEDED', 'FAILED', 'NOT_EVALUABLE')
    AND NEW."status" IS DISTINCT FROM OLD."status" THEN
    RAISE EXCEPTION 'terminal job status is immutable';
  END IF;
  RETURN NEW;
END;
$$;
--> statement-breakpoint
DROP TRIGGER IF EXISTS jobs_terminal_status_immutable ON "jobs";
--> statement-breakpoint
CREATE TRIGGER jobs_terminal_status_immutable
BEFORE UPDATE ON "jobs"
FOR EACH ROW EXECUTE FUNCTION prevent_terminal_job_status_regression();