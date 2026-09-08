import "server-only";

import { createHash, timingSafeEqual } from "node:crypto";

export const RESEARCH_ACCESS_COOKIE = "orama_research_access";

function configuredAccessToken() {
  return process.env.ORAMA_RESEARCH_ACCESS_TOKEN?.trim() || null;
}

function isProductionRuntime() {
  return process.env.NODE_ENV === "production";
}

function readCookie(request: Request, name: string) {
  const cookies = request.headers.get("cookie") ?? "";
  const prefix = `${name}=`;
  return cookies
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(prefix))
    ?.slice(prefix.length) ?? null;
}

function requestToken(request: Request) {
  const authorization = request.headers.get("authorization");
  if (authorization?.startsWith("Bearer ")) {
    return authorization.slice("Bearer ".length);
  }
  return readCookie(request, RESEARCH_ACCESS_COOKIE);
}

export function isResearchAccessConfigured() {
  return configuredAccessToken() !== null;
}

export function researchAccessIsRequired() {
  return isProductionRuntime() || isResearchAccessConfigured();
}

export function verifyResearchAccessToken(candidate: string | null | undefined) {
  const expected = configuredAccessToken();
  if (!expected || !candidate) {
    return false;
  }

  const expectedHash = createHash("sha256").update(expected).digest();
  const candidateHash = createHash("sha256").update(candidate).digest();
  return timingSafeEqual(expectedHash, candidateHash);
}

export function requestHasResearchAccess(request: Request) {
  if (!researchAccessIsRequired()) {
    return true;
  }
  return verifyResearchAccessToken(requestToken(request));
}

export function requireResearchAccess(request: Request): Response | null {
  if (!researchAccessIsRequired()) {
    return null;
  }
  if (!isResearchAccessConfigured()) {
    return Response.json(
      { error: "Research access is not configured for this deployment." },
      { status: 503 },
    );
  }
  if (!requestHasResearchAccess(request)) {
    return Response.json({ error: "Research access is required." }, { status: 401 });
  }
  return null;
}

export function researchAccessCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "strict" as const,
    secure: isProductionRuntime(),
    path: "/",
    maxAge: 8 * 60 * 60,
  };
}