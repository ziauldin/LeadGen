"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Copy, Download, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { SettingsCard } from "@/components/settings/settings-card";
import { useAuth } from "@/hooks/use-auth";
import { authApi } from "@/lib/api/endpoints";
import { getErrorMessage } from "@/lib/api/client";

function RecoveryCodes({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const text = codes.join("\n");
  function download() {
    const url = URL.createObjectURL(new Blob([`LeadsGen recovery codes\n\n${text}\n`], { type: "text/plain" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "leadsgen-recovery-codes.txt";
    link.click();
    URL.revokeObjectURL(url);
  }
  return (
    <div className="space-y-4" role="region" aria-label="Recovery codes">
      <p className="text-[13px] text-[var(--on-surface)]">
        Save these recovery codes somewhere safe. Each one works once if you lose your phone. They
        won&apos;t be shown again.
      </p>
      <ul className="grid grid-cols-2 gap-2 rounded-lg border border-[var(--outline-variant)] bg-[var(--surface-container-low)] p-4 font-mono text-[13px] sm:grid-cols-3">
        {codes.map((code) => (
          <li key={code}>{code}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => void navigator.clipboard.writeText(text).then(() => toast.success("Copied"))}
        >
          <Copy aria-hidden /> Copy
        </Button>
        <Button variant="outline" size="sm" onClick={download}>
          <Download aria-hidden /> Download
        </Button>
        <Button size="sm" onClick={onDone}>
          I&apos;ve saved them
        </Button>
      </div>
    </div>
  );
}

export function TwoFactorCard() {
  const queryClient = useQueryClient();
  const { refreshUser } = useAuth();
  const status = useQuery({ queryKey: ["2fa"], queryFn: authApi.twoFactorStatus });
  const [setup, setSetup] = useState<{ secret: string; qr_code: string } | null>(null);
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[] | null>(null);
  const [disableOpen, setDisableOpen] = useState(false);
  const [regenOpen, setRegenOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [dialogCode, setDialogCode] = useState("");
  const [dialogError, setDialogError] = useState<string | null>(null);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["2fa"] });
    await refreshUser();
  };

  const start = useMutation({
    mutationFn: authApi.twoFactorSetup,
    onSuccess: (data) => {
      setSetup(data);
      setCode("");
    },
  });
  const enable = useMutation({
    mutationFn: () => authApi.twoFactorEnable(code.trim()),
    onSuccess: async (data) => {
      setCodes(data.recovery_codes);
      setSetup(null);
      await refresh();
      toast.success("Two-factor authentication is on");
    },
  });
  const disable = useMutation({
    mutationFn: () => authApi.twoFactorDisable(password, dialogCode.trim()),
    meta: { silent: true },
    onSuccess: async () => {
      setDisableOpen(false);
      await refresh();
      toast.success("Two-factor authentication is off");
    },
    onError: (error) => setDialogError(getErrorMessage(error)),
  });
  const regenerate = useMutation({
    mutationFn: () => authApi.regenerateRecoveryCodes(dialogCode.trim()),
    meta: { silent: true },
    onSuccess: async (data) => {
      setRegenOpen(false);
      setCodes(data.recovery_codes);
      await refresh();
    },
    onError: (error) => setDialogError(getErrorMessage(error)),
  });

  const enabled = status.data?.enabled;

  return (
    <SettingsCard
      id="two-factor"
      title="Two-factor authentication"
      description="Ask for a code from an authenticator app (Google Authenticator, 1Password, Authy…) when you sign in."
    >
      {codes ? (
        <RecoveryCodes codes={codes} onDone={() => setCodes(null)} />
      ) : enabled ? (
        <div className="space-y-4">
          <p className="flex items-center gap-2 text-[13px] font-medium text-emerald-700">
            <CheckCircle2 className="size-4" aria-hidden /> On · {status.data?.recovery_codes_left}{" "}
            recovery codes left
          </p>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" size="sm" onClick={() => { setDialogError(null); setDialogCode(""); setRegenOpen(true); }}>
              New recovery codes
            </Button>
            <Button variant="destructive" size="sm" onClick={() => { setDialogError(null); setDialogCode(""); setPassword(""); setDisableOpen(true); }}>
              Turn off
            </Button>
          </div>
        </div>
      ) : setup ? (
        <form
          className="grid gap-6 sm:grid-cols-[auto_1fr]"
          onSubmit={(event) => {
            event.preventDefault();
            enable.mutate();
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element -- data URI QR code */}
          <img src={setup.qr_code} alt="QR code to scan with your authenticator app" className="size-44 rounded border border-[var(--outline-variant)] bg-white" />
          <div className="space-y-3">
            <ol className="list-decimal space-y-1 pl-5 text-[13px] text-[var(--on-surface)]">
              <li>Scan the QR code with your authenticator app.</li>
              <li>
                Or enter this key by hand:{" "}
                <code className="break-all rounded bg-[var(--surface-container-low)] px-1.5 py-0.5 font-mono">
                  {setup.secret}
                </code>
              </li>
              <li>Type the 6-digit code it shows to finish.</li>
            </ol>
            <label htmlFor="totp-code" className="block text-[13px] font-medium">
              Code from your app
            </label>
            <div className="flex max-w-xs gap-2">
              <Input
                id="totp-code"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={code}
                onChange={(event) => setCode(event.target.value)}
                placeholder="123456"
              />
              <Button type="submit" disabled={code.trim().length < 6 || enable.isPending}>
                {enable.isPending ? "Checking…" : "Turn on"}
              </Button>
            </div>
            <Button type="button" variant="ghost" size="sm" onClick={() => setSetup(null)}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <p className="flex flex-1 items-center gap-2 text-[13px] text-[var(--on-surface-variant)]">
            <ShieldCheck className="size-4" aria-hidden /> Off. We strongly recommend turning it on.
          </p>
          <Button onClick={() => start.mutate()} disabled={start.isPending || status.isLoading}>
            {start.isPending ? "Preparing…" : "Set up two-factor"}
          </Button>
        </div>
      )}

      <ConfirmDialog
        open={disableOpen}
        onOpenChange={setDisableOpen}
        title="Turn off two-factor authentication?"
        description="Your account will only be protected by your password."
        confirmLabel="Turn off"
        destructive
        loading={disable.isPending}
        confirmDisabled={!password || dialogCode.trim().length < 6}
        onConfirm={() => disable.mutate()}
      >
        <div className="space-y-3">
          <Input type="password" aria-label="Password" placeholder="Password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} />
          <Input aria-label="Authentication or recovery code" placeholder="Code" autoComplete="one-time-code" value={dialogCode} onChange={(event) => setDialogCode(event.target.value)} />
          {dialogError && <p role="alert" className="text-[13px] text-destructive">{dialogError}</p>}
        </div>
      </ConfirmDialog>
      <ConfirmDialog
        open={regenOpen}
        onOpenChange={setRegenOpen}
        title="Create new recovery codes?"
        description="Your old recovery codes will stop working."
        confirmLabel="Create new codes"
        loading={regenerate.isPending}
        confirmDisabled={dialogCode.trim().length < 6}
        onConfirm={() => regenerate.mutate()}
      >
        <div className="space-y-3">
          <Input aria-label="Code from your authenticator app" placeholder="123456" inputMode="numeric" value={dialogCode} onChange={(event) => setDialogCode(event.target.value)} />
          {dialogError && <p role="alert" className="text-[13px] text-destructive">{dialogError}</p>}
        </div>
      </ConfirmDialog>
    </SettingsCard>
  );
}
