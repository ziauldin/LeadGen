"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function statusVariant(status: string): "default" | "secondary" | "destructive" | "outline" {
  if (status === "ok" || status === "ready") return "secondary";
  return "destructive";
}

export default function HealthCheckPage() {
  const liveness = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
  });

  const readiness = useQuery({
    queryKey: ["health", "ready"],
    queryFn: api.healthReady,
    enabled: liveness.isSuccess,
    retry: false,
  });

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>API health</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <section className="space-y-2">
            <h2 className="text-sm font-medium">Liveness</h2>
            {liveness.isLoading && <p className="text-muted-foreground text-sm">Checking…</p>}
            {liveness.isError && (
              <Badge variant="destructive">API unreachable — start the backend on port 8000</Badge>
            )}
            {liveness.data && (
              <div className="space-y-2 text-sm">
                <p>
                  Status: <Badge variant={statusVariant(liveness.data.status)}>{liveness.data.status}</Badge>
                </p>
                <p className="text-muted-foreground">Environment: {liveness.data.environment}</p>
              </div>
            )}
          </section>

          <section className="space-y-2">
            <h2 className="text-sm font-medium">Readiness</h2>
            {readiness.isLoading && <p className="text-muted-foreground text-sm">Checking dependencies…</p>}
            {readiness.isError && (
              <Badge variant="destructive">Readiness check failed — database or Redis may be down</Badge>
            )}
            {readiness.data && (
              <div className="space-y-3 text-sm">
                <p>
                  Status:{" "}
                  <Badge variant={statusVariant(readiness.data.status)}>{readiness.data.status}</Badge>
                </p>
                <ul className="space-y-2">
                  {readiness.data.dependencies.map((dep) => (
                    <li key={dep.name} className="flex items-start justify-between gap-4">
                      <span className="font-medium capitalize">{dep.name}</span>
                      <span className="text-right">
                        <Badge variant={statusVariant(dep.status)}>{dep.status}</Badge>
                        {dep.detail && (
                          <p className="text-muted-foreground mt-1 max-w-xs text-xs">{dep.detail}</p>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        </CardContent>
      </Card>
    </main>
  );
}
