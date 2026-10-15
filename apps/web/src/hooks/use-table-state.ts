"use client";

import { useCallback, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

export type TableState = {
  page: number;
  pageSize: number;
  sort: string | undefined;
  filters: Record<string, string>;
};

const RESERVED = new Set(["page", "size", "sort"]);

/**
 * Table paging, sorting and filters kept in the URL, so views can be shared and survive
 * reloads. Must be used inside a <Suspense> boundary (it reads search params).
 */
export function useTableState(defaults: { pageSize?: number; sort?: string } = {}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const state: TableState = useMemo(() => {
    const filters: Record<string, string> = {};
    params.forEach((value, key) => {
      if (!RESERVED.has(key) && value) filters[key] = value;
    });
    return {
      page: Math.max(0, Number(params.get("page") ?? 1) - 1),
      pageSize: Number(params.get("size")) || defaults.pageSize || 25,
      sort: params.get("sort") ?? defaults.sort,
      filters,
    };
  }, [params, defaults.pageSize, defaults.sort]);

  const update = useCallback(
    (changes: Record<string, string | number | undefined | null>, resetPage = true) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(changes)) {
        if (value === undefined || value === null || value === "") next.delete(key);
        else next.set(key, String(value));
      }
      if (resetPage && !("page" in changes)) next.delete("page");
      const qs = next.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return {
    ...state,
    /** Query params for the API: skip/limit/sort plus the active filters. */
    apiParams: {
      skip: state.page * state.pageSize,
      limit: state.pageSize,
      sort: state.sort,
      ...state.filters,
    },
    setPage: (page: number) => update({ page: page > 0 ? page + 1 : undefined }, false),
    setPageSize: (size: number) => update({ size }),
    setSort: (sort: string | undefined) => update({ sort }),
    setFilter: (key: string, value: string | undefined) => update({ [key]: value }),
    clearFilters: () =>
      update(Object.fromEntries(Object.keys(state.filters).map((key) => [key, undefined]))),
  };
}
