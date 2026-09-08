export type JobStatus = "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "NOT_EVALUABLE";

export interface UploadInitiateRequest {
  filename: string;
  contentType?: string;
  size: number;
}

export interface UploadInitiateResponse {
  uploadId: string;
  uploadUrl: string;
  expiresAt: string;
}

export interface UploadCompleteRequest {
  uploadId: string;
  metadata: Record<string, string | number | boolean | null>;
}

export interface UploadCompleteResponse {
  datasetId: string;
  recordedAt: string;
}

export interface ValidationIssue {
  code: string;
  field?: string;
  message: string;
  suggestion?: string;
}

export interface ValidationSummary {
  errorCount: number;
  warningCount: number;
  participantsSheet: boolean;
  observationsSheet: boolean;
  outcomesSheet: boolean;
  encountersSheet: boolean;
  dataDictionarySheet: boolean;
}

export interface ValidationResult {
  datasetId: string;
  generatedAt: string;
  summary: ValidationSummary;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface AnalysisConfig {
  horizons: number[];
  min_history_days: number;
  min_observations_per_variable: number;
  prediction_gap_days: number;
}

export interface CreateJobRequest {
  datasetId: string;
  config: AnalysisConfig;
}

export interface CreateJobResponse {
  jobId: string;
  status: JobStatus;
  createdAt: string;
}

export interface CohortExclusionRow {
  reason: string;
  count: number;
  percent: number;
}

export interface TrajectoryComparisonRow {
  measure: string;
  staticModel: number;
  trajectoryModel: number;
  delta: number;
}

export interface ReportMetric {
  name: string;
  value: string;
  note: string;
}

export interface ResearchReport {
  executiveSummary: string;
  metrics: ReportMetric[];
  limitations: string[];
  disclaimer: string;
  generatedAt: string;
}

export interface JobResult {
  cohortExclusions: CohortExclusionRow[];
  comparison: TrajectoryComparisonRow[];
  warnings: string[];
  report: ResearchReport;
  feasibilityDecision?: string;
  decisionReasons?: string[];
  artifactReferences?: string[];
}

export interface JobRecord {
  jobId: string;
  datasetId: string;
  status: JobStatus;
  createdAt: string;
  updatedAt: string;
  pollCount: number;
  config: AnalysisConfig;
  configHash?: string;
  analysisLockedAt?: string;
  resultWritePrefix?: string;
  retentionUntil?: string;
  result?: JobResult;
  errorMessage?: string;
}

export interface JobStatusResponse {
  job: JobRecord;
}

export interface JobsListResponse {
  jobs: JobRecord[];
}

export interface JobCallbackRequest {
  status: Exclude<JobStatus, "QUEUED" | "RUNNING">;
  result?: JobResult;
  workerResult?: unknown;
  errorMessage?: string;
}

export interface DatasetMetadataPreview {
  filename: string;
  size: number;
  contentType: string;
  extension: string;
  headerRow?: string[];
  rowCount?: number;
}
