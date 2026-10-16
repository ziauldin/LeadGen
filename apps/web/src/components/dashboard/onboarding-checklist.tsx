"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronDown, Circle, Rocket } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ButtonLink } from "@/components/ui/button-link";
import { ErrorState } from "@/components/shared/loading-error";
import { authApi, workspacesApi } from "@/lib/api/endpoints";
import type { Onboarding } from "@/lib/api/types";
import { cn } from "@/lib/utils";

type StepKey = Exclude<keyof Onboarding, "completed">;

type Step = {
  key: StepKey;
  title: string;
  description: string;
  links?: { href: string; label: string }[];
  resend?: boolean;
};

export const ONBOARDING_STEPS: Step[] = [
  {
    key: "email_verified",
    title: "Verify your email address",
    description: "Open the link we emailed you. You need it to approve and send emails.",
    resend: true,
  },
  {
    key: "sender_profile",
    title: "Add your sender details",
    description: "Your name, company and postal address appear in every email footer.",
    links: [{ href: "/settings/workspace", label: "Add sender details" }],
  },
  {
    key: "sending_provider",
    title: "Connect an email provider",
    description: "Choose the service that sends your approved emails.",
    links: [{ href: "/settings/providers", label: "Connect provider" }],
  },
  {
    key: "niche_created",
    title: "Create a niche",
    description: "Describe the market you want to reach so we can suggest searches.",
    links: [{ href: "/niches/new", label: "Create niche" }],
  },
  {
    key: "leads_added",
    title: "Add your first leads",
    description: "Search your niche for people, or import a CSV you already have.",
    links: [
      { href: "/search", label: "Find leads" },
      { href: "/leads", label: "Import CSV" },
    ],
  },
  {
    key: "campaign_created",
    title: "Create a campaign",
    description: "Set up a sequence. Every email waits for your approval before it's sent.",
    links: [{ href: "/campaigns/new", label: "Create campaign" }],
  },
];

/** Getting-started steps for a new workspace. Renders nothing once everything is done. */
export function OnboardingChecklist() {
  const [open, setOpen] = useState(true);
  const onboarding = useQuery({
    queryKey: ["onboarding"],
    queryFn: workspacesApi.onboarding,
  });
  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => toast.success("Verification email sent. Check your inbox."),
  });

  if (onboarding.isLoading) return null;
  if (onboarding.error) {
    return (
      <div className="mb-6">
        <ErrorState
          message="Couldn't load your setup checklist."
          onRetry={() => onboarding.refetch()}
        />
      </div>
    );
  }
  const status = onboarding.data;
  if (!status || status.completed) return null;

  const done = ONBOARDING_STEPS.filter((step) => status[step.key]).length;
  const total = ONBOARDING_STEPS.length;
  const nextStep = ONBOARDING_STEPS.find((step) => !status[step.key]);

  return (
    <section
      aria-labelledby="onboarding-title"
      className="mb-6 rounded-lg border border-[var(--outline-variant)] bg-white shadow-sm"
    >
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center">
        <span
          className="hidden size-10 shrink-0 items-center justify-center rounded-lg bg-[var(--primary-fixed)] sm:flex"
          aria-hidden
        >
          <Rocket className="size-5 text-[var(--primary)]" />
        </span>
        <div className="min-w-0 flex-1">
          <h3 id="onboarding-title" className="text-[16px] font-semibold text-[var(--on-surface)]">
            Get set up
          </h3>
          <p className="text-[13px] text-[var(--on-surface-variant)]">
            {done} of {total} steps done
            {nextStep ? ` · Next: ${nextStep.title.toLowerCase()}` : ""}
          </p>
          <div
            role="progressbar"
            aria-label="Setup progress"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={done}
            className="mt-2 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-[var(--surface-container-high)]"
          >
            <div
              className="h-full rounded-full bg-[var(--primary)] transition-[width]"
              style={{ width: `${(done / total) * 100}%` }}
            />
          </div>
        </div>
        <ButtonLink href="/onboarding" size="sm" className="self-start sm:self-center">
          Open setup guide
        </ButtonLink>
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-controls="onboarding-steps"
          onClick={() => setOpen((value) => !value)}
          className="self-start sm:self-center"
        >
          {open ? "Hide steps" : "Show steps"}
          <ChevronDown className={cn("transition-transform", open && "rotate-180")} aria-hidden />
        </Button>
      </div>

      {open ? (
        <ol id="onboarding-steps" className="divide-y divide-[var(--outline-variant)] border-t border-[var(--outline-variant)]">
          {ONBOARDING_STEPS.map((step) => {
            const complete = status[step.key];
            return (
              <li
                key={step.key}
                className="flex flex-col gap-3 px-5 py-3.5 sm:flex-row sm:items-center"
                data-complete={complete}
              >
                <div className="flex min-w-0 flex-1 items-start gap-3">
                  {complete ? (
                    <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-emerald-600" aria-hidden />
                  ) : (
                    <Circle className="mt-0.5 size-5 shrink-0 text-[var(--on-surface-variant)]" aria-hidden />
                  )}
                  <div className="min-w-0">
                    <p
                      className={cn(
                        "text-[13px] font-medium",
                        complete
                          ? "text-[var(--on-surface-variant)] line-through"
                          : "text-[var(--on-surface)]",
                      )}
                    >
                      {step.title}
                      <span className="sr-only">{complete ? " (done)" : " (to do)"}</span>
                    </p>
                    {!complete ? (
                      <p className="text-[12px] text-[var(--on-surface-variant)]">
                        {step.description}
                      </p>
                    ) : null}
                  </div>
                </div>
                {!complete ? (
                  <div className="flex flex-wrap gap-2 pl-8 sm:pl-0">
                    {step.resend ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resend.mutate()}
                        disabled={resend.isPending || resend.isSuccess}
                      >
                        {resend.isPending
                          ? "Sending…"
                          : resend.isSuccess
                            ? "Email sent"
                            : "Resend verification email"}
                      </Button>
                    ) : null}
                    {step.links?.map((link, index) => (
                      <ButtonLink
                        key={link.href}
                        size="sm"
                        variant={index === 0 ? "default" : "outline"}
                        href={link.href}
                      >
                        {link.label}
                      </ButtonLink>
                    ))}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      ) : null}
    </section>
  );
}
