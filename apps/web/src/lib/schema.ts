import { pgTable, text, integer, timestamp, jsonb } from "drizzle-orm/pg-core";

export const uploads = pgTable("uploads", {
  uploadId: text("upload_id").primaryKey(),
  filename: text("filename").notNull(),
  contentType: text("content_type").notNull().default("application/octet-stream"),
  size: integer("size").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const datasets = pgTable("datasets", {
  datasetId: text("dataset_id").primaryKey(),
  uploadId: text("upload_id")
    .notNull()
    .references(() => uploads.uploadId),
  metadata: jsonb("metadata"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const jobs = pgTable("jobs", {
  jobId: text("job_id").primaryKey(),
  datasetId: text("dataset_id")
    .notNull()
    .references(() => datasets.datasetId),
  status: text("status").notNull().default("QUEUED"),
  config: jsonb("config"),
  result: jsonb("result"),
  errorMessage: text("error_message"),
  pollCount: integer("poll_count").notNull().default(0),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const auditLog = pgTable("audit_log", {
  id: text("id").primaryKey(),
  eventType: text("event_type").notNull(),
  entityId: text("entity_id"),
  actorId: text("actor_id"),
  payload: jsonb("payload"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
