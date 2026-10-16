"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import * as Sentry from "@sentry/nextjs";
import { useQueryClient } from "@tanstack/react-query";
import {
  endImpersonation,
  getErrorMessage,
  getImpersonation,
  refreshAccessToken,
  setAccessToken,
  setSessionExpiredHandler,
  setWorkspaceId,
} from "@/lib/api/client";
import { authApi } from "@/lib/api/endpoints";
import type { User } from "@/lib/api/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  isVerified: boolean;
  /** Resolves to an MFA token when a two-factor code is still needed. */
  login: (
    email: string,
    password: string,
    next?: string | null,
    captchaToken?: string | null,
  ) => Promise<{ mfaToken: string } | void>;
  completeTwoFactor: (mfaToken: string, code: string, next?: string | null) => Promise<void>;
  register: (
    name: string,
    email: string,
    password: string,
    next?: string | null,
    captchaToken?: string | null,
  ) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

/** Only follow same-site relative redirects after sign-in. */
export function safeNext(next?: string | null): string {
  if (next && next.startsWith("/") && !next.startsWith("//")) return next;
  return "/dashboard";
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const me = await authApi.me();
      setUser(me);
      Sentry.setUser({ id: String(me.id) });
    } catch {
      setUser(null);
      Sentry.setUser(null);
    }
  }, []);

  // Restore the session from the refresh cookie on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshAccessToken();
      if (!cancelled && token) await refreshUser();
      if (!cancelled) setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [refreshUser]);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      setAccessToken(null);
      queryClient.clear();
      const next = encodeURIComponent(window.location.pathname + window.location.search);
      router.replace(`/login?next=${next}`);
    });
    return () => setSessionExpiredHandler(null);
  }, [queryClient, router]);

  const finishSignIn = useCallback(
    async (accessToken: string | null | undefined, next?: string | null) => {
      setAccessToken(accessToken ?? null);
      queryClient.clear();
      await refreshUser();
      router.push(safeNext(next));
    },
    [queryClient, refreshUser, router],
  );

  const login = useCallback(
    async (email: string, password: string, next?: string | null, captchaToken?: string | null) => {
      const result = await authApi.login({ email, password, captcha_token: captchaToken });
      if (result.mfa_required && result.mfa_token) return { mfaToken: result.mfa_token };
      await finishSignIn(result.access_token, next);
    },
    [finishSignIn],
  );

  const completeTwoFactor = useCallback(
    async (mfaToken: string, code: string, next?: string | null) => {
      const result = await authApi.loginTwoFactor(mfaToken, code);
      await finishSignIn(result.access_token, next);
    },
    [finishSignIn],
  );

  const register = useCallback(
    async (
      name: string,
      email: string,
      password: string,
      next?: string | null,
      captchaToken?: string | null,
    ) => {
      await authApi.register({ name, email, password, captcha_token: captchaToken });
      await login(email, password, next);
    },
    [login],
  );

  const logout = useCallback(async () => {
    if (getImpersonation()) {
      // Ending an impersonation session never signs the admin out.
      endImpersonation();
      queryClient.clear();
      window.location.assign("/admin/workspaces");
      return;
    }
    try {
      await authApi.logout();
    } catch {
      // Signing out locally is enough if the API is unreachable.
    }
    setAccessToken(null);
    setWorkspaceId(null);
    queryClient.clear();
    // A full navigation drops all in-memory state and avoids the auth guard adding ?next=.
    window.location.assign("/login");
  }, [queryClient]);

  const value = useMemo(
    () => ({
      user,
      loading,
      isVerified: Boolean(user?.email_verified_at),
      login,
      completeTwoFactor,
      register,
      logout,
      refreshUser,
    }),
    [user, loading, login, completeTwoFactor, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function getAuthErrorMessage(error: unknown) {
  return getErrorMessage(error);
}
