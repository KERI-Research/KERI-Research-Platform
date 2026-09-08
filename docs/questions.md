# Deployment Questions

## Cloudflare R2 CORS policy - resolved

Allow the production origin `https://orama.cerebrallab.org` only. Permit the `PUT` method and the `Content-Type` request header for direct uploads to short-lived, one-object presigned URLs. Do not add a wildcard origin or browser access to storage credentials.

The worker's R2 credentials remain isolated in Hugging Face Space secrets and are never copied into Vercel or browser-visible configuration.

## Cloudflare R2 CORS application - pending account permission

The currently configured R2 credential returned `AccessDenied` for `GetBucketCors`, so the CORS rule cannot be inspected or applied programmatically with that token. Apply this exact policy in the Cloudflare dashboard using a credential with bucket-CORS administration rights:

- Origin: `https://orama.cerebrallab.org`
- Method: `PUT`
- Allowed header: `Content-Type`
- No wildcard origins or browser storage credentials

## Hugging Face Space deployment token - pending write scope

The configured `ORAMA_WORKER_HF_TOKEN` can authenticate and clone `JayNightmare/orama-worker`, but the Space rejects a push with `not authorized to push to this repo`. Grant that token write/contribute access to the private `JayNightmare/orama-worker` Space, then publish the verified worker update from `apps/worker`.
