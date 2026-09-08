# ORAMA Project Todo

## Step 1

- Status: Complete
- Type: Web
- Work: Important

### Scope

Create the front-end synthetic research scaffold that demonstrates dataset upload, validation, analysis configuration, job display, and report output without using patient data.

### Features

- Upload UI and accepted file hints for CSV / Parquet / ZIP input
- Schema mapping and validation preview screens
- Configuration form for horizons, history, and prediction gaps
- Job queue and status screens
- Non-diagnostic banner and research-only messaging

### Payloads

- In: browser payload for upload metadata such as `{ filename, contentType, size }`
- In: job creation payload such as `{ datasetId, config }`
- Out: job response such as `{ jobId, status, createdAt }`
- Out: validation payload such as `{ datasetId, generatedAt, summary, errors, warnings }`

### Workspace

- [apps/web/src/app/upload/page.tsx](apps/web/src/app/upload/page.tsx)
- [apps/web/src/app/validation/page.tsx](apps/web/src/app/validation/page.tsx)
- [apps/web/src/app/analysis/page.tsx](apps/web/src/app/analysis/page.tsx)
- [apps/web/src/app/jobs/page.tsx](apps/web/src/app/jobs/page.tsx)
- [apps/web/src/app/report/[jobId]/page.tsx](apps/web/src/app/report/[jobId]/page.tsx)
- [apps/web/src/lib/orama-mocks.ts](apps/web/src/lib/orama-mocks.ts)
- [apps/web/src/components/ResearchBanner.tsx](apps/web/src/components/ResearchBanner.tsx)

---

## Step 2

- Status: Complete
- Type: Web
- Work: Urgent

### Scope

Complete the Vercel-side storage and metadata flow so uploads can be initiated, finalized, and connected to downstream job execution.

### Features

- Direct-upload session generation
- Upload completion capture with dataset persistence
- Dataset metadata validation and provenance tracking
- Linkage from dataset to analysis jobs

### Payloads

- In: upload initiation `{ filename, contentType?, size }`
- Out: upload initiation response `{ uploadId, uploadUrl, expiresAt }`
- In: upload completion `{ uploadId, metadata }`
- Out: dataset creation response `{ datasetId, recordedAt }`
- Out: validation response for stored metadata, including summary/errors/warnings

### Workspace

- [apps/web/src/app/api/orama/uploads/initiate/route.ts](apps/web/src/app/api/orama/uploads/initiate/route.ts)
- [apps/web/src/app/api/orama/uploads/complete/route.ts](apps/web/src/app/api/orama/uploads/complete/route.ts)
- [apps/web/src/app/api/orama/datasets/[datasetId]/validate/route.ts](apps/web/src/app/api/orama/datasets/[datasetId]/validate/route.ts)
- [apps/web/src/lib/orama-store.ts](apps/web/src/lib/orama-store.ts)
- [apps/web/src/lib/schema.ts](apps/web/src/lib/schema.ts)
- [apps/web/src/types/orama.ts](apps/web/src/types/orama.ts)

Notes:

- Completed: upload sessions are persisted, the worker issues a short-lived R2 direct-upload URL, completion confirms object existence, dataset metadata/provenance is persisted, and audit events are recorded.
- Completed: private ZIP/CSV/Parquet uploads are parsed into the worker contract and validated before a job can be created.

---

## Step 3

- Status: Complete
- Type: Worker
- Work: Urgent

### Scope

Build the private FastAPI worker that accepts a job request, validates the synthetic dataset contract, runs the analysis pipeline, and returns a realistic status payload.

### Features

- Health endpoint and auth checking
- Worker job runner endpoint
- In-memory job tracking
- Schema validation and pipeline execution
- Feasibility classification and report payload generation

### Payloads

- In: worker run request such as `{ job_id, dataset, analysis_config }`
- Out: job status response with fields like `{ status, message, result?, error? }`
- Out: synthetic report payload and markdown output

### Workspace

- [apps/worker/app/main.py](apps/worker/app/main.py)
- [apps/worker/app/security.py](apps/worker/app/security.py)
- [apps/worker/app/store.py](apps/worker/app/store.py)
- [apps/worker/app/schemas.py](apps/worker/app/schemas.py)
- [apps/worker/app/pipeline/validation.py](apps/worker/app/pipeline/validation.py)
- [apps/worker/app/pipeline/ingest.py](apps/worker/app/pipeline/ingest.py)
- [apps/worker/app/pipeline/models.py](apps/worker/app/pipeline/models.py)
- [apps/worker/app/pipeline/evaluate.py](apps/worker/app/pipeline/evaluate.py)
- [apps/worker/app/pipeline/reporting.py](apps/worker/app/pipeline/reporting.py)

Notes:

- This worker is implemented and tested for the synthetic research-only path.
- The remaining work is to scale it from synthetic in-memory execution toward real storage-driven job intake and output artifacts.

---

## Step 4

- Status: Complete
- Type: Model
- Work: Important

### Scope

Implement the static-only baseline as the first required modelling layer before trajectory-based improvements are introduced.

### Features

- Cohort creation and event definition
- Pre-index feature extraction for static features
- Non-trajectory baseline model training
- Comparison against a simple reference model

### Payloads

- In: participant, outcome, observation, encounter, data dictionary tables
- Out: per-horizon model metrics and feasibility summary
- Out: feature manifest for the static feature set

### Workspace

- [apps/worker/app/pipeline/cohort.py](apps/worker/app/pipeline/cohort.py)
- [apps/worker/app/pipeline/index_dates.py](apps/worker/app/pipeline/index_dates.py)
- [apps/worker/app/pipeline/static_features.py](apps/worker/app/pipeline/static_features.py)
- [apps/worker/app/pipeline/models.py](apps/worker/app/pipeline/models.py)
- [apps/worker/tests/test_viability_gates.py](apps/worker/tests/test_viability_gates.py)
- [apps/worker/tests/test_xgboost_models.py](apps/worker/tests/test_xgboost_models.py)

Notes:

- Completed: M0 provides the demographic/utilisation reference, M1 provides the static-only elastic-net baseline, features are restricted to pre-cutoff non-outcome fields, and the baseline is evaluated per horizon.

---

## Step 5

- Status: Complete
- Type: Model
- Work: Urgent

### Scope

Add the longitudinal feature generation and the locked comparison between static-only and static-plus-trajectory models.

### Features

- Compute within-person change, slope, variability, and timing features
- Build trajectory-only and static-plus-trajectory feature sets
- Compare static vs longitudinal performance
- Generate feature manifest with metadata for each derived variable

### Payloads

- In: patient history, repeated observations, and time-window definitions
- Out: feature matrix with names like `haemoglobin_slope_365d`, `sbp_recent_vs_historic_diff`
- Out: evaluation records for static-only, trajectory-only, and combined models

### Workspace

- [apps/worker/app/pipeline/trajectories.py](apps/worker/app/pipeline/trajectories.py)
- [apps/worker/app/pipeline/models.py](apps/worker/app/pipeline/models.py)
- [apps/worker/app/pipeline/evaluate.py](apps/worker/app/pipeline/evaluate.py)
- [apps/worker/app/pipeline/reporting.py](apps/worker/app/pipeline/reporting.py)

Notes:

- Completed: pre-cutoff change, slope, variability, timing, and 30/90/365-day windowed slope features are implemented.
- Completed: static-only, trajectory-only (M5), and static-plus-trajectory model suites are evaluated with per-derived-feature manifests.

---

## Step 6

- Status: Complete
- Type: Worker
- Work: Urgent

### Scope

Ensure no leakage, train-only preprocessing, and patient-level partition isolation for the experiment.

### Features

- Split by patient before fitting
- Keep test patients unseen until the final analysis lock
- Enforce pre-index-only feature extraction
- Prevent outcome-derived or post-index leakage in feature generation
- Enforce development-only preprocessing rules

### Payloads

- In: patient-level group assignments and feature generation windows
- Out: disjoint train/test IDs
- Out: validation results such as `assert train_patient_ids.isdisjoint(test_patient_ids)`

### Workspace

- [apps/worker/app/pipeline/splits.py](apps/worker/app/pipeline/splits.py)
- [apps/worker/app/pipeline/validation.py](apps/worker/app/pipeline/validation.py)
- [apps/worker/tests/test_no_leakage.py](apps/worker/tests/test_no_leakage.py)
- [apps/worker/tests/test_preprocessing_train_only.py](apps/worker/tests/test_preprocessing_train_only.py)
- [apps/worker/tests/test_patient_split_isolation.py](apps/worker/tests/test_patient_split_isolation.py)

Notes:

- Completed: patient-level split isolation, pre-cutoff feature enforcement, forbidden-variable rejection, train-only preprocessing, and an analysis-lock gate before held-out evaluation are implemented and covered by tests.

---

## Step 7

- Status: Complete
- Type: Model
- Work: Important

### Scope

Add calibration, confidence intervals, and stability reporting to move from raw model performance to research-grade evidence.

### Features

- Calibration intercept and slope checks
- Bootstrap or resample confidence intervals
- Feature stability and subgroup checks
- Report generation with metrics and caveats

### Payloads

- In: summary metrics by horizon and model
- Out: calibration output, confidence intervals, and stability summaries
- Out: final research report payload with executive summary, metrics, limitations, and disclaimer

### Workspace

- [apps/worker/app/pipeline/calibration.py](apps/worker/app/pipeline/calibration.py)
- [apps/worker/app/pipeline/evaluate.py](apps/worker/app/pipeline/evaluate.py)
- [apps/worker/app/pipeline/reporting.py](apps/worker/app/pipeline/reporting.py)
- [apps/worker/tests/test_reporting_templates.py](apps/worker/tests/test_reporting_templates.py)

Notes:

- Completed: calibration intercept/slope, deterministic patient-level bootstrap intervals, held-out subgroup metrics, bootstrap coefficient-direction stability, and research reports are implemented.
- Completed: the feasibility decision rule requires discrimination, incremental trajectory value, calibration, stability, and subgroup gates before a positive conclusion.

---

## Step 8

- Status: Complete
- Type: Web
- Work: Important

### Scope

Run the complete end-to-end synthetic job flow: upload → validation → job → worker → report output.

### Features

- Full UI journey for dataset intake and analysis
- Browser polling of job status
- Download of generated research outputs
- Result page with static vs longitudinal comparison and disclosures

### Payloads

- In: upload session and dataset metadata
- In: job creation request with analysis config
- Out: job status updates with remote compute progress
- Out: report and artifact download metadata

### Workspace

- [apps/web/src/app/api/orama/jobs/route.ts](apps/web/src/app/api/orama/jobs/route.ts)
- [apps/web/src/app/api/orama/jobs/[jobId]/route.ts](apps/web/src/app/api/orama/jobs/[jobId]/route.ts)
- [apps/web/src/app/api/orama/jobs/[jobId]/callback/route.ts](apps/web/src/app/api/orama/jobs/[jobId]/callback/route.ts)
- [apps/web/src/app/api/orama/results/[jobId]/download/route.ts](apps/web/src/app/api/orama/results/[jobId]/download/route.ts)
- [apps/web/src/app/jobs/[jobId]/page.tsx](apps/web/src/app/jobs/[jobId]/page.tsx)
- [apps/web/src/app/report/[jobId]/page.tsx](apps/web/src/app/report/[jobId]/page.tsx)

Notes:

- Completed: browser intake uses direct upload, persisted datasets drive private-object validation and job creation, jobs dispatch asynchronously to the worker, and browser polling/callbacks persist worker state.
- Completed: generated JSON, Markdown, HTML, and model-card artifacts are written to private job-scoped storage and downloaded with short-lived URLs.

---

## Step 9

- Status: Complete
- Type: Web
- Work: Important

### Scope

Add governance controls, retention logic, and access restrictions that match the research-only sensitivity of health data.

### Features

- Research-only disclaimers and protected output pages
- Audit trail support in the data model
- Retention/deletion policy scaffolding
- Access-aware handling of raw uploads and outputs

### Payloads

- In: audit records such as `{ eventType, entityId, actorId, payload }`
- Out: immutable event logs and deletion policy metadata

### Workspace

- [apps/web/src/lib/schema.ts](apps/web/src/lib/schema.ts)
- [apps/worker/app/security.py](apps/worker/app/security.py)
- [apps/web/src/app/api/orama/jobs/[jobId]/callback/route.ts](apps/web/src/app/api/orama/jobs/[jobId]/callback/route.ts)
- [docs/plan.md](docs/plan.md)

Notes:

- Completed: research-only messaging, protected browser APIs, secure research-session cookies, authenticated worker endpoints, server-side secret handling, and upload lifecycle audit events are implemented.
- Completed: audit rows are append-only in Neon; raw uploads/results have explicit retention timestamps, protected deletion endpoints, and a daily Vercel retention schedule.

---

## Step 10

- Status: Complete
- Type: Model
- Work: Minor

### Scope

Freeze the analysis configuration before the held-out test set is evaluated and treat the output as a feasibility report, not a clinical model.

### Features

- Final model lock before test exposure
- Explicit NO_GO / REDIRECT / NOT_EVALUABLE decision handling
- Research-only interpretation guidelines
- Mandatory external validation recommendation

### Payloads

- In: locked analysis config with fixed horizons, sampling strategy, and preprocessing rules
- Out: feasibility decision payload with `status`, `decision`, `decisionReasons`, `metrics`, and `artefacts`

### Workspace

- [docs/plan.md](docs/plan.md)
- [apps/worker/app/pipeline/evaluate.py](apps/worker/app/pipeline/evaluate.py)
- [apps/worker/app/pipeline/reporting.py](apps/worker/app/pipeline/reporting.py)
- [apps/worker/app/main.py](apps/worker/app/main.py)

Notes:

- Completed: the worker rejects unlocked analysis configurations before held-out evaluation, validates the canonical configuration hash, and produces explicit `GO_FOR_EXTERNAL_VALIDATION`, `NO_GO`, `REDIRECT`, or `NOT_EVALUABLE` outcomes.
- Completed: positive outcomes explicitly require independently governed external validation and never imply clinical deployment.

---

## Overall status summary

- Web scaffold: Complete
- Worker pipeline: Complete for synthetic prototype
- Storage and job orchestration: Complete
- Real longitudinal modelling: Complete for the planned static, trajectory-only, and combined synthetic feasibility comparison
- Validation gates and leakage controls: Complete
- Governance controls and retention implementation: Complete
- Final freeze and external validation gate: Complete

## Production deployment status

- Completed: the verified worker source is published to the private `JayNightmare/orama-worker` Space using the write-enabled `ORAMA_WORKER_HF_TOKEN`. The Hugging Face bearer gate and ORAMA shared-secret gate both pass an authenticated internal request.
- Completed: Cloudflare R2 CORS is verified for `https://orama.cerebrallab.org` direct uploads; no further CORS action is required.
- Completed: Vercel deployment `dpl_7BkM2AbyhmJLQU6r1Cbtbzk837uW` is ready and aliased to `https://orama.cerebrallab.org`. Its production environment targets the standard private `hf.space` worker host and includes the required access, retention, worker, database, and callback configuration.
- Completed: production access checks confirm an unauthenticated page redirect, unauthenticated API rejection, and successful authenticated jobs retrieval.
- Completed: the Space R2 credential pair was corrected after its access-key ID was found to be malformed. The subsequent worker-issued signed R2 write and delete probe returned `200` for both operations.
- Completed: a disposable 20-participant synthetic ZIP completed the production upload, R2 write, metadata finalization, worker validation, locked job dispatch, terminal `NOT_EVALUABLE` feasibility result, private report download, and authorized dataset/artifact cleanup flow.
- Operational cleanup decision: one failed pre-fix signed-upload attempt left an unfinalized synthetic `uploads` metadata row with no R2 object or dataset. Its removal is documented in `docs/questions.md` for explicit confirmation because it requires a destructive Neon operation.

The implementation roadmap and production validation are complete. No clinical or patient-data workflow was introduced by the operational checks.
