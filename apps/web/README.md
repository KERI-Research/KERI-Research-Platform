# ORAMA Research Platform (web)

This Next.js app is a **research-only, synthetic-data scaffold** for a longitudinal cancer-risk dashboard journey. It is **non-diagnostic**, uses **mocked API routes**, and must **not** be used for clinical decision-making or patient-facing interpretation.

## Local development

```bash
npm install
npm run dev
```

Then open `http://localhost:3000`.

## Environment variables

Copy `.env.example` to `.env.local` and fill placeholders as needed for future backend integration.

- `ORAMA_DATABASE_URL`
- `ORAMA_OBJECT_STORAGE_BUCKET`
- `ORAMA_OBJECT_STORAGE_ENDPOINT`
- `ORAMA_WORKER_URL`
- `ORAMA_WORKER_SHARED_SECRET`
- `NEXT_PUBLIC_APP_NAME`

Only `NEXT_PUBLIC_*` values are exposed to the browser. Keep every `ORAMA_*` value server-side only.

## What this scaffold demonstrates

- Persistent research-only disclaimer banner and shared navigation
- Local-only metadata preview for `.csv`, `.parquet`, and `.zip` selections
- Mock schema-mapping, validation, analysis configuration, jobs, and report pages
- Mock App Router API endpoints for upload initiation/completion, validation, job lifecycle, callback handling, and report download

## Important limitations

- This app demonstrates a **mocked synthetic job journey only**
- No real files are uploaded, stored, or transmitted by the upload page
- No real diagnostic, prognostic, or clinical decision-support logic is implemented
- Replace the in-memory stores and TODOs with private storage, database, and worker integrations before any real research deployment
