"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { buttonVariants } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { nichesApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

export default function NichesPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["niches"],
    queryFn: nichesApi.list,
  });

  return (
    <div>
      <PageHeader
        title="Niches"
        description="Target markets and qualification criteria."
        actions={
          <Link href="/niches/new" className={cn(buttonVariants())}>
            New niche
          </Link>
        }
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      {(data?.items ?? []).length === 0 && !isLoading ? (
        <EmptyState
          title="No niches yet"
          description="Create a niche to define your target market."
          action={
            <Link href="/niches/new" className={cn(buttonVariants())}>
              Create niche
            </Link>
          }
        />
      ) : null}
      <div className="grid gap-4 md:grid-cols-2">
        {(data?.items ?? []).map((niche) => (
          <Card key={niche.id}>
            <CardHeader>
              <CardTitle className="text-lg">
                <Link href={`/niches/${niche.id}`} className="hover:underline">
                  {niche.name}
                </Link>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <p>
                {niche.industry} · {niche.country}
              </p>
              <div className="flex flex-wrap gap-1">
                {niche.keywords.slice(0, 4).map((kw) => (
                  <Badge key={kw} variant="secondary">
                    {kw}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
