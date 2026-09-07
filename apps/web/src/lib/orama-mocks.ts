import type { JobResult, ValidationResult } from "@/types/orama";

export const APP_NAME = "ORAMA Research Platform";
export const RESEARCH_DISCLAIMER =
  "Research use only — non-diagnostic. Synthetic data only. Not for clinical decision-making.";
export const SCAFFOLD_NOTICE =
  "This scaffold only demonstrates a mocked synthetic workflow. It does not store, upload, or transmit real dataset contents.";

export const ACCEPTED_EXTENSIONS = [".csv", ".parquet", ".zip"] as const;

export const REQUIRED_CONTRACT_FIELDS = [
  "patient_id",
  "observed_at",
  "variable_code",
  "value",
  "unit",
  "source",
  "diagnosis_date",
  "cancer_type",
  "incident_flag",
] as const;

export const CONTRACT_SECTIONS = [
  "participants",
  "observations",
  "outcomes",
  "encounters",
  "data_dictionary",
] as const;

export const SAMPLE_COLUMNS = [
  "subject_key",
  "visit_date",
  "lab_ldl",
  "lab_hba1c",
  "procedure_source",
  "unit_label",
  "first_cancer_dx_date",
  "tumor_group",
  "is_incident_case",
  "encounter_type",
] as const;

export const DEFAULT_ANALYSIS_CONFIG = {
  horizons: [30, 90, 180, 365, 730],
  min_history_days: 365,
  min_observations_per_variable: 2,
  prediction_gap_days: 30,
} as const;

export function buildMockValidationResult(datasetId: string): ValidationResult {
  const errors = [
    {
      code: "OBS-001",
      field: "observed_at",
      message: "14 observation rows have timestamps earlier than the participant enrollment date.",
      suggestion: "Reconcile encounter chronology before downstream modeling.",
    },
    {
      code: "OUT-003",
      field: "incident_flag",
      message: "3 outcome rows are missing an incident_flag value.",
      suggestion: "Populate a boolean incident flag for each outcome record.",
    },
  ];

  const warnings = [
    {
      code: "DD-007",
      field: "variable_code",
      message: "Six variable codes do not yet have descriptions in the data dictionary scaffold.",
      suggestion: "Document each variable before handing off to a real validator or worker.",
    },
    {
      code: "ENC-004",
      field: "source",
      message: "Encounter source vocabularies appear mixed across oncology and longitudinal registry extracts.",
      suggestion: "Normalize source system labels prior to model training.",
    },
  ];

  return {
    datasetId,
    generatedAt: new Date().toISOString(),
    summary: {
      errorCount: errors.length,
      warningCount: warnings.length,
      participantsSheet: true,
      observationsSheet: true,
      outcomesSheet: true,
      encountersSheet: true,
      dataDictionarySheet: false,
    },
    errors,
    warnings,
  };
}

export function buildMockJobResult(jobId: string): JobResult {
  return {
    cohortExclusions: [
      { reason: "No 365-day lookback history", count: 91, percent: 15.8 },
      { reason: "Insufficient repeated observations", count: 57, percent: 9.9 },
      { reason: "Outcome date conflicts", count: 11, percent: 1.9 },
    ],
    comparison: [
      { measure: "AUROC @ 180 days", staticModel: 0.68, trajectoryModel: 0.76, delta: 0.08 },
      { measure: "AUPRC @ 365 days", staticModel: 0.19, trajectoryModel: 0.27, delta: 0.08 },
      { measure: "Calibration slope", staticModel: 0.84, trajectoryModel: 0.93, delta: 0.09 },
    ],
    warnings: [
      "Synthetic evaluation only: metrics are illustrative placeholders and not clinically validated.",
      "Interpret trajectory lift as a demo artifact until backed by a reproducible worker pipeline.",
    ],
    report: {
      executiveSummary: `Mock research job ${jobId} suggests longitudinal trajectories may outperform static baselines in this synthetic cohort. Results are for workflow prototyping only and cannot support patient care or diagnosis.`,
      metrics: [
        { name: "Cohort retained", value: "72.4%", note: "After synthetic exclusion rules." },
        { name: "Best horizon", value: "365 days", note: "Highest mock trajectory AUROC." },
        { name: "Trajectory lift", value: "+0.08 AUROC", note: "Versus static feature baseline." },
      ],
      limitations: [
        "All inputs and outputs in this scaffold are synthetic placeholders.",
        "No calibration, fairness, subgroup, or external validation workflow is implemented here.",
        "No diagnostic or treatment recommendations are produced or implied.",
      ],
      disclaimer: RESEARCH_DISCLAIMER,
      generatedAt: new Date().toISOString(),
    },
  };
}
