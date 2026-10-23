import type { ReactNode } from "react";
import { PortalGate } from "@/components/portal-gate";

// The portal is gated on a client-side session, so there is no static shell worth validating.
export const instant = false;

export default function AdminLayout({ children }: { children: ReactNode }) {
  return <PortalGate role="ADMIN">{children}</PortalGate>;
}
