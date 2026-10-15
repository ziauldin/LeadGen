"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import {
  Globe,
  MoreHorizontal,
  Pencil,
  Plus,
  Search,
  Tag,
  Target,
  Trash2,
  Users,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ErrorState } from "@/components/shared/loading-error";
import { DeleteNicheDialog } from "@/components/niches/delete-niche-dialog";
import { nichesApi } from "@/lib/api/endpoints";
import type { Niche } from "@/lib/api/types";

function sizeRange(niche: Niche) {
  if (!niche.company_size_min && !niche.company_size_max) return null;
  if (niche.company_size_min && niche.company_size_max)
    return `${niche.company_size_min}–${niche.company_size_max} people`;
  if (niche.company_size_min) return `${niche.company_size_min}+ people`;
  return `Up to ${niche.company_size_max} people`;
}

function NicheCard({ niche, onDelete }: { niche: Niche; onDelete: (niche: Niche) => void }) {
  const size = sizeRange(niche);
  return (
    <article className="flex flex-col rounded-lg border border-[var(--outline-variant)] bg-white p-5 shadow-sm transition-shadow hover:shadow-md">
      <div className="mb-3 flex items-start justify-between gap-2">
        <span
          className="flex size-10 items-center justify-center rounded-lg bg-[var(--primary-fixed)]"
          aria-hidden
        >
          <Target className="size-5 text-[var(--primary)]" />
        </span>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${niche.name}`} />
            }
          >
            <MoreHorizontal aria-hidden />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-44">
            <DropdownMenuItem render={<Link href={`/niches/${niche.id}`} />}>
              <Pencil aria-hidden />
              Edit niche
            </DropdownMenuItem>
            <DropdownMenuItem render={<Link href={`/leads?niche_id=${niche.id}`} />}>
              <Users aria-hidden />
              View leads
            </DropdownMenuItem>
            <DropdownMenuItem render={<Link href={`/search?niche_id=${niche.id}`} />}>
              <Search aria-hidden />
              Run a search
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={() => onDelete(niche)}>
              <Trash2 aria-hidden />
              Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <h3 className="text-[16px] font-semibold text-[var(--on-surface)]">
        <Link
          href={`/niches/${niche.id}`}
          className="hover:text-[var(--primary)] hover:underline focus-visible:rounded focus-visible:ring-2 focus-visible:ring-[var(--primary)] focus-visible:outline-none"
        >
          {niche.name}
        </Link>
      </h3>
      <p className="mb-3 text-[13px] text-[var(--on-surface-variant)]">{niche.industry}</p>

      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-[var(--on-surface-variant)]">
        <span className="inline-flex items-center gap-1">
          <Globe className="size-3.5" aria-hidden />
          {niche.country}
        </span>
        {size ? (
          <span className="inline-flex items-center gap-1">
            <Users className="size-3.5" aria-hidden />
            {size}
          </span>
        ) : null}
      </div>

      {niche.target_roles.length > 0 ? (
        <div className="mb-3">
          <p className="mb-1.5 text-[11px] font-semibold tracking-wider text-[var(--on-surface-variant)] uppercase">
            Target roles
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {niche.target_roles.slice(0, 4).map((role) => (
              <li
                key={role}
                className="rounded bg-[var(--primary-fixed)] px-2 py-0.5 text-[11px] font-medium text-[var(--on-primary-fixed)]"
              >
                {role}
              </li>
            ))}
            {niche.target_roles.length > 4 ? (
              <li className="px-1 text-[11px] text-[var(--on-surface-variant)]">
                +{niche.target_roles.length - 4} more
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}

      {niche.keywords.length > 0 ? (
        <div>
          <p className="mb-1.5 text-[11px] font-semibold tracking-wider text-[var(--on-surface-variant)] uppercase">
            Keywords
          </p>
          <ul className="flex flex-wrap gap-1.5">
            {niche.keywords.slice(0, 5).map((keyword) => (
              <li
                key={keyword}
                className="inline-flex items-center gap-1 rounded bg-[var(--surface-container)] px-2 py-0.5 text-[11px] text-[var(--on-surface-variant)]"
              >
                <Tag className="size-2.5" aria-hidden />
                {keyword}
              </li>
            ))}
            {niche.keywords.length > 5 ? (
              <li className="px-1 text-[11px] text-[var(--on-surface-variant)]">
                +{niche.keywords.length - 5} more
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}

      <div className="flex-1" />
      <div className="mt-4 flex items-center justify-between border-t border-[var(--outline-variant)] pt-4">
        <Link
          href={`/leads?niche_id=${niche.id}`}
          className="text-[12px] font-medium text-[var(--primary)] hover:underline"
        >
          View leads →
        </Link>
        <Link
          href={`/search?niche_id=${niche.id}`}
          className="text-[12px] font-medium text-[var(--on-surface-variant)] hover:text-[var(--on-surface)] hover:underline"
        >
          Run search
        </Link>
      </div>
    </article>
  );
}

export default function NichesPage() {
  const [deleteTarget, setDeleteTarget] = useState<Niche | null>(null);
  const niches = useQuery({
    queryKey: ["niches", { limit: 200 }],
    queryFn: () => nichesApi.list({ limit: 200 }),
  });
  const items = niches.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Niches"
        description="The markets you target: who they are, where they are and which keywords describe them."
        actions={
          <ButtonLink href="/niches/new">
            <Plus aria-hidden />
            New niche
          </ButtonLink>
        }
      />

      {niches.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, i) => (
            <div
              key={i}
              className="h-56 animate-pulse rounded-lg border border-[var(--outline-variant)] bg-white"
            />
          ))}
        </div>
      ) : niches.error ? (
        <ErrorState error={niches.error} onRetry={() => niches.refetch()} />
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] px-6 py-20 text-center">
          <span
            className="mb-4 flex size-14 items-center justify-center rounded-full bg-[var(--primary-fixed)]"
            aria-hidden
          >
            <Target className="size-7 text-[var(--primary)]" />
          </span>
          <h3 className="mb-1 text-[18px] font-semibold text-[var(--on-surface)]">No niches yet</h3>
          <p className="mb-6 max-w-md text-[14px] text-[var(--on-surface-variant)]">
            A niche describes one market you want to reach. Create one to generate search queries
            and start finding leads.
          </p>
          <ButtonLink href="/niches/new">
            <Plus aria-hidden />
            Create your first niche
          </ButtonLink>
        </div>
      ) : (
        <>
          <p className="mb-3 text-[13px] text-[var(--on-surface-variant)]" aria-live="polite">
            {niches.data?.total.toLocaleString()} niche{niches.data?.total === 1 ? "" : "s"}
          </p>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {items.map((niche) => (
              <NicheCard key={niche.id} niche={niche} onDelete={setDeleteTarget} />
            ))}
          </div>
        </>
      )}

      <DeleteNicheDialog
        niche={deleteTarget}
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      />
    </div>
  );
}
