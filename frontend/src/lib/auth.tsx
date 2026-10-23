"use client";

/** Session = JWT in localStorage + the /auth/me profile. Role gating happens in <RequireRole>. */

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, tokenStore, UNAUTHORIZED_EVENT } from "./api";
import type { Role, User } from "./types";

type Status = "loading" | "anon" | "authed";

interface AuthCtx {
  user: User | null;
  status: Status;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export const homeFor = (role: Role) => (role === "ADMIN" ? "/admin/tickets" : "/author/books");

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  // No token → nothing to restore; skip the "loading" state entirely (server render also lands here).
  const [status, setStatus] = useState<Status>(() => (tokenStore.get() ? "loading" : "anon"));

  useEffect(() => {
    let cancelled = false;
    if (!tokenStore.get()) return;
    api.auth
      .me()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
        setStatus("authed");
      })
      .catch(() => {
        if (cancelled) return;
        tokenStore.clear();
        setStatus("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const onUnauthorized = () => {
      setUser(null);
      setStatus("anon");
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.auth.login(email, password);
    tokenStore.set(res.access_token);
    setUser(res.user);
    setStatus("authed");
    return res.user;
  }, []);

  const logout = useCallback(() => {
    api.auth.logout().catch(() => {});
    tokenStore.clear();
    setUser(null);
    setStatus("anon");
  }, []);

  return <Ctx.Provider value={{ user, status, login, logout }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Renders children only for the given role; otherwise redirects to login or the user's own home. */
export function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "anon") router.replace("/login");
    else if (status === "authed" && user && user.role !== role) router.replace(homeFor(user.role));
  }, [status, user, role, router]);

  if (status !== "authed" || !user || user.role !== role) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-slate-500">Loading your workspace…</div>
    );
  }
  return <>{children}</>;
}
