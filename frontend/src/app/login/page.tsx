"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Button, Field, Input } from "@/components/ui";

const DEMO = [
  { label: "Author · Priya Sharma (2 books)", email: "priya.sharma@email.com", password: "password123" },
  { label: "Author · Kavita Deshmukh (book in production)", email: "kavita.deshmukh@email.com", password: "password123" },
  { label: "Admin · Aarav Mehta", email: "admin@bookleaf.com", password: "admin123" },
];

export default function LoginPage() {
  const { login, status, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (status === "authed" && user) router.replace(homeFor(user.role));
  }, [status, user, router]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email.trim(), password);
      router.replace(homeFor(u.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-lg bg-brand-700 text-sm font-bold text-white">BL</div>
          <h1 className="text-xl font-semibold text-slate-900">BookLeaf Support Portal</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in with your author or staff account.</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 rounded-lg bg-white p-6 shadow-sm ring-1 ring-slate-200">
          <Field label="Email" htmlFor="email">
            <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
          </Field>
          <Field label="Password" htmlFor="password">
            <Input id="password" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </Field>
          {error && <p className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>}
          <Button type="submit" className="w-full" loading={busy}>
            Sign in
          </Button>
        </form>
        <div className="mt-5 rounded-lg border border-dashed border-slate-300 p-4">
          <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">Demo accounts (click to fill)</div>
          <div className="flex flex-col gap-1.5">
            {DEMO.map((d) => (
              <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword(d.password); }} className="rounded-md px-2 py-1.5 text-left text-sm text-slate-700 hover:bg-slate-100">
                {d.label} <span className="text-slate-400">· {d.email}</span>
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-slate-500">All 10 dataset authors log in with their dataset email and <code>password123</code>.</p>
        </div>
      </div>
    </div>
  );
}
