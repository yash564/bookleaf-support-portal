"use client";

import type { ReactNode } from "react";
import { RequireRole } from "@/lib/auth";
import { AppShell } from "./app-shell";
import type { Role } from "@/lib/types";

/** Role-gated shell used by the /author and /admin layouts. */
export function PortalGate({ role, children }: { role: Role; children: ReactNode }) {
  return (
    <RequireRole role={role}>
      <AppShell>{children}</AppShell>
    </RequireRole>
  );
}
