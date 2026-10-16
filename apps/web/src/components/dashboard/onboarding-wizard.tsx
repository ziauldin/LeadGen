"use client";

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Circle, PartyPopper } from "lucide-react";
import { ONBOARDING_STEPS } from "@/components/dashboard/onboarding-checklist";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { authApi, workspacesApi } from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

type WizardStep = {
  key: string;
  title: string;
  description: string;
  why: string;
  links?: { href: string; label: string }[];
  resend?: boolean;
  optional?: boolean;
};

const WHY: Record<string, string> = {
  email_verified: "We only let verified accounts approve and send emails, so nobody can send in your name.",
  sender_profile: "Anti-spam laws require your identity and a postal address in every commercial email.",
  sending_provider: "Emails go out through your own provider account, so your reputation is never shared.",
  niche_created: "A niche groups leads by market and powers search suggestions and reporting.",
  leads_added: "Each lead keeps where it came from and why you're contacting them.",
  campaign_created: "Campaigns turn leads into drafts that you review before anything is sent.",
};

const DELIVERABILITY: WizardStep = {
  key: "deliverability",
  title: "Check your domain's DNS",
  description: "Make sure SPF, DKIM and DMARC are set up for the domain you send from.",
  why: "Mailbox providers check these records to decide whether your email reaches the inbox.",
  links: [
    { href: "/settings/deliverability", label: "Run the check" },
    { href: "/help/deliverability", label: "How to set them up" },
  ],
  optional: true,
};

export function OnboardingWizard() {
  const onboarding = useQuery({ queryKey: ["onboarding"], queryFn: workspacesApi.onboarding, refetchOnWindowFocus: true });
  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => toast.success("Verification email sent. Check your inbox."),
  });
  const steps = useMemo<WizardStep[]>(() => {
    const base = ONBOARDING_STEPS.map((step) => ({ ...step, why: WHY[step.key] ?? "" }));
    // DNS comes right after connecting a provider.
    const at = base.findIndex((step) => step.key === "sending_provider") + 1;
    return [...base.slice(0, at), DELIVERABILITY, ...base.slice(at)];
  }, []);
  const [skipped, setSkipped] = useState<Set<string>>(new Set());
  const [active, setActive] = useState<string | null>(null);

  const status = onboarding.data as Record<string, boolean> | undefined;
  const done = (key: string) => Boolean(status?.[key]) || skipped.has(key);
  const firstOpen = steps.find((step) => !done(step.key))?.key ?? null;
  const current = steps.find((step) => step.key === (active ?? firstOpen));

  useEffect(() => {
    if (active && done(active) && !skipped.has(active)) setActive(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  if (onboarding.isLoading) return <LoadingState />;
  if (onboarding.error) return <ErrorState error={onboarding.error} onRetry={() => void onboarding.refetch()} />;

  const completed = steps.filter((step) => status?.[step.key]).length;
  const required = steps.filter((step) => !step.optional);
  const allDone = required.every((step) => status?.[step.key]);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-[24px] font-bold">Set up your workspace</h1>
        <p className="mt-1 text-[14px] text-[var(--on-surface-variant)]">
          {completed} of {steps.length} done. This takes about 15 minutes.
        </p>
        <div
          role="progressbar"
          aria-label="Setup progress"
          aria-valuemin={0}
          aria-valuemax={steps.length}
          aria-valuenow={completed}
          className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--surface-container-high)]"
        >
          <div className="h-full rounded-full bg-[var(--primary)] transition-[width]" style={{ width: `${(completed / steps.length) * 100}%` }} />
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-[260px_minmax(0,1fr)]">
        <ol aria-label="Setup steps" className="space-y-1">
          {steps.map((step, index) => {
            const isDone = Boolean(status?.[step.key]);
            const selected = current?.key === step.key;
            return (
              <li key={step.key}>
                <button
                  type="button"
                  onClick={() => setActive(step.key)}
                  aria-current={selected ? "step" : undefined}
                  className={cn(
                    "flex w-full items-start gap-2 rounded-lg px-3 py-2 text-left text-[13px]",
                    selected ? "bg-[var(--surface-container-high)] font-semibold" : "hover:bg-[var(--surface-container-low)]",
                  )}
                >
                  {isDone ? (
                    <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-[var(--primary)]" aria-label="Done" />
                  ) : (
                    <Circle className="mt-0.5 size-4 shrink-0 text-[var(--on-surface-variant)]" aria-label="Not done" />
                  )}
                  <span>
                    {index + 1}. {step.title}
                    {step.optional ? <span className="ml-1 font-normal text-[var(--on-surface-variant)]">(recommended)</span> : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>

        <section aria-live="polite" className="rounded-xl border border-[var(--outline-variant)] bg-white p-6">
          {allDone && !active ? (
            <div className="text-center">
              <PartyPopper className="mx-auto size-10 text-[var(--primary)]" aria-hidden />
              <h2 className="mt-3 text-[20px] font-semibold">You&apos;re ready to go</h2>
              <p className="mt-2 text-[14px] text-[var(--on-surface-variant)]">
                Add leads to your campaign to create drafts, then review them in Approvals.
              </p>
              <div className="mt-5 flex justify-center gap-2">
                <ButtonLink href="/approvals">Open approvals</ButtonLink>
                <ButtonLink href="/dashboard" variant="outline">
                  Go to dashboard
                </ButtonLink>
              </div>
            </div>
          ) : current ? (
            <div>
              <h2 className="text-[20px] font-semibold">{current.title}</h2>
              <p className="mt-2 text-[14px]">{current.description}</p>
              <p className="mt-3 rounded-md bg-[var(--surface-container-low)] px-3 py-2 text-[13px] text-[var(--on-surface-variant)]">
                <span className="font-medium text-[var(--on-surface)]">Why it matters: </span>
                {current.why}
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {status?.[current.key] ? (
                  <p className="flex items-center gap-1.5 text-[14px] font-medium text-[var(--primary)]">
                    <CheckCircle2 className="size-4" aria-hidden /> Done
                  </p>
                ) : (
                  <>
                    {current.links?.map((link, index) => (
                      <ButtonLink key={link.href} href={link.href} variant={index === 0 ? "default" : "outline"}>
                        {link.label}
                      </ButtonLink>
                    ))}
                    {current.resend ? (
                      <Button variant="outline" disabled={resend.isPending} onClick={() => resend.mutate()}>
                        Resend the email
                      </Button>
                    ) : null}
                  </>
                )}
                <Button
                  variant="ghost"
                  onClick={() => {
                    setSkipped((prev) => new Set(prev).add(current.key));
                    setActive(null);
                  }}
                >
                  {status?.[current.key] ? "Next step" : "Skip for now"}
                </Button>
              </div>
              <p className="mt-4 text-[12px] text-[var(--on-surface-variant)]">
                Steps are ticked off automatically when you come back to this page.
              </p>
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
