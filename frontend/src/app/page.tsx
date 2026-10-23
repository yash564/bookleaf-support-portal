"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { homeFor, useAuth } from "@/lib/auth";

export default function Home() {
  const { status, user } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (status === "anon") router.replace("/login");
    else if (status === "authed" && user) router.replace(homeFor(user.role));
  }, [status, user, router]);
  return <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">Loading…</div>;
}
