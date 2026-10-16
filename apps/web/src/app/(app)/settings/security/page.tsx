import type { Metadata } from "next";
import { Suspense } from "react";
import { MfaRequiredNotice } from "@/components/settings/security/mfa-required-notice";
import {
  ChangePasswordCard,
  DeleteAccountCard,
  SessionsCard,
  WorkspaceTwoFactorPolicyCard,
} from "@/components/settings/security/account-security-cards";
import { SignInMethodsCard } from "@/components/settings/security/sign-in-methods-card";
import { TwoFactorCard } from "@/components/settings/security/two-factor-card";

export const metadata: Metadata = { title: "Security · Settings · LeadsGen" };

export default function SecuritySettingsPage() {
  return (
    <div className="space-y-6">
      <Suspense>
        <MfaRequiredNotice />
      </Suspense>
      <TwoFactorCard />
      <Suspense>
        <SignInMethodsCard />
      </Suspense>
      <SessionsCard />
      <ChangePasswordCard />
      <WorkspaceTwoFactorPolicyCard />
      <DeleteAccountCard />
    </div>
  );
}
