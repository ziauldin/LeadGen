"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CompanyCard } from "@/components/companies/company-card";
import { PageHeader } from "@/components/layout/page-header";
import { companiesApi } from "@/lib/api/endpoints";

export default function CompaniesPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["companies"],
    queryFn: companiesApi.list,
  });

  const enrichMutation = useMutation({
    mutationFn: (id: number) => companiesApi.enrich(id, true),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["companies"] }),
  });

  return (
    <div>
      <PageHeader title="Companies" description="Enriched company records linked to leads." />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
      <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {data?.items.slice(0, 6).map((company) => (
          <CompanyCard key={company.id} company={company} />
        ))}
      </div>
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Domain</TableHead>
              <TableHead>Enrichment</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data?.items.map((company) => (
              <TableRow key={company.id}>
                <TableCell className="font-medium">{company.name}</TableCell>
                <TableCell>{company.domain ?? "—"}</TableCell>
                <TableCell>{company.enrichment_status}</TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => enrichMutation.mutate(company.id)}
                    disabled={enrichMutation.isPending}
                  >
                    Enrich
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
