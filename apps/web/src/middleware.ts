import { NextResponse, type NextRequest } from "next/server";

// Pages that work without a session. Everything else under the app needs one.
const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/invite",
  "/health",
  "/healthz",
  "/auth/complete",
  "/subprocessors",
  // Marketing site
  "/features",
  "/use-cases",
  "/pricing",
  "/about",
  "/contact",
  "/docs",
  "/help",
  "/blog",
  "/changelog",
  "/legal",
  "/sitemap.xml",
  "/robots.txt",
  "/opengraph-image",
  "/impersonate",
];

const SESSION_HINT = "lg_session";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const isPublic = pathname === "/" || PUBLIC_PATHS.some((p) => pathname.startsWith(p));
  const hasSession = request.cookies.get(SESSION_HINT)?.value === "1";

  if (!isPublic && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    return NextResponse.redirect(url);
  }
  // Signed-in visitors go straight to the app from the home page and auth pages.
  if (hasSession && (pathname === "/" || pathname === "/login" || pathname === "/register")) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard";
    url.search = "";
    return NextResponse.redirect(url);
  }
  return NextResponse.next();
}

export const config = {
  // Skip the API proxy, Next internals and static files.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\.(?:png|jpg|svg|ico|webp)$).*)"],
};
