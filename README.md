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

- A full **synthetic** job journey in the web dashboard: upload metadata preview → schema
  mapping → validation → analysis configuration → polling job status → research report.
- A functional worker pipeline that ingests synthetic participants/observations/outcomes/
  encounters, builds trajectory features with strict pre-index-date cutoffs, fits a
  five-model comparison (M0–M4, static vs. static+trajectory), and produces a conservative
  GO/NO_GO/REDIRECT/NOT_EVALUABLE research feasibility conclusion plus JSON/Markdown reports.
- Unit tests proving core safeguards: no post-index-date leakage into trajectory features,
  patient-level train/test isolation (no participant appears in both splits), preprocessing
  fit only on training folds, rejection of invalid/leaky schemas, and viability gating when
  data is insufficient.

This is a **scaffold**: the web app's API routes are safe mocked adapters (in-memory stores,
`TODO` integration seams) and are not wired to a real database, object storage, or the worker
over the network yet. No external services are provisioned, no Hugging Face Space is created
or published, no Vercel project is created, and nothing is deployed automatically by this
repository.

## Repository layout

```
apps/
  web/     Next.js dashboard + mocked App Router API routes (see apps/web/README.md)
  worker/  FastAPI research pipeline worker (see apps/worker/README.md)
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
| `ORAMA_DATABASE_URL` | Future database connection string for dataset/job metadata persistence |
| `ORAMA_OBJECT_STORAGE_BUCKET` | Future private object storage bucket for uploaded datasets |
| `ORAMA_OBJECT_STORAGE_ENDPOINT` | Future private object storage endpoint |
| `ORAMA_WORKER_URL` | Base URL of the deployed worker (called only from server-side route handlers) |
| `ORAMA_WORKER_SHARED_SECRET` | Shared secret sent to the worker's internal endpoints |
| `NEXT_PUBLIC_APP_NAME` | Client-visible application name |

**Worker environment variables:**

| Variable | Purpose |
| --- | --- |
| `ORAMA_WORKER_SHARED_SECRET` | Expected value of the `X-Orama-Worker-Secret` header on internal endpoints |
| `ORAMA_RUNTIME_ENV` | Set to `local`/`dev`/`test` to permit the placeholder shared secret for local development only |

## Deployment topology (manual, not automated by this repo)

1. **Worker → private Hugging Face Docker Space.** Create a private Space with the Docker
   SDK, push `apps/worker` contents, and set `ORAMA_WORKER_SHARED_SECRET` as a Space secret.
   The container listens on port `7860` as required by HF Docker Spaces.
2. **Web → Vercel project rooted at `apps/web`.** Configure the Vercel project's root
   directory as `apps/web` (monorepo-aware build), and set the environment variables above
   in the Vercel project settings (`ORAMA_WORKER_URL` pointing at the deployed Space,
   `ORAMA_WORKER_SHARED_SECRET` matching the Space secret, plus database/object storage
   values once those integrations are implemented).
3. Wire the `TODO` seams in `apps/web/src/app/api/orama/**` to real private object storage,
   a database, authentication, and the deployed worker before using this for anything beyond
   local synthetic demonstration.

This repository does **not** provision any of the above automatically — no Space is created
or published, no Vercel project is created, and no data is sent anywhere.

## Governance and safety controls

- **Synthetic data only.** No real patient data, clinical datasets, or external health
  records are included or referenced anywhere in this repository.
- **Non-diagnostic by design.** The web app displays a persistent "research use only —
  non-diagnostic" banner; the worker's reports carry the same disclaimer.
- **No direct identifiers.** The upload UI warns against uploading direct identifiers and
  only ever previews client-side file metadata; it never persists or transmits file content.
- **Leakage safeguards.** Trajectory features are only derived from observations strictly
  before `index_date - prediction_gap_days`; unit tests assert this boundary.
- **Split isolation.** Patient-level train/test splits guarantee no participant appears in
  both folds; unit tests assert this.
- **Train-only preprocessing.** Imputation, scaling, and encoding are fit only on the
  training fold via a single fitted `sklearn` `Pipeline`.
- **Viability gating.** Models return `NOT_EVALUABLE` rather than an unreliable metric when
  outcomes, history, or horizon data are insufficient.
- **Conservative conclusions.** The worker never reports a stronger conclusion than
  `GO`/`NO_GO`/`REDIRECT`/`NOT_EVALUABLE`, and reports explicitly state they carry no
  clinical-validity claim.

## Limitations

This scaffold is for internal research and engineering exploration only. It has not been
clinically validated, does not implement real authentication or persistence, and must not be
connected to real patient data or used to inform any clinical, screening, or treatment
decision.
