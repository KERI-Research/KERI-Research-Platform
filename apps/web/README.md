# ORAMA Research Platform (web)

This Next.js app is a **research-only, synthetic-data platform** for a longitudinal cancer-risk workflow. It is **non-diagnostic**, uses private object storage and a private worker, and must **not** be used for clinical decision-making or patient-facing interpretation.

## Local development

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Environment variables

Copy `.env.example` to `.env.local` and configure the server-side deployment variables.

- `ORAMA_DATABASE_URL`
- `ORAMA_WORKER_URL`
- `ORAMA_WORKER_HF_TOKEN` when the worker is a private `hf.space` deployment
- `ORAMA_WORKER_SHARED_SECRET`
- `ORAMA_APP_URL`
- `ORAMA_RESEARCH_ACCESS_TOKEN`
- `ORAMA_RESEARCH_ACTOR_ID`
- `ORAMA_RETENTION_DAYS`
- `ORAMA_RETENTION_CRON_SECRET`
- `NEXT_PUBLIC_APP_NAME`

Only `NEXT_PUBLIC_*` values are exposed to the browser. Keep every `ORAMA_*` value server-side only.

## What this scaffold demonstrates

- Persistent research-only disclaimer banner and shared navigation
- Direct browser-to-R2 upload sessions issued by the authenticated worker
- Server-persisted datasets, metadata validation, frozen jobs, worker polling, callbacks, and report artifacts
- Production research access session and manual/scheduled retention deletion routes
- Daily retention cleanup through `vercel.json` at 03:00 UTC

## Important limitations

- Only synthetic or explicitly approved pseudonymised research data may be uploaded
- No diagnostic, prognostic, or clinical decision-support output is implemented
- Apply `drizzle/0001_governance_and_artifacts.sql` before enabling production intake
- Configure the R2 bucket CORS policy for only `https://orama.cerebrallab.org`, `PUT`, and `Content-Type`
- Set `ORAMA_RETENTION_CRON_SECRET` or Vercel's `CRON_SECRET` before the scheduled cleanup is enabled
