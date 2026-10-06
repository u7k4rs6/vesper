// Forwards browser calls to the API and adds the dashboard token server-side.
// The browser never sees DASHBOARD_TOKEN (docs/03_FRONTEND_SPEC.md §9).
import { NextRequest } from "next/server";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function forward(req: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  if (path.some((p) => p === ".." || p === ".")) {
    return Response.json({ error: { code: "bad_path", message: "Bad path." } }, { status: 400 });
  }
  const url = `${API}/api/${path.map(encodeURIComponent).join("/")}${req.nextUrl.search}`;
  const headers: Record<string, string> = { "X-Dashboard-Token": process.env.DASHBOARD_TOKEN ?? "" };
  // The API rate-limits the demo button per browser, so pass the browser's address along.
  const client = req.headers.get("x-forwarded-for")?.split(",")[0].trim() || req.headers.get("x-real-ip");
  if (client) headers["X-Forwarded-For"] = client;
  const contentType = req.headers.get("content-type");
  if (contentType) headers["Content-Type"] = contentType;
  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body: req.method === "GET" ? undefined : await req.text(),
      cache: "no-store",
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json(
      { error: { code: "unreachable", message: "Vesper couldn't reach the server. It will keep trying." } },
      { status: 502 },
    );
  }
}

export { forward as GET, forward as POST };
