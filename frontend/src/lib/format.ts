import type { AiStatus, TicketCategory, TicketPriority, TicketStatus } from "./types";

export const inr = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined || v === "") return "—";
  const n = typeof v === "string" ? Number(v) : v;
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
};

export const fmtDate = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }) : "—";

export const relTime = (iso: string): string => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  const m = s / 60;
  if (m < 60) return `${Math.floor(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.floor(h)}h ago`;
  const d = h / 24;
  if (d < 30) return `${Math.floor(d)}d ago`;
  return fmtDate(iso);
};

/** Age in whole hours/days, for the admin queue's "waiting" column. */
export const ageOf = (iso: string): string => {
  const h = (Date.now() - new Date(iso).getTime()) / 36e5;
  return h < 24 ? `${Math.max(1, Math.round(h))}h` : `${Math.floor(h / 24)}d`;
};

export const fmtBytes = (b: number | null): string => {
  if (b === null) return "";
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(0)} KB`;
  return `${(b / 1024 / 1024).toFixed(1)} MB`;
};

export const STATUS_LABEL: Record<TicketStatus, string> = {
  OPEN: "Open",
  IN_PROGRESS: "In progress",
  RESOLVED: "Resolved",
  CLOSED: "Closed",
};
export const STATUSES: TicketStatus[] = ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"];

export const PRIORITY_LABEL: Record<TicketPriority, string> = { CRITICAL: "Critical", HIGH: "High", MEDIUM: "Medium", LOW: "Low" };
export const PRIORITIES: TicketPriority[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

export const CATEGORY_LABEL: Record<TicketCategory, string> = {
  ROYALTY_PAYMENTS: "Royalty & Payments",
  ISBN_METADATA: "ISBN & Metadata Issues",
  PRINTING_QUALITY: "Printing & Quality",
  DISTRIBUTION_AVAILABILITY: "Distribution & Availability",
  BOOK_STATUS_PRODUCTION: "Book Status & Production Updates",
  GENERAL_INQUIRY: "General Inquiry",
};
export const CATEGORIES = Object.keys(CATEGORY_LABEL) as TicketCategory[];

export const AI_STATUS_LABEL: Record<AiStatus, string> = {
  PENDING: "Classifying…",
  DONE: "AI classified",
  FALLBACK: "Rule-based (AI was unavailable)",
  SKIPPED: "Rule-based (AI disabled)",
};

export type Tone = "neutral" | "info" | "success" | "warning" | "danger" | "brand";

export const statusTone: Record<TicketStatus, Tone> = { OPEN: "info", IN_PROGRESS: "warning", RESOLVED: "success", CLOSED: "neutral" };
export const priorityTone: Record<TicketPriority, Tone> = { CRITICAL: "danger", HIGH: "warning", MEDIUM: "info", LOW: "neutral" };
