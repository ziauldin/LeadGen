// Liveness check for the platform (doesn't touch the API).
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
