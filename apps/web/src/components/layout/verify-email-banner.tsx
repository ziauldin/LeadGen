"use client";

import { useMutation } from "@tanstack/react-query";
import { MailWarning } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/hooks/use-auth";
import { authApi } from "@/lib/api/endpoints";

/** Unverified users can look around but can't send, approve, invite or add credentials. */
export function VerifyEmailBanner() {
  const { user, isVerified } = useAuth();
  const resend = useMutation({
    mutationFn: authApi.resendVerification,
    onSuccess: () => toast.success("Verification email sent. Check your inbox."),
  });
  if (!user || isVerified) return null;

  return (
    <div
      role="status"
      className="mb-6 flex flex-col gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-[13px] text-amber-900 sm:flex-row sm:items-center"
    >
      <MailWarning className="size-4 shrink-0" aria-hidden />
      <p className="flex-1">
        Confirm your email address ({user.email}) to approve and send emails, invite teammates and
        connect providers.
      </p>
      <button
        type="button"
        onClick={() => resend.mutate()}
        disabled={resend.isPending}
        className="self-start rounded-md border border-amber-400 px-3 py-1 font-medium hover:bg-amber-100 disabled:opacity-60 sm:self-auto"
      >
        {resend.isPending ? "Sending…" : "Resend email"}
      </button>
    </div>
  );
}
