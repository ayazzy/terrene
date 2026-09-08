// Same-origin development proxy. Hosted API location is a server-side variable.
async function proxy(req: Request) {
  const origin =
    process.env.CRC_API_URL ||
    (process.env.NODE_ENV !== 'production' ? 'http://127.0.0.1:8000' : '');
  if (!origin)
    return Response.json(
      { detail: 'Screening API is not configured for this deployment.' },
      { status: 503 },
    );
  const u = new URL(req.url);
  const headers = new Headers();
  for (const key of ['authorization', 'content-type']) {
    const v = req.headers.get(key);
    if (v) headers.set(key, v);
  }
  try {
    const r = await fetch(origin + u.pathname + u.search, {
      method: req.method,
      headers,
      body: ['GET', 'HEAD'].includes(req.method) ? undefined : await req.text(),
    });
    return new Response(r.body, {
      status: r.status,
      headers: {
        'Content-Type': r.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch {
    return Response.json(
      {
        detail:
          'Screening service is offline. Start the CRC API and worker, then retry.',
      },
      { status: 503 },
    );
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
