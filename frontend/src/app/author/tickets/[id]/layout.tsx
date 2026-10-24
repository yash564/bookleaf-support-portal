import type { ReactNode } from "react";

// Ticket pages are rendered entirely from client state (session + live data); nothing to prerender.
export const instant = false;

export default function TicketLayout({ children }: { children: ReactNode }) {
  return children;
}
