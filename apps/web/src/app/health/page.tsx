"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Cog,
  Database,
  RefreshCw,
  Server,
  XCircle,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Readiness = Awaited<ReturnType<typeof api.healthReady>>;
type Dependency = Readiness["dependencies"][number];

const DEPENDENCIES: Record<string, { label: string; about: string; icon: LucideIcon }> = {
  database: { label: "Database", about: "Stores workspaces, leads, campaigns and emails.", icon: Database },
  redis: { label: "Queue", about: "Hands work such as sending and enrichment to the workers.", icon: Zap },
  worker: { label: "Background worker", about: "Sends approved emails and processes replies.", icon: Cog },
  scheduler: { label: "Scheduler", about: "Starts timed jobs like follow-ups and inbox checks.", icon: Cog },
};

function describe(dependency: Dependency) {
  const key = dependency.name.toLowerCase();
  const known =
    DEPENDENCIES[key] ??
    Object.entries(DEPENDENCIES).find(([name]) => key.includes(name))?.[1];
  return known ?? { label: dependency.name.replaceAll("_", " "), about: "", icon: Server };
}

const isOk = (status: string | undefined) => status === "ok" || status === "ready";

/** The readiness endpoint answers 503 with the same body when something is down. */
async function fetchReadiness(): Promise<Readiness> {
  try {
    return await api.healthReady();
  } catch (error) {
    if (
      error instanceof ApiError &&
      error.status === 503 &&
      error.detail &&
      typeof error.detail === "object" &&
      "dependencies" in error.detail
    ) {
      return error.detail as Readiness;
    }
    throw error;
  }
}

function Pill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[12px] font-semibold",
        ok
          ? "bg-[var(--secondary-fixed)] text-[var(--on-secondary-fixed)]"
          : "bg-[var(--error-container)] text-[var(--on-error-container)]",
      )}
    >
      {ok ? <CheckCircle2 className="size-3.5" aria-hidden /> : <XCircle className="size-3.5" aria-hidden />}
      {label}
    </span>
  );
}

export default function HealthPage() {
  const liveness = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
    retry: false,
  });
  const readiness = useQuery({
    queryKey: ["health", "ready"],
    queryFn: fetchReadiness,
    refetchInterval: 30_000,
    retry: false,
  });

  const apiUp = liveness.isSuccess;
  const ready = readiness.data;
  const failing = ready?.dependencies.filter((dep) => !isOk(dep.status)) ?? [];
  const loading = liveness.isLoading || readiness.isLoading;

  let overall: { tone: "ok" | "warn" | "down"; title: string; text: string };
  if (liveness.isError) {
    overall = {
      tone: "down",
      title: "API unreachable",
      text: "We can't reach the API right now, so the app won't work. Please try again in a few minutes.",
    };
  } else if (ready && ready.status !== "ready") {
    overall = {
      tone: "warn",
      title: "Degraded",
      text: `The API is up, but ${failing.length ? failing.map((dep) => describe(dep).label.toLowerCase()).join(", ") : "a dependency"} ${failing.length === 1 ? "isn't" : "aren't"} responding. Some things, like sending or background jobs, may be delayed.`,
    };
  } else if (readiness.isError) {
    overall = {
      tone: "warn",
      title: "Status unknown",
      text: "The API is up, but the readiness check didn't answer.",
    };
  } else {
    overall = { tone: "ok", title: "All systems operational", text: "Everything is up and responding." };
  }

  const checkedAt = Math.max(liveness.dataUpdatedAt, readiness.dataUpdatedAt, liveness.errorUpdatedAt);
  const refreshing = liveness.isFetching || readiness.isFetching;

  return (
    <main className="min-h-screen bg-[var(--background)] px-4 py-10 sm:py-16">
      <div className="mx-auto w-full max-w-2xl space-y-5">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-lg bg-[var(--primary-fixed)]">
              <Activity className="size-5 text-[var(--primary)]" aria-hidden />
            </div>
            <div>
              <h1 className="text-[22px] font-semibold text-[var(--on-surface)]">System status</h1>
              <p className="text-[13px] text-[var(--on-surface-variant)]">
                Live health of the API and the services it depends on.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 sm:ml-auto">
            <span className="text-[12px] text-[var(--on-surface-variant)]" aria-live="polite">
              {checkedAt ? `Checked ${new Date(checkedAt).toLocaleTimeString()}` : "Checking…"}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                void liveness.refetch();
                void readiness.refetch();
              }}
              disabled={refreshing}
            >
              <RefreshCw className={cn(refreshing && "animate-spin")} aria-hidden />
              Refresh
            </Button>
          </div>
        </header>

        {loading ? (
          <div className="h-20 animate-pulse rounded-lg bg-[var(--surface-container-high)]" role="status" aria-label="Checking status" />
        ) : (
          <section
            aria-live="polite"
            className={cn(
              "flex items-start gap-3 rounded-lg border p-4",
              overall.tone === "ok" && "border-[var(--secondary)]/30 bg-[var(--secondary-fixed)]/40",
              overall.tone === "warn" && "border-[var(--tertiary-fixed-dim)] bg-[var(--tertiary-fixed)]/50",
              overall.tone === "down" && "border-[var(--error)]/30 bg-[var(--error-container)]/60",
            )}
          >
            {overall.tone === "ok" ? (
              <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-[var(--secondary)]" aria-hidden />
            ) : overall.tone === "warn" ? (
              <AlertTriangle className="mt-0.5 size-5 shrink-0 text-[var(--tertiary)]" aria-hidden />
            ) : (
              <XCircle className="mt-0.5 size-5 shrink-0 text-[var(--error)]" aria-hidden />
            )}
            <div>
              <h2 className="text-[15px] font-semibold text-[var(--on-surface)]">{overall.title}</h2>
              <p className="text-[13px] text-[var(--on-surface-variant)]">{overall.text}</p>
            </div>
          </section>
        )}

        <section className="rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm" aria-labelledby="components-heading">
          <h2 id="components-heading" className="border-b border-[var(--outline-variant)] px-4 py-3 text-[14px] font-semibold text-[var(--on-surface)]">
            Components
          </h2>
          <ul className="divide-y divide-[var(--outline-variant)]">
            <li className="flex items-start gap-3 px-4 py-3">
              <Server className="mt-0.5 size-4 shrink-0 text-[var(--primary)]" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-semibold text-[var(--on-surface)]">API</p>
                <p className="text-[12px] text-[var(--on-surface-variant)]">
                  {liveness.data ? (
                    <>
                      Environment{" "}
                      <span className="rounded bg-[var(--surface-container)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--on-surface)]">
                        {liveness.data.environment}
                      </span>
                    </>
                  ) : (
                    "Handles every request from the app."
                  )}
                </p>
              </div>
              {liveness.isLoading ? null : <Pill ok={apiUp} label={apiUp ? "Operational" : "Down"} />}
            </li>
            {(ready?.dependencies ?? []).map((dependency) => {
              const info = describe(dependency);
              const Icon = info.icon;
              const ok = isOk(dependency.status);
              return (
                <li key={dependency.name} className="flex items-start gap-3 px-4 py-3">
                  <Icon className={cn("mt-0.5 size-4 shrink-0", ok ? "text-[var(--primary)]" : "text-[var(--error)]")} aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] font-semibold capitalize text-[var(--on-surface)]">{info.label}</p>
                    {info.about ? (
                      <p className="text-[12px] text-[var(--on-surface-variant)]">{info.about}</p>
                    ) : null}
                    {dependency.detail ? (
                      <p className={cn("mt-1 break-words font-mono text-[11px]", ok ? "text-[var(--outline)]" : "text-[var(--error)]")}>
                        {dependency.detail}
                      </p>
                    ) : null}
                  </div>
                  <Pill ok={ok} label={ok ? "Operational" : dependency.status === "missing" ? "Missing" : "Not responding"} />
                </li>
              );
            })}
            {!ready && !readiness.isLoading ? (
              <li className="px-4 py-3 text-[13px] text-[var(--on-surface-variant)]">
                {liveness.isError
                  ? "Dependencies can't be checked while the API is unreachable."
                  : "The readiness check didn't return any details."}
              </li>
            ) : null}
          </ul>
        </section>

        <p className="text-center text-[12px] text-[var(--on-surface-variant)]">
          Refreshes every 30 seconds.{" "}
          <Link href="/dashboard" className="text-[var(--primary)] hover:underline">
            Back to the app
          </Link>
        </p>
      </div>
    </main>
  );
}
