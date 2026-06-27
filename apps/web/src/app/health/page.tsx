"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  AlertTriangle,
  CheckCircle2,
  Database,
  RefreshCw,
  Server,
  XCircle,
  Zap,
} from "lucide-react";

type DependencyStatus = { name: string; status: string; detail?: string | null };

function StatusPill({ status }: { status: string }) {
  const ok = status === "ok" || status === "ready";
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[12px] font-semibold"
      style={{
        background: ok ? "var(--secondary-fixed)" : "var(--error-container)",
        color: ok ? "var(--on-secondary-fixed)" : "var(--on-error-container)",
      }}
    >
      {ok ? (
        <CheckCircle2 className="w-3.5 h-3.5" />
      ) : (
        <XCircle className="w-3.5 h-3.5" />
      )}
      {ok ? "Healthy" : status}
    </span>
  );
}

const DEP_ICONS: Record<string, typeof Server> = {
  database: Database,
  redis: Zap,
};

export default function HealthCheckPage() {
  const liveness = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    refetchInterval: 30_000,
  });

  const readiness = useQuery({
    queryKey: ["health", "ready"],
    queryFn: api.healthReady,
    enabled: liveness.isSuccess,
    retry: false,
    refetchInterval: 30_000,
  });

  const dependencies: DependencyStatus[] = readiness.data?.dependencies ?? [];
  const lastChecked = new Date().toLocaleTimeString();

  return (
    <main
      className="min-h-screen flex items-center justify-center p-6"
      style={{ background: "var(--background)" }}
    >
      <div className="w-full max-w-xl">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ background: "var(--primary-fixed)" }}
          >
            <Server className="w-5 h-5" style={{ color: "var(--primary)" }} />
          </div>
          <div>
            <h1
              className="text-[20px] font-semibold"
              style={{ color: "var(--on-surface)" }}
            >
              System Status
            </h1>
            <p className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
              LeadsGen API infrastructure
            </p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 text-[12px]" style={{ color: "var(--on-surface-variant)" }}>
            <RefreshCw className="w-3.5 h-3.5" />
            Auto-refreshes every 30s · last {lastChecked}
          </div>
        </div>

        {/* Liveness */}
        <div
          className="bg-white border rounded-lg p-5 shadow-sm mb-4"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2
              className="text-[14px] font-semibold"
              style={{ color: "var(--on-surface)" }}
            >
              API Liveness
            </h2>
            {liveness.isLoading ? (
              <div
                className="w-4 h-4 border-2 rounded-full animate-spin"
                style={{
                  borderColor: "var(--primary-container)",
                  borderTopColor: "var(--primary)",
                }}
              />
            ) : liveness.isError ? (
              <StatusPill status="error" />
            ) : liveness.data ? (
              <StatusPill status={liveness.data.status} />
            ) : null}
          </div>
          {liveness.isError && (
            <div
              className="flex items-start gap-2 p-3 rounded"
              style={{ background: "var(--error-container)" }}
            >
              <AlertTriangle
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: "var(--on-error-container)" }}
              />
              <p className="text-[13px]" style={{ color: "var(--on-error-container)" }}>
                API is unreachable. Make sure the backend is running on port 8000 and CORS is
                configured.
              </p>
            </div>
          )}
          {liveness.data && (
            <div className="flex items-center justify-between">
              <span className="text-[13px]" style={{ color: "var(--on-surface-variant)" }}>
                Environment
              </span>
              <span
                className="px-2 py-0.5 rounded text-[12px] font-mono"
                style={{
                  background: "var(--surface-container)",
                  color: "var(--on-surface)",
                }}
              >
                {liveness.data.environment}
              </span>
            </div>
          )}
        </div>

        {/* Readiness + dependencies */}
        <div
          className="bg-white border rounded-lg p-5 shadow-sm"
          style={{ borderColor: "var(--outline-variant)" }}
        >
          <div className="flex items-center justify-between mb-4">
            <h2
              className="text-[14px] font-semibold"
              style={{ color: "var(--on-surface)" }}
            >
              Dependencies
            </h2>
            {readiness.isLoading && liveness.isSuccess ? (
              <div
                className="w-4 h-4 border-2 rounded-full animate-spin"
                style={{
                  borderColor: "var(--primary-container)",
                  borderTopColor: "var(--primary)",
                }}
              />
            ) : readiness.data ? (
              <StatusPill status={readiness.data.status} />
            ) : null}
          </div>

          {readiness.isError && (
            <div
              className="flex items-start gap-2 p-3 rounded mb-4"
              style={{ background: "var(--error-container)" }}
            >
              <AlertTriangle
                className="w-4 h-4 mt-0.5 shrink-0"
                style={{ color: "var(--on-error-container)" }}
              />
              <p className="text-[13px]" style={{ color: "var(--on-error-container)" }}>
                Readiness check failed — database or Redis may be down.
              </p>
            </div>
          )}

          {dependencies.length > 0 && (
            <div className="space-y-3">
              {dependencies.map((dep) => {
                const Icon = DEP_ICONS[dep.name.toLowerCase()] ?? Server;
                const ok = dep.status === "ok" || dep.status === "ready";
                return (
                  <div
                    key={dep.name}
                    className="flex items-start justify-between p-3 rounded"
                    style={{
                      background: ok
                        ? "var(--surface-container-low)"
                        : "var(--error-container)",
                    }}
                  >
                    <div className="flex items-center gap-3">
                      <Icon
                        className="w-4 h-4"
                        style={{ color: ok ? "var(--primary)" : "var(--on-error-container)" }}
                      />
                      <div>
                        <p
                          className="text-[13px] font-semibold capitalize"
                          style={{
                            color: ok
                              ? "var(--on-surface)"
                              : "var(--on-error-container)",
                          }}
                        >
                          {dep.name}
                        </p>
                        {dep.detail && (
                          <p
                            className="text-[12px] mt-0.5"
                            style={{
                              color: ok
                                ? "var(--on-surface-variant)"
                                : "var(--on-error-container)",
                            }}
                          >
                            {dep.detail}
                          </p>
                        )}
                      </div>
                    </div>
                    {ok ? (
                      <CheckCircle2
                        className="w-4 h-4 shrink-0"
                        style={{ color: "var(--secondary)" }}
                      />
                    ) : (
                      <XCircle
                        className="w-4 h-4 shrink-0"
                        style={{ color: "var(--on-error-container)" }}
                      />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {!readiness.data && !readiness.isLoading && !readiness.isError && liveness.isError && (
            <p
              className="text-[13px] text-center"
              style={{ color: "var(--on-surface-variant)" }}
            >
              Connect the API first to check dependencies.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
