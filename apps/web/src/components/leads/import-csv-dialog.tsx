"use client";

import { useId, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, FileUp } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { getErrorMessage } from "@/lib/api/client";
import { leadsApi } from "@/lib/api/endpoints";
import type { LeadImportResult } from "@/lib/api/types";

const MAX_BYTES = 5 * 1024 * 1024;

export function ImportCsvDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const inputId = useId();
  const queryClient = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [result, setResult] = useState<LeadImportResult | null>(null);

  const upload = useMutation({
    mutationFn: (csv: File) => leadsApi.importCsv(csv),
    // Shown inside the dialog instead of a toast so the user can fix the file and retry.
    onError: (error) => setLocalError(getErrorMessage(error)),
    onSuccess: (data) => {
      setResult(data);
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      queryClient.invalidateQueries({ queryKey: ["companies"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["onboarding"] });
      toast.success(`Import finished: ${data.created} new, ${data.updated} updated`);
    },
  });

  function reset() {
    setFile(null);
    setLocalError(null);
    setResult(null);
    upload.reset();
  }

  function close(next: boolean) {
    if (upload.isPending) return;
    onOpenChange(next);
    if (!next) reset();
  }

  function pick(selected: File | null) {
    setResult(null);
    setLocalError(null);
    if (selected && selected.size > MAX_BYTES) {
      setFile(null);
      setLocalError("That file is larger than 5 MB. Split it into smaller files and import each.");
      return;
    }
    setFile(selected);
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Import leads from CSV</DialogTitle>
          <DialogDescription>
            UTF-8 CSV with a header row, up to 5 MB and 10,000 rows. Include columns such as
            full_name, job_title, email, company, website, niche, source_url and
            compliance_source_note. Existing leads with the same email are updated.
          </DialogDescription>
        </DialogHeader>

        {result ? (
          <div className="space-y-3 text-[13px]" aria-live="polite">
            <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[
                { label: "Created", value: result.created },
                { label: "Updated", value: result.updated },
                { label: "Skipped", value: result.skipped },
                { label: "Errors", value: result.errors.length },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-2.5"
                >
                  <dt className="text-[12px] text-[var(--on-surface-variant)]">{item.label}</dt>
                  <dd className="text-[18px] font-semibold text-[var(--on-surface)]">
                    {item.value.toLocaleString()}
                  </dd>
                </div>
              ))}
            </dl>
            {result.errors.length > 0 ? (
              <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900">
                <p className="mb-1.5 flex items-center gap-2 font-semibold">
                  <AlertTriangle className="size-4" aria-hidden />
                  Rows that couldn&apos;t be imported
                </p>
                <ul className="max-h-40 list-disc space-y-0.5 overflow-y-auto pl-5">
                  {result.errors.slice(0, 50).map((error, index) => (
                    <li key={`${index}-${error}`}>{error}</li>
                  ))}
                </ul>
                {result.errors.length > 50 ? (
                  <p className="mt-1.5">…and {result.errors.length - 50} more.</p>
                ) : null}
              </div>
            ) : (
              <p className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="size-4" aria-hidden />
                Every row was processed.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-2">
            <label
              htmlFor={inputId}
              className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border border-dashed border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-6 text-center text-[13px] focus-within:ring-2 focus-within:ring-[var(--primary)] hover:border-[var(--primary)]"
            >
              <FileUp className="size-6 text-[var(--primary)]" aria-hidden />
              <span className="font-medium text-[var(--on-surface)]">
                {file ? file.name : "Choose a CSV file"}
              </span>
              <span className="text-[12px] text-[var(--on-surface-variant)]">
                {file ? `${(file.size / 1024).toFixed(0)} KB` : "Click to browse"}
              </span>
              <input
                id={inputId}
                type="file"
                accept=".csv,text/csv"
                className="sr-only"
                onChange={(event) => pick(event.target.files?.[0] ?? null)}
              />
            </label>
            {localError ? (
              <p role="alert" className="text-[13px] text-destructive">
                {localError}
              </p>
            ) : null}
          </div>
        )}

        <DialogFooter>
          {result ? (
            <>
              <Button variant="outline" onClick={reset}>
                Import another file
              </Button>
              <Button onClick={() => close(false)}>Done</Button>
            </>
          ) : (
            <>
              <Button variant="outline" onClick={() => close(false)} disabled={upload.isPending}>
                Cancel
              </Button>
              <Button
                onClick={() => file && upload.mutate(file)}
                disabled={!file || upload.isPending}
              >
                {upload.isPending ? "Importing…" : "Import"}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
