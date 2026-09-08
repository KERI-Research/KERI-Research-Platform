# Deployment Questions

## Cloudflare R2 CORS policy - verified

The production bucket now accepts the approved browser upload policy. A preflight request on 2026-09-08 returned `204 No Content` with:

- `Access-Control-Allow-Origin: https://orama.cerebrallab.org`
- `Access-Control-Allow-Methods: GET, PUT, HEAD`
- `Access-Control-Allow-Headers: Content-Type`
- `Access-Control-Max-Age: 3600`

The worker's R2 credentials remain isolated in Hugging Face Space secrets and are never copied into Vercel or browser-visible configuration.

## Hugging Face Space deployment - source published

The configured `ORAMA_WORKER_HF_TOKEN` now has write access, and the verified worker source has been published to the private `JayNightmare/orama-worker` Space. The standard private Space host accepts both the Hugging Face bearer token and the ORAMA worker shared-secret header; an authenticated lookup for a nonexistent job returns the expected `404 Job not found` response.

The Space has the private R2 credential pair, bucket/endpoint settings, and Vercel callback origin configured. A previously malformed R2 access-key ID was corrected on 2026-09-08; the subsequent signed R2 write/delete probe returned `200` for both operations.

## Vercel production deployment - verified

Production deployment `dpl_7BkM2AbyhmJLQU6r1Cbtbzk837uW` is ready and aliased to `https://orama.cerebrallab.org`. It targets the private Hugging Face Space through the standard `hf.space` hostname and holds the required research-access, retention, worker-authentication, database, and callback configuration as server-side environment values.

Production access checks returned the expected results: an unauthenticated page request redirects to `/access`, an unauthenticated jobs request returns `401`, and a valid research session can retrieve the jobs API with `200`.

## Synthetic smoke metadata cleanup - confirmation required

One pre-fix failed signed-upload attempt left an unfinalized `uploads` metadata row for `orama-production-smoke.zip`. Cloudflare R2 rejected that request before an object was created, so the row has no raw object, dataset, job, artifact, or patient content. The normal retention job deletes expired datasets but deliberately does not delete unfinished upload sessions.

May this one isolated synthetic metadata row be removed through the Neon administrative connection? The complete post-fix synthetic workflow was created and deleted successfully.
