# orama-research-platform

> **Research use only — non-diagnostic.** ORAMA is a scaffold for exploring longitudinal,
> trajectory-based cancer-risk **research** modelling on **synthetic data only**. It is not a
> diagnostic, clinical decision-support, or patient-facing risk tool, and nothing in this
> repository should be used to make clinical, treatment, screening, or triage decisions.

This monorepo contains two deployable apps:

| App | Path | Stack | Deployment target |
| --- | --- | --- | --- |
| Web dashboard | [`apps/web`](apps/web) | Next.js (App Router) + TypeScript + Tailwind CSS | Vercel |
| Research worker | [`apps/worker`](apps/worker) | Python 3.11 + FastAPI | Private Hugging Face Docker Space |

## What this scaffold demonstrates

- A private synthetic job journey in the web dashboard: direct R2 upload → schema
  validation → frozen analysis configuration → worker status polling → artifact-backed research report.
- A functional worker pipeline that ingests private ZIP/CSV/Parquet contract uploads or inline test fixtures,
  builds trajectory features with strict pre-index-date cutoffs, fits a six-model comparison
  (M0–M5, static, trajectory-only, and combined), and produces a conservative
  GO_FOR_EXTERNAL_VALIDATION/NO_GO/REDIRECT/NOT_EVALUABLE research conclusion plus stored reports.
- Unit tests proving core safeguards: no post-index-date leakage into trajectory features,
  patient-level train/test isolation (no participant appears in both splits), preprocessing
  fit only on training folds, rejection of invalid/leaky schemas, and viability gating when
  data is insufficient.

The web app persists upload, dataset, job, audit, retention, and result metadata in Postgres.
Raw uploads and generated reports remain in private R2 storage; Vercel only requests narrowly scoped
URLs from the authenticated worker. Deployment secrets and storage credentials are server-only.

## Repository layout

```text
apps/
  web/     Next.js dashboard + private App Router orchestration API (see apps/web/README.md)
  worker/  FastAPI research pipeline and R2 access boundary (see apps/worker/README.md)
```

## Local development

### Web dashboard

```bash
npm install       # installs workspace dependencies (npm workspaces, root of repo)
npm run dev:web   # or: npm run dev --workspace=apps/web
```

Open `http://localhost:3000`. See [`apps/web/README.md`](apps/web/README.md) for details.

### Worker

```bash
cd apps/worker
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ORAMA_RUNTIME_ENV=local
uvicorn app.main:app --reload --port 7860
```

Or via Docker:

```bash
cd apps/worker
docker build -t orama-worker .
docker run --rm -p 7860:7860 -e ORAMA_RUNTIME_ENV=local -e ORAMA_WORKER_SHARED_SECRET=changeme-local-dev-secret orama-worker
```

Run the worker test suite:

```bash
cd apps/worker
pytest
```

See [`apps/worker/README.md`](apps/worker/README.md) for endpoint and pipeline details.

## Environment variables

All secrets are placeholders in this scaffold. Never commit real values.

**`apps/web/.env.example`** (copy to `.env.local`; only `NEXT_PUBLIC_*` is exposed to the
browser, every `ORAMA_*` value must stay server-side):

| Variable | Purpose |
| --- | --- |
| `ORAMA_DATABASE_URL` | Neon/Postgres URL for dataset, job, audit, and retention metadata |
| `ORAMA_DATABASE_URL_UNPOOLED` | Direct Neon URL used only by Drizzle Kit migrations |
| `ORAMA_WORKER_URL` | Base URL of the deployed worker (called only from server-side route handlers) |
| `ORAMA_WORKER_SHARED_SECRET` | Shared secret sent to the worker's internal endpoints |
| `ORAMA_APP_URL` | Canonical public ORAMA origin used to construct callback URLs |
| `ORAMA_RESEARCH_ACCESS_TOKEN` | Production researcher session token; never expose as `NEXT_PUBLIC_*` |
| `ORAMA_RESEARCH_ACTOR_ID` | Optional service-side audit actor label |
| `ORAMA_RETENTION_DAYS` | Dataset and artifact retention period; defaults to 30 days |
| `ORAMA_RETENTION_CRON_SECRET` or `CRON_SECRET` | Authorization for `POST /api/orama/retention/run` |
| `NEXT_PUBLIC_APP_NAME` | Client-visible application name |

**Worker environment variables:**

| Variable | Purpose |
| --- | --- |
| `ORAMA_WORKER_SHARED_SECRET` | Expected value of the `X-Orama-Worker-Secret` header on internal endpoints |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | R2 credentials held only by the private worker |
| `ORAMA_OBJECT_STORAGE_BUCKET` / `ORAMA_OBJECT_STORAGE_ENDPOINT` | Private R2 bucket configuration |
| `ORAMA_VERCEL_URL` | Exact Vercel production origin permitted for worker callbacks |
| `ORAMA_RUNTIME_ENV` | Set to `local`/`dev`/`test` to permit the placeholder shared secret for local development only |

## Deployment topology

1. **Worker → private Hugging Face Docker Space.** Deploy `apps/worker`, configure the R2 and
  callback secrets, and expose only the authenticated internal endpoints behind the custom worker origin.
2. **Web → Vercel project rooted at `apps/web`.** Configure the database, worker URL, shared secret,
  access token, and retention cron secret. Apply the Drizzle migrations before accepting uploads.
3. **R2 CORS.** Allow only `https://orama.cerebrallab.org` to make `PUT` requests with the `Content-Type`
  header. Do not configure wildcard origins or browser storage credentials.

## Governance and safety controls

- **Synthetic data only.** No real patient data, clinical datasets, or external health
  records are included or referenced anywhere in this repository.
- **Non-diagnostic by design.** The web app displays a persistent "research use only —
  non-diagnostic" banner; the worker's reports carry the same disclaimer.
- **No direct identifiers.** The upload parser rejects direct-identifier columns, email-form patient IDs,
  valid NHS-number patterns, unknown patient references, undocumented variables, and unit conflicts.
- **Leakage safeguards.** Each horizon builds its own analysis frame with a distinct
  `prediction_anchor_date`: case patients anchor at `outcome_date - horizon`, control
  patients anchor at an eligible pseudo reference date, and any control with an outcome
  falling inside that horizon window is excluded rather than mislabeled. Every static,
  encounter, and trajectory feature is derived only from data strictly before
  `feature_cutoff = prediction_anchor_date - prediction_gap_days`, and no outcome-derived
  columns (diagnosis/outcome dates, cohort labels, incident flags, treatment fields) ever
  enter the model matrices. Unit tests assert horizon-specific labelling, the pre-cutoff
  feature boundary, outcome-free controls, and the absence of forbidden columns.
- **Split isolation.** Patient-level train/test splits guarantee no participant appears in
  both folds; unit tests assert this.
- **Train-only preprocessing.** Imputation, scaling, and encoding are fit only on the
  training fold via a single fitted `sklearn` `Pipeline`.
- **Viability gating.** Models return `NOT_EVALUABLE` rather than an unreliable metric when
  outcomes, history, or horizon data are insufficient.
- **Conservative conclusions.** The worker only reports `GO_FOR_EXTERNAL_VALIDATION` when discrimination,
  calibration, trajectory stability, and subgroup gates pass; reports explicitly state they carry no
  clinical-validity claim.
- **Retention and access.** Browser-facing APIs require a production research session; raw objects and output
  artifacts are deleted by authorized manual or scheduled retention workflows while audit rows remain append-only.

## Limitations

This platform is for internal synthetic research and engineering exploration only. It has not been
clinically validated and must not be connected to real patient data or used to inform any clinical,
screening, or treatment decision.
