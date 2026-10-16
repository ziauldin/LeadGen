import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro } from "@/components/marketing/site-chrome";

export const metadata: Metadata = {
  title: "API reference · LeadsGen",
  description: "The LeadsGen REST API and webhooks: authentication, endpoints, idempotency and signed events.",
  alternates: { canonical: "/docs/api" },
};

export const revalidate = 3600;

type Operation = { summary?: string; description?: string; tags?: string[] };
type OpenApi = { paths: Record<string, Record<string, Operation>> };

const API = (process.env.API_INTERNAL_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const METHOD_STYLES: Record<string, string> = {
  get: "bg-[var(--primary-fixed)] text-[var(--on-primary-fixed)]",
  post: "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]",
  patch: "bg-[var(--tertiary-fixed,#ffe8c2)] text-[var(--on-surface)]",
  delete: "bg-[var(--error-container)] text-[var(--on-error-container)]",
};

async function loadSchema(): Promise<OpenApi | null> {
  try {
    const response = await fetch(`${API}/v1/openapi.json`, { next: { revalidate: 3600 } });
    return response.ok ? ((await response.json()) as OpenApi) : null;
  } catch {
    return null;
  }
}

const EVENTS: [string, string][] = [
  ["lead.created", "A lead was added by hand, import, search or the API"],
  ["email.sent", "An email was accepted by your sending provider"],
  ["email.bounced", "An email bounced or was marked as spam"],
  ["reply.received", "Someone replied to one of your emails"],
  ["enrollment.completed", "A lead finished a campaign sequence"],
];

export default async function ApiDocsPage() {
  const schema = await loadSchema();
  const operations = schema
    ? Object.entries(schema.paths).flatMap(([path, methods]) =>
        Object.entries(methods).map(([method, op]) => ({ path, method, summary: op.summary ?? op.description ?? "" })),
      )
    : [];

  return (
    <div className="mx-auto max-w-4xl space-y-12">
      <PageIntro eyebrow="Developers" title="API reference">
        Automate lead capture, enroll leads in campaigns and react to replies in real time.
      </PageIntro>

      <section className="space-y-3">
        <h2 className="text-[22px] font-bold">Authentication</h2>
        <p className="text-[15px] leading-7">
          Create a key in <strong>Settings → API &amp; webhooks</strong> (Starter plan and above) and send it as a
          bearer token. Keys are scoped, can expire, and stop working if their creator leaves the workspace.
        </p>
        <pre className="overflow-x-auto rounded-lg bg-[#111827] p-4 text-[13px] text-white" tabIndex={0}>
          <code>{`curl https://api.example.com/v1/leads \\
  -H "Authorization: Bearer lg_live_..." \\
  -H "Idempotency-Key: 5f1c..."   # optional, for safe retries of POSTs`}</code>
        </pre>
        <p className="text-[15px] leading-7">
          Lists accept <code>skip</code> and <code>limit</code> (up to 200) and return{" "}
          <code>{"{items, total, skip, limit}"}</code>. Requests are rate limited per key.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-[22px] font-bold">Endpoints</h2>
        {operations.length ? (
          <ul className="divide-y divide-[var(--outline-variant)] rounded-xl border border-[var(--outline-variant)] bg-white">
            {operations.map((op) => (
              <li key={`${op.method} ${op.path}`} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:gap-4">
                <span className={`w-16 rounded px-2 py-0.5 text-center font-mono text-[12px] font-semibold uppercase ${METHOD_STYLES[op.method] ?? ""}`}>
                  {op.method}
                </span>
                <code className="font-mono text-[13px]">{op.path}</code>
                <span className="text-[13px] text-[var(--on-surface-variant)] sm:ml-auto">{op.summary}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-[15px]">
            The full list is in the OpenAPI document at <code>/v1/openapi.json</code> on your API.
          </p>
        )}
        <p className="text-[13px] text-[var(--on-surface-variant)]">
          Import <code>/v1/openapi.json</code> into Postman, Insomnia or your code generator.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-[22px] font-bold">Webhooks</h2>
        <p className="text-[15px] leading-7">
          We POST JSON to your endpoint and sign it with HMAC-SHA256: the <code>LeadsGen-Signature</code> header is{" "}
          <code>t=&lt;unix time&gt;,v1=&lt;hex&gt;</code> over <code>&quot;t.body&quot;</code>. Failed deliveries are retried for
          about two days and can be replayed from the delivery log.
        </p>
        <dl className="grid gap-3 sm:grid-cols-2">
          {EVENTS.map(([name, text]) => (
            <div key={name} className="rounded-lg border border-[var(--outline-variant)] bg-white p-4">
              <dt className="font-mono text-[13px] font-semibold">{name}</dt>
              <dd className="mt-1 text-[14px] text-[var(--on-surface-variant)]">{text}</dd>
            </div>
          ))}
        </dl>
      </section>

      <p className="text-center text-[15px]">
        <Link href="/register" className="font-semibold text-[var(--primary)] hover:underline">
          Create a workspace
        </Link>{" "}
        to get an API key.
      </p>
    </div>
  );
}
