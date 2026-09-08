import { NextRequest, NextResponse } from "next/server";

const ACCESS_COOKIE = "orama_research_access";
const EXEMPT_API_PATHS = [
  "/api/orama/access/session",
  "/api/orama/retention/run",
];

function accessIsRequired() {
  return process.env.NODE_ENV === "production" || Boolean(process.env.ORAMA_RESEARCH_ACCESS_TOKEN);
}

function isExemptPath(pathname: string) {
  return pathname === "/access"
    || pathname.startsWith("/api/orama/jobs/") && pathname.endsWith("/callback")
    || EXEMPT_API_PATHS.includes(pathname);
}

export function proxy(request: NextRequest) {
  if (!accessIsRequired() || isExemptPath(request.nextUrl.pathname)) {
    return NextResponse.next();
  }

  if (request.cookies.has(ACCESS_COOKIE)) {
    return NextResponse.next();
  }

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Research access is required." }, { status: 401 });
  }

  const loginUrl = new URL("/access", request.url);
  loginUrl.searchParams.set("next", `${request.nextUrl.pathname}${request.nextUrl.search}`);
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};