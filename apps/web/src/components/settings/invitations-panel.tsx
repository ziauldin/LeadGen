"use client";

import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { MailPlus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfirmDialog } from "@/components/shared/confirm-dialog";
import { ErrorState, LoadingState } from "@/components/shared/loading-error";
import { Field, SettingsCard, formatDate } from "@/components/settings/settings-card";
import { ROLE_LABELS } from "@/components/settings/members-table";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api/client";
import { workspacesApi } from "@/lib/api/endpoints";
import type { Invitation } from "@/lib/api/types";

const inviteSchema = z.object({
  email: z.string().trim().min(1, "Enter an email address").email("Enter a valid email address"),
  role: z.enum(["admin", "member"]),
});
type InviteValues = z.infer<typeof inviteSchema>;
const INVITE_ROLES = { member: ROLE_LABELS.member, admin: ROLE_LABELS.admin };

export function InvitationsPanel() {
  const queryClient = useQueryClient();
  const { isVerified } = useAuth();
  const [revokeTarget, setRevokeTarget] = useState<Invitation | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);

  const invitations = useQuery({ queryKey: ["invitations"], queryFn: workspacesApi.invitations });

  const form = useForm<InviteValues>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { email: "", role: "member" },
  });

  const invite = useMutation({
    mutationFn: (values: InviteValues) => workspacesApi.invite(values.email, values.role),
    meta: { silent: true },
    onSuccess: (invitation) => {
      setInviteError(null);
      void queryClient.invalidateQueries({ queryKey: ["invitations"] });
      form.reset({ email: "", role: form.getValues("role") });
      toast.success(`Invitation sent to ${invitation.email}`);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 403 && !isVerified) {
        setInviteError("Verify your email address before inviting people.");
      } else {
        setInviteError(error.message);
      }
    },
  });

  const revoke = useMutation({
    mutationFn: (id: number) => workspacesApi.revokeInvitation(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["invitations"] });
      toast.success("Invitation revoked");
      setRevokeTarget(null);
    },
  });

  const errors = form.formState.errors;
  const pending = invitations.data ?? [];

  return (
    <SettingsCard
      id="invitations"
      title="Invite people"
      description="We email them a link that's valid for 7 days. They join with the role you choose."
    >
      {!isVerified ? (
        <p className="mb-4 rounded-md bg-[var(--tertiary-fixed)] px-3 py-2 text-[12px] text-[var(--on-tertiary-fixed)]">
          Verify your email address to invite people. Check your inbox for the verification link.
        </p>
      ) : null}

      <form
        onSubmit={form.handleSubmit((values) => invite.mutate(values))}
        className="flex flex-col gap-3 sm:flex-row sm:items-start"
        noValidate
      >
        <Field
          label="Email address"
          htmlFor="invite-email"
          error={errors.email?.message}
          className="flex-1"
        >
          <Input
            id="invite-email"
            type="email"
            autoComplete="off"
            placeholder="colleague@company.com"
            className="h-9 bg-white"
            disabled={!isVerified}
            aria-invalid={Boolean(errors.email)}
            aria-describedby={errors.email ? "invite-email-error" : undefined}
            {...form.register("email")}
          />
        </Field>
        <Field label="Role" htmlFor="invite-role" className="sm:w-36">
          <Controller
            control={form.control}
            name="role"
            render={({ field }) => (
              <Select
                value={field.value}
                items={INVITE_ROLES}
                onValueChange={(value) => value && field.onChange(value)}
                disabled={!isVerified}
              >
                <SelectTrigger id="invite-role" className="h-9 w-full bg-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent alignItemWithTrigger={false}>
                  <SelectItem value="member">Member</SelectItem>
                  <SelectItem value="admin">Admin</SelectItem>
                </SelectContent>
              </Select>
            )}
          />
        </Field>
        <Button type="submit" className="h-9 sm:mt-[26px]" disabled={!isVerified || invite.isPending}>
          <MailPlus aria-hidden />
          {invite.isPending ? "Sending…" : "Send invite"}
        </Button>
      </form>
      {inviteError ? (
        <p role="alert" className="mt-3 rounded-md bg-[var(--error-container)] px-3 py-2 text-[13px] text-[var(--on-error-container)]">
          {inviteError}
        </p>
      ) : null}
      <p className="mt-2 text-[12px] text-[var(--on-surface-variant)]">
        To make someone an owner, invite them as an admin and change their role once they&apos;ve joined.
      </p>

      <div className="mt-6">
        <h3 className="mb-2 text-[14px] font-semibold text-[var(--on-surface)]">
          Pending invitations{pending.length ? ` (${pending.length})` : ""}
        </h3>
        {invitations.isLoading ? (
          <LoadingState message="Loading invitations…" />
        ) : invitations.error ? (
          <ErrorState error={invitations.error} onRetry={() => void invitations.refetch()} />
        ) : pending.length === 0 ? (
          <p className="rounded-md border border-dashed border-[var(--outline-variant)] p-4 text-center text-[13px] text-[var(--on-surface-variant)]">
            No pending invitations.
          </p>
        ) : (
          <ul className="divide-y divide-[var(--outline-variant)] rounded-lg border border-[var(--outline-variant)]">
            {pending.map((invitation) => (
              <li key={invitation.id} className="flex items-center gap-3 px-3 py-2.5 text-[13px]">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium text-[var(--on-surface)]">{invitation.email}</p>
                  <p className="text-[12px] text-[var(--on-surface-variant)]">
                    {ROLE_LABELS[invitation.role]} · sent {formatDate(invitation.created_at)} · expires{" "}
                    {formatDate(invitation.expires_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-label={`Revoke invitation for ${invitation.email}`}
                  onClick={() => setRevokeTarget(invitation)}
                >
                  <X aria-hidden />
                  <span className="hidden sm:inline">Revoke</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={revokeTarget !== null}
        onOpenChange={(open) => !open && setRevokeTarget(null)}
        title="Revoke this invitation?"
        description={`The link sent to ${revokeTarget?.email ?? "them"} will stop working.`}
        confirmLabel="Revoke invitation"
        destructive
        loading={revoke.isPending}
        onConfirm={() => revokeTarget && revoke.mutate(revokeTarget.id)}
      />
    </SettingsCard>
  );
}
