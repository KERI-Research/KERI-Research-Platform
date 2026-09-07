# ORAMA Worker

This worker is a Python 3.11 FastAPI service for a **synthetic-only longitudinal research pipeline** in the ORAMA research platform scaffold. It accepts inline synthetic participant, observation, outcome, encounter, and data-dictionary payloads, runs a synchronous feasibility-oriented modelling workflow, and returns research-only metrics and report artifacts.

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

## Endpoints

- `GET /health` — unauthenticated health check
- `POST /internal/jobs/run` — authenticated synchronous synthetic research pipeline execution
- `GET /internal/jobs/{job_id}` — authenticated job lookup and result retrieval
