# ORAMA Worker

This worker is a Python 3.11 FastAPI service for a **synthetic-only longitudinal research pipeline**. It accepts an inline test fixture or a private R2 ZIP/CSV/Parquet object, runs an asynchronous feasibility workflow, and writes research-only report artifacts to a job-scoped private prefix.

## Important disclaimer

**Research use only. Synthetic data only. Non-diagnostic. Not clinically validated.**

This scaffold is intended for internal experimentation on synthetic longitudinal cancer-risk modelling workflows. It must not be used to make clinical, treatment, screening, triage, or patient-care decisions.

## Local development

From `apps/worker`:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export ORAMA_RUNTIME_ENV=local
uvicorn app.main:app --reload --port 7860
```

Health check:

```bash
curl http://127.0.0.1:7860/health
```

## Running with Docker

Build and run:

```bash
docker build -t orama-worker .
docker run --rm -p 7860:7860 \
  -e ORAMA_RUNTIME_ENV=local \
  -e ORAMA_WORKER_SHARED_SECRET=changeme-local-dev-secret \
  orama-worker
```

The container listens on port `7860`, matching the default port for Hugging Face Docker Spaces.

## Concurrent job capacity

The worker runs at most two jobs at once (`ORAMA_MAX_CONCURRENT_JOBS=2`). Extra
jobs remain `QUEUED` until a processing slot is available. The Docker runtime
limits OpenMP, OpenBLAS, MKL, NumExpr, and XGBoost to one native compute thread
per job, which keeps two active jobs within the Space's two vCPU allocation.
CPU affinity is not used because container CPU numbering is not a stable worker
contract.

## Private Hugging Face Docker Space deployment

This directory is structured for deployment as a **private Hugging Face Docker Space**:

- `Dockerfile` uses `python:3.11-slim`
- the service binds to `0.0.0.0:7860`
- dependencies are installed from `requirements.txt`
- the FastAPI app entrypoint is `app.main:app`

For private Space configuration, set the shared secret environment variable in Space secrets.

## Internal shared-secret authentication

Internal job endpoints require the header:

- `X-Orama-Worker-Secret: <secret>`

The service checks this value against the environment variable:

- `ORAMA_WORKER_SHARED_SECRET`

If the environment variable is missing, the app can fall back to the placeholder local-development default only when `ORAMA_RUNTIME_ENV` is explicitly set to a local/dev value:

- `changeme-local-dev-secret`

**That fallback is for local development only and is not appropriate for production or any internet-exposed deployment.**

## Pipeline design: horizon-specific prediction anchors

To avoid target/horizon leakage, the worker builds a **separate analysis frame per
horizon** (default `[30, 90, 180, 365, 730]` days) rather than a single shared index date:

- **Cases** (patients with a recorded outcome) anchor at
  `prediction_anchor_date = outcome_date - horizon_days`, so the outcome always falls
  exactly at the end of that horizon's window — never at day 0.
- **Controls** (patients without a recorded outcome) anchor at an eligible pseudo
  reference/follow-up date; any control whose outcome would fall inside a given horizon
  window is excluded from that horizon rather than mislabeled.
- All static, encounter, and trajectory features are derived only from data strictly
  before `feature_cutoff = prediction_anchor_date - prediction_gap_days`.
- Labels (`M0`–`M4` targets) are computed per horizon: positive only if the outcome occurs
  strictly after the anchor and within that horizon; models never see outcome dates,
  cohort labels, incident flags, or other outcome-derived columns as inputs.

Unit tests in `tests/test_horizon_labels.py` and `tests/test_no_leakage.py` assert this
boundary, horizon-specific labelling, outcome-free controls, and the absence of forbidden
columns in the model feature matrices.

## Endpoints

- `GET /health` — unauthenticated health check
- `POST /internal/storage/presign-upload` — authenticated one-object R2 PUT URL generation
- `POST /internal/datasets/validate` — authenticated private-object contract validation
- `POST /internal/jobs/run` — authenticated asynchronous locked research job submission
- `GET /internal/jobs/{job_id}` — authenticated job lookup and result retrieval
- `POST /internal/storage/presign-download` — authenticated signed result-artifact download URL generation
- `DELETE /internal/storage/uploads/{upload_id}` — authenticated raw-upload deletion
- `DELETE /internal/storage/jobs/{job_id}/artifacts` — authenticated job artifact deletion

The worker accepts an object only under `uploads/` and writes artifacts only under `results/<job-id>/`.
It rejects ambiguous data sources, direct identifiers, leaky variables, invalid unit mappings, and a configuration hash that does not match the immutable job configuration.

## Packaging ordinary-incidence source data

Use the packer to convert a completed, explicitly synthetic canonical
ordinary-incidence bundle into one endpoint-specific ORAMA ZIP. It accepts only
`simulation_only: true` source manifests, excludes augmented source events,
derives each control's reference date from its latest safe native event, and
checks the generated archive through the worker ingestion validator before it
is written.

From `apps/worker`:

```bash
python -m app.importers.ordinary_incidence \
  ../../res/ordinary_incidence/ordinary_incidence-5000-20260831-e834cfb774c5 \
  --endpoint cancer \
  --output ../../res/ordinary_incidence/ordinary-incidence-5000-cancer-orama.zip
```

Use `--endpoint diabetes` to package that endpoint instead. The source
`conditions.parquet` table is intentionally not mapped until a numeric,
pre-index condition-feature policy is defined.
