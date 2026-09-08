---
title: ORAMA Research Worker
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
fullWidth: false
tags:
  - research
  - longitudinal
  - machine-learning
  - cancer-feasibility
  - non-diagnostic
pinned: false
license: other
---

## ORAMA Research Worker

> **Research use only — non-diagnostic.**
> This worker is a synthetic feasibility modelling service. It does not produce clinical decisions,
> diagnoses, or predictions suitable for patient care. All outputs require independent biological,
> clinical, and governance validation before any further use.

Private FastAPI worker for the [ORAMA Research Platform](https://orama.cerebrallab.org).
Runs the longitudinal cancer feasibility pipeline (M0–M5 model comparison suite) as an
asynchronous background job triggered by the Vercel orchestration layer.

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/health` | None | Liveness check |
| `POST` | `/internal/jobs/run` | Shared secret | Submit and run a pipeline job |
| `GET` | `/internal/jobs/{job_id}` | Shared secret | Poll job status and result |
| `POST` | `/internal/storage/presign-upload` | Shared secret | Issue one-object R2 PUT URL |
| `POST` | `/internal/datasets/validate` | Shared secret | Validate private upload contract |
| `POST` | `/internal/storage/presign-download` | Shared secret | Sign a result artifact download |
| `DELETE` | `/internal/storage/uploads/{upload_id}` | Shared secret | Delete one raw upload |
| `DELETE` | `/internal/storage/jobs/{job_id}/artifacts` | Shared secret | Delete job-scoped artifacts |

All `/internal/*` endpoints require the `X-Orama-Worker-Secret` header matching `ORAMA_WORKER_SHARED_SECRET`.

## Required Secrets (set in HF Space Settings → Variables and Secrets)

```text
AWS_ACCESS_KEY_ID          # Cloudflare R2 token key
AWS_SECRET_ACCESS_KEY      # Cloudflare R2 token secret
ORAMA_OBJECT_STORAGE_BUCKET=orama
ORAMA_OBJECT_STORAGE_ENDPOINT=https://4ae744de780b974371d520e056d76b8c.r2.cloudflarestorage.com
ORAMA_WORKER_SHARED_SECRET # Must match Vercel ORAMA_WORKER_SHARED_SECRET
ORAMA_VERCEL_URL=https://orama.cerebrallab.org
```

## Architecture

```text
Vercel (Next.js) ──POST /internal/jobs/run──▶ This Space
                                               │
                                               ├─ Downloads one private input from R2
                                               ├─ Runs ORAMA pipeline (M0–M5)
                                               ├─ Writes artefacts to R2
                                               └─ Callbacks to Vercel /api/orama/jobs/{id}/callback
```

## Pipeline Models

| Model | Description |
| --- | --- |
| M0 | Demographic / utilisation reference (logistic regression) |
| M1 | Static-only elastic-net logistic regression |
| M2 | Static + trajectory elastic-net logistic regression |
| M3 | Static-only XGBoost |
| M4 | Static + trajectory XGBoost (primary ORAMA candidate) |
| M5 | Trajectory-only elastic-net logistic regression |

Primary outcome: `ΔM4 − M3 AUROC` and `ΔM2 − M1 AUROC` across prediction horizons. A positive outcome is `GO_FOR_EXTERNAL_VALIDATION`, never a deployment or clinical decision.

## Governance

- Processes pseudonymised synthetic data only in this scaffold
- No patient identifiers, NHS numbers, or direct identifiers may be uploaded
- Requires institutional approval, DPIA, and data-sharing agreement before real health data use
- All outputs are research artefacts requiring independent validation
