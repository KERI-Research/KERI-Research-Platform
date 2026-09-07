CREATE TABLE IF NOT EXISTS "uploads" (
	"upload_id" text PRIMARY KEY NOT NULL,
	"filename" text NOT NULL,
	"content_type" text DEFAULT 'application/octet-stream' NOT NULL,
	"size" integer NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "datasets" (
	"dataset_id" text PRIMARY KEY NOT NULL,
	"upload_id" text NOT NULL,
	"metadata" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "jobs" (
	"job_id" text PRIMARY KEY NOT NULL,
	"dataset_id" text NOT NULL,
	"status" text DEFAULT 'QUEUED' NOT NULL,
	"config" jsonb,
	"result" jsonb,
	"error_message" text,
	"poll_count" integer DEFAULT 0 NOT NULL,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE IF NOT EXISTS "audit_log" (
	"id" text PRIMARY KEY NOT NULL,
	"event_type" text NOT NULL,
	"entity_id" text,
	"actor_id" text,
	"payload" jsonb,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "datasets" ADD CONSTRAINT "datasets_upload_id_uploads_upload_id_fk" FOREIGN KEY ("upload_id") REFERENCES "public"."uploads"("upload_id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
--> statement-breakpoint
DO $$ BEGIN
 ALTER TABLE "jobs" ADD CONSTRAINT "jobs_dataset_id_datasets_dataset_id_fk" FOREIGN KEY ("dataset_id") REFERENCES "public"."datasets"("dataset_id") ON DELETE no action ON UPDATE no action;
EXCEPTION
 WHEN duplicate_object THEN null;
END $$;
