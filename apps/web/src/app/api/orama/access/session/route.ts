import { NextResponse } from "next/server";

import {
  isResearchAccessConfigured,
  RESEARCH_ACCESS_COOKIE,
  requestHasResearchAccess,
  researchAccessCookieOptions,
  researchAccessIsRequired,
  verifyResearchAccessToken,
} from "@/lib/research-access";

function isAccessRequest(body: unknown): body is { accessToken: string } {
  return typeof body === "object" && body !== null && typeof (body as { accessToken?: unknown }).accessToken === "string";
}

export async function GET(request: Request) {
  return NextResponse.json({
    accessRequired: researchAccessIsRequired(),
    configured: isResearchAccessConfigured(),
    authenticated: requestHasResearchAccess(request),
  });
}

export async function POST(request: Request) {
  const body: unknown = await request.json().catch(() => null);
  if (!isAccessRequest(body) || !verifyResearchAccessToken(body.accessToken)) {
    return NextResponse.json({ error: "Invalid research access token." }, { status: 401 });
  }

  const response = NextResponse.json({ authenticated: true });
  response.cookies.set(RESEARCH_ACCESS_COOKIE, body.accessToken, researchAccessCookieOptions());
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ authenticated: false });
  response.cookies.set(RESEARCH_ACCESS_COOKIE, "", { ...researchAccessCookieOptions(), maxAge: 0 });
  return response;
}