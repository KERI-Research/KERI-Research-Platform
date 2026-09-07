Yes—build ORAMA as a **research-only, asynchronous ML platform**: Vercel hosts the UI and a thin orchestration API; a Hugging Face Space or dedicated Inference Endpoint performs the expensive validation, feature engineering, training, evaluation, and artefact generation. Do not run patient-level model training inside Vercel functions, and do not upload identifiable health records to a public Hub repository.

ORAMA’s core experiment should compare a static baseline against the same baseline augmented with within-person longitudinal trajectory features, using only pre-index data. The project is explicitly non-diagnostic: it should report research evidence, uncertainty, calibration and viability gates—not produce clinical decisions.[1][2]

## Target architecture

```text
Browser
  └─ Next.js / React frontend on Vercel
       ├─ Dataset upload box (CSV / Parquet / ZIP)
       ├─ Schema-mapping and validation preview
       ├─ Run configuration form
       ├─ Job-status polling / SSE
       └─ Research report + downloadable artefacts

Vercel API routes
  ├─ Authenticate researcher
  ├─ Create job ID and metadata
  ├─ Issue short-lived direct-upload URL to private storage
  ├─ Validate file metadata only
  ├─ Start remote Hugging Face job
  └─ Proxy job status / signed result downloads

Private object storage
  ├─ Raw immutable dataset upload
  ├─ Sanitised analysis input
  ├─ Job logs
  ├─ Trained model artefacts
  └─ Evaluation reports / figures / manifests

Hugging Face compute
  ├─ Preferred: private Docker Space for queued research jobs
  └─ Production / heavy workloads: dedicated Inference Endpoint
       ├─ Download one authorised job input
       ├─ Run ORAMA pipeline
       ├─ Write outputs to private storage
       └─ Return only job status and artefact URIs

Metadata database (e.g. Postgres)
  ├─ Users and RBAC
  ├─ Projects / datasets / data dictionary versions
  ├─ Jobs and configuration hashes
  ├─ Cohort counts and viability decisions
  └─ Audit trail
```

Use a **private Hugging Face repository** only for versioned code, environment configuration and non-sensitive model artefacts. Hugging Face supports private dataset repositories, but uploaded datasets remain stored and versioned on the Hub; for governed clinical data, private object storage under your institutional controls is the safer default. Hugging Face also offers managed, autoscaling infrastructure through Inference Endpoints, whereas HF Inference is a serverless inference service rather than a suitable training-job system.[1]

## Compute choice

| Need | Use | Why |
|---|---|---|
| Prototype and internal feasibility runs | Private Docker Space | Fastest route to a custom Python/FastAPI worker with persistent app logic and GPU selection |
| Long-running, expensive training | Dedicated job container / HF Space worker | Training must be asynchronous and resumable; the browser should never wait for it |
| Stable online prediction from a frozen, validated research model | Hugging Face Inference Endpoint | Managed model deployment and autoscaling; keep this separate from training |
| Small, stateless model inference | HF Inference / Inference Providers | Suitable for supported serverless models, not the ORAMA training pipeline |

For the initial build, make the remote service a **private Docker Space containing FastAPI + a worker queue**. The Vercel backend submits jobs; the Space reads the input dataset from storage and writes results back. Later, move resource-intensive training to a dedicated managed endpoint or a separate container-job platform if required.

Never put `HF_TOKEN`, object-storage credentials, or database admin credentials in browser code. Store them only as Vercel/Hugging Face server-side secrets.

## Dataset contract

The upload UI should require either:

1. A single normalised longitudinal file, preferably Parquet; or  
2. A ZIP containing `observations.parquet`, `outcomes.parquet`, `participants.parquet`, and `data_dictionary.json`.

Suggested minimum schema:

| Table | Required fields | Purpose |
|---|---|---|
| `participants` | `patient_id`, `sex_at_birth`, `birth_year` or age proxy | Demographics and cohort covariates |
| `observations` | `patient_id`, `observed_at`, `variable_code`, `value`, `unit`, `source` | Repeated blood, metabolic, anthropometric, or routine clinical measurements |
| `outcomes` | `patient_id`, `diagnosis_date`, `cancer_type`, `incident_flag` | Incident cancer endpoints and index dates |
| `encounters` | `patient_id`, `encounter_at`, `encounter_type` | Healthcare-utilisation controls |
| `data_dictionary` | variable definitions, units, mapping, provenance | Reproducible interpretation |

Validate before starting a remote job:

- `patient_id` is pseudonymised; no names, NHS numbers, addresses, emails, dates of birth, free text, or direct identifiers.
- Dates are valid and all observations used in features occur strictly before the patient’s index date.
- Units map to expected canonical units.
- There are enough historical observations per variable and patient.
- The outcome is incident cancer, not prevalent disease.
- Cases and comparison participants can be assigned valid index dates.
- Dataset version, schema version, hashes, uploader identity, and consent/governance classification are recorded.

The frontend should surface a **data-quality gate** before compute begins:

```json
{
  "status": "ready_for_analysis",
  "patients": 18420,
  "incident_cases": 612,
  "eligible_cases": 387,
  "eligible_controls": 8212,
  "median_pre_index_observations": 9,
  "missingness_summary": {},
  "excluded_reasons": {
    "insufficient_history": 225,
    "prevalent_cancer": 41,
    "invalid_dates": 7
  }
}
```

If the required history or event count is inadequate, return `NOT_EVALUABLE` rather than manufacturing unstable metrics. That follows the proposal’s viability-gate principle.[1][2]

## ORAMA model specification

### 1. Cohort construction

For each incident cancer case:

- Set `index_date = diagnosis_date`.
- Define pre-diagnostic horizons, for example: 30 days, 90 days, 180 days, 365 days, and 730 days before diagnosis.
- Exclude observations inside the active prediction gap for that horizon.
- Require a pre-specified minimum history, such as two or more measurements across a minimum time span.
- Match or weight comparison participants by eligibility time, age band, sex, calendar period, and observation opportunity.
- Assign controls an equivalent pseudo-index date.
- Treat death and loss to follow-up as censoring/competing-risk concerns, not simple “negative” labels.

This supports the actual ORAMA question: whether within-person change adds useful signal beyond static values.[1][2]

### 2. Feature layers

Create three feature sets, which lets you isolate the value of trajectories.

| Feature set | Contents | Role |
|---|---|---|
| `static_only` | Last valid pre-index values, demographics, baseline comorbidity and observation controls | Mandatory benchmark |
| `trajectory_only` | Change, slope, deviation, variability and measurement-pattern features | Tests longitudinal signal directly |
| `static_plus_trajectory` | Static features plus trajectory features | Primary ORAMA candidate model |

For each patient-variable pair, calculate only from eligible pre-index observations:

- Last measurement and time since last measurement.
- First eligible measurement.
- Absolute change: \(x_{last} - x_{first}\).
- Relative change: \(\frac{x_{last} - x_{first}}{|x_{first}| + \epsilon}\).
- Ordinary least-squares slope per 30, 90, and 365 days.
- Robust Theil–Sen slope, where feasible.
- Recent versus historic mean difference.
- Personal z-score: deviation of latest observation from that patient’s historical mean.
- Maximum deviation from historic baseline.
- Coefficient of variation, standard deviation, range, and number of observations.
- Direction consistency: proportion of consecutive changes in the same direction.
- Acceleration: difference between recent and older slopes.
- Missingness indicator, observation frequency, time since first and last observation.
- Healthcare-utilisation covariates: encounter count and measurement density.

Use a feature manifest so every generated value is traceable:

```json
{
  "feature": "haemoglobin_slope_365d",
  "source_variable": "haemoglobin",
  "unit": "g/L",
  "window_days": 365,
  "method": "theil_sen",
  "pre_index_only": true,
  "minimum_observations": 2
}
```

### 3. Modelling stack

Begin with interpretable models and add complexity only if it delivers stable, calibrated incremental value.

```text
M0: Demographic / utilisation reference model
M1: Static-only elastic-net logistic regression
M2: Static + trajectory elastic-net logistic regression
M3: Static-only gradient-boosted trees
M4: Static + trajectory gradient-boosted trees
M5: Optional survival model:
    time-dependent Cox model or discrete-time survival model
```

Recommended first implementation:

- **Elastic-net logistic regression** for transparency and coefficient stability.
- **XGBoost or LightGBM** for non-linear interactions and missing-value handling.
- **Isotonic regression** or Platt scaling for calibration, fitted only using development/validation partitions.
- **SHAP** for the boosted model and coefficients / bootstrap confidence intervals for the elastic-net model.
- Bootstrap resampling, subgroup checks, and temporal validation for stability.

Avoid deep longitudinal architectures initially. A transformer/LSTM may look sophisticated but makes it harder to prove that ORAMA’s core effect comes from interpretable personal trajectories rather than leakage, irregular sampling, or healthcare utilisation.

### 4. Split and leakage policy

This is non-negotiable:

```text
1. Split by patient before any preprocessing.
2. Keep test patients completely unseen.
3. Fit imputation, unit harmonisation rules, scaling, encoding,
   feature selection, and calibration on development data only.
4. Build each patient's features using only observations before
   the defined pre-index cutoff.
5. Exclude outcome-derived, treatment-related and post-index fields.
6. Do not allow records from one participant in multiple partitions.
7. Freeze the test set until the pipeline and analysis plan are frozen.
```

The ORAMA proposal explicitly identifies patient isolation, pre-index-only features, train-only preprocessing, and an untouched held-out test set as safeguards against misleading performance claims.[1][2]

### 5. Evaluation and decision rule

Return all performance measures with confidence intervals, but make **incremental utility** the primary outcome.

```text
Primary comparison:
  Δ performance = M2/M4 (static + trajectories) − M1/M3 (static only)

A positive feasibility result requires:
  - Incremental value across more than one resample or time split
  - Adequate calibration
  - Stable influential features
  - No obvious utilisation or leakage explanation
  - Biologically and clinically plausible patterns
  - Sufficient event counts per endpoint and horizon
```

Report:

- AUROC and AUPRC.
- Sensitivity at fixed specificity thresholds.
- Specificity at fixed sensitivity thresholds.
- Brier score.
- Calibration intercept, slope, calibration curve, and expected calibration error.
- Decision-curve analysis only as exploratory research evidence.
- Confidence intervals from patient-level bootstrap resampling.
- Subgroup metrics only where event counts allow.
- Per-cancer, pan-cancer, and time-horizon eligibility counts.
- Feature stability, directionality and SHAP summaries.
- Explicit `NOT_EVALUABLE`, `NO_GO`, `REDIRECT`, or `GO_FOR_EXTERNAL_VALIDATION` outcome.

A “GO” must not mean clinically deployable. It means the feasibility signal warrants independently governed external validation, which is consistent with the study boundary in your materials.[1][2]

## API contract

### Create a job

`POST /api/orama/jobs`

```json
{
  "projectId": "orama-uk-feasibility-001",
  "datasetId": "ds_01J...",
  "outcome": {
    "type": "pan_cancer_incident",
    "horizonsDays": [30, 90, 180, 365, 730]
  },
  "eligibility": {
    "minimumHistoryDays": 365,
    "minimumObservationsPerVariable": 2,
    "excludePreIndexDays": 30
  },
  "models": [
    "elastic_net_static",
    "elastic_net_static_trajectory",
    "xgboost_static",
    "xgboost_static_trajectory"
  ],
  "split": {
    "strategy": "patient_grouped_temporal_holdout",
    "testFraction": 0.2,
    "randomSeed": 42
  }
}
```

Vercel should respond immediately:

```json
{
  "jobId": "job_01J...",
  "status": "QUEUED",
  "statusUrl": "/api/orama/jobs/job_01J..."
}
```

### Submit to Hugging Face

`POST /internal/jobs/run` on the private worker:

```json
{
  "jobId": "job_01J...",
  "datasetReadUrl": "short-lived-signed-url",
  "resultWritePrefix": "private://orama-results/job_01J/",
  "configUri": "private://orama-config/job_01J.json",
  "callbackUrl": "https://your-app.vercel.app/api/orama/jobs/job_01J/callback"
}
```

The worker should not receive permanent storage credentials. Use a narrowly scoped, short-lived read URL for one input object and a separate, constrained result-upload mechanism.

### Worker result

```json
{
  "jobId": "job_01J...",
  "status": "COMPLETED",
  "decision": "NO_GO",
  "decisionReasons": [
    "Trajectory models did not show stable incremental value",
    "Cancer-specific endpoint underpowered at 365-day horizon"
  ],
  "metrics": {
    "staticAuprc": 0.112,
    "trajectoryAuprc": 0.115,
    "deltaAuprc": 0.003,
    "calibrationSlope": 0.93
  },
  "artefacts": {
    "report": "signed-download-url",
    "metrics": "signed-download-url",
    "featureManifest": "signed-download-url",
    "modelCard": "signed-download-url"
  }
}
```

## Vercel implementation

Your Next.js app needs these server routes:

```text
app/api/orama/uploads/initiate/route.ts
app/api/orama/uploads/complete/route.ts
app/api/orama/datasets/[datasetId]/validate/route.ts
app/api/orama/jobs/route.ts
app/api/orama/jobs/[jobId]/route.ts
app/api/orama/jobs/[jobId]/callback/route.ts
app/api/orama/results/[jobId]/download/route.ts
```

Use direct-to-storage upload from the browser:

```text
Browser → request upload session from Vercel
Browser → upload direct to private storage using signed URL
Browser → notify Vercel upload completed
Vercel → run metadata/schema validation
Vercel → create job and trigger HF worker
HF worker → process remotely and save artefacts
Browser → polls Vercel for job state
```

This prevents Vercel request limits from becoming your dataset-transfer layer and avoids routing sensitive files through application memory.

UI states:

```text
Upload → Mapping → Validation → Configure analysis →
Queued → Remote processing → Evaluation complete → Report
```

The result page should show:

- Cohort flow and exclusions.
- Dataset provenance and configuration hash.
- Static vs longitudinal comparison.
- Calibration and discrimination with confidence intervals.
- Feature direction, timing and stability.
- Warnings for sparse measurements, endpoint underpowering and potential utilisation bias.
- A strong “Research use only — non-diagnostic” banner.

## Hugging Face worker layout

```text
orama-worker/
├─ Dockerfile
├─ requirements.txt
├─ app/
│  ├─ main.py                 # FastAPI endpoints
│  ├─ worker.py               # job lifecycle
│  ├─ config.py
│  ├─ security.py
│  ├─ schemas/
│  │  ├─ input.py
│  │  └─ output.py
│  ├─ pipeline/
│  │  ├─ ingest.py
│  │  ├─ validation.py
│  │  ├─ cohort.py
│  │  ├─ index_dates.py
│  │  ├─ trajectories.py
│  │  ├─ splits.py
│  │  ├─ models.py
│  │  ├─ calibration.py
│  │  ├─ evaluate.py
│  │  └─ reporting.py
│  └─ templates/
│     ├─ model_card.md.j2
│     └─ report.html.j2
├─ tests/
│  ├─ test_no_post_index_leakage.py
│  ├─ test_patient_partition_isolation.py
│  ├─ test_train_only_preprocessing.py
│  └─ test_feature_timestamps.py
└─ README.md
```

The central safety test should be explicit:

```python
assert features["max_source_timestamp"].lt(features["index_date"] - prediction_gap).all()
assert train_patient_ids.isdisjoint(test_patient_ids)
assert preprocessing.fit_partition == "development_only"
```

## Governance essentials

Because ORAMA processes health data, treat this as a governed research environment—not a standard web-app upload feature.

- Use pseudonymised research data only; minimise variables and remove direct identifiers before upload.
- Obtain institutional approval, data-sharing agreements, DPIA review and an approved lawful basis before processing real UK health data.
- Use role-based access control, MFA/SSO where available, immutable audit logs, encryption in transit and at rest, retention limits and deletion workflows.
- Do not print row-level data, patient identifiers, raw values, signed URLs or secrets to Vercel/Hugging Face logs.
- Keep raw data separate from code and models; keep all output artefacts access-controlled.
- Build a data-deletion job that removes raw upload, derived data, job logs and artefacts according to your retention policy.
- Do not expose individual predictions or “cancer risk” output to patients, clinicians or public users.

Hugging Face supports gated datasets to control access requests, but gated access is granted to individual accounts and is not a substitute for your organisation’s governance controls around sensitive health data.[1]

## Build order

1. Build the Next.js upload/mapping/validation UI using synthetic Synthea-style data only.
2. Implement the private storage and job metadata layer.
3. Create the Hugging Face Docker worker with schema validation and cohort reporting first.
4. Implement the static-only baseline before any trajectory model.
5. Add trajectory features and the locked static-vs-longitudinal comparison.
6. Add grouped patient splits, pre-index enforcement, train-only preprocessing and unit tests.
7. Add calibration, bootstrap intervals, feature stability and report generation.
8. Run end-to-end only with synthetic or explicitly approved de-identified data.
9. Freeze the analysis configuration before opening the held-out test partition.
10. Treat the output as a feasibility report requiring biological, clinical and independent external validation—not a deployed diagnostic model.

Sources
[1] ORAMA-Proposal-Presentation-Draft.pptx https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/772847312/71667a4e-fda8-4842-b295-55858201171f/ORAMA-Proposal-Presentation-Draft.pptx
[2] ORAMA-Proposal-Presenter-Notes.docx https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/772847312/6653a1dd-42ff-4c71-b96e-e55e6f8ddc4f/ORAMA-Proposal-Presenter-Notes.docx
[3] EDD-Primer-Research-Proposal-Template_Jan2021-2.docx https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/772847312/17c9b61d-7b90-4b70-bbd1-3895f59b0171/EDD-Primer-Research-Proposal-Template_Jan2021-2.docx
