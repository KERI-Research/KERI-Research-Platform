export const APP_NAME = "ORAMA Research Platform";
export const RESEARCH_DISCLAIMER =
  "Research use only — non-diagnostic. Synthetic data only. Not for clinical decision-making.";
export const SCAFFOLD_NOTICE =
  "Only synthetic or explicitly approved pseudonymised research data may enter this private workflow. It is not a clinical system.";

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
