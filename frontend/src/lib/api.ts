/** The only place the frontend talks HTTP. Typed wrappers over the REST API + the error envelope. */

import type {
  AdminTicket,
  AdminTicketUpdate,
  AiUsage,
  BooksResponse,
  DraftOut,
  ListResponse,
  LoginResponse,
  MessageKind,
  QueueFilters,
  QueueStats,
  Ticket,
  TicketCreate,
  TicketListItem,
  TicketStatus,
  User,
} from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const TOKEN_KEY = "bookleaf.token";
export const UNAUTHORIZED_EVENT = "bookleaf:unauthorized";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { field?: string; message?: string }[] | Record<string, unknown> | null,
    public requestId?: string | null,
  ) {
    super(message);
  }
  /** Map field-level validation details to a {field: message} object for forms. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    if (Array.isArray(this.details)) {
      for (const d of this.details) if (d.field && d.message) out[d.field] = d.message;
    }
    return out;
  }
}

export const tokenStore = {
  get: (): string | null => {
    try {
      return typeof window === "undefined" ? null : window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set: (t: string) => {
    try {
      window.localStorage.setItem(TOKEN_KEY, t);
    } catch {}
  },
  clear: () => {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {}
  },
};

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

function buildQuery(q?: Query): string {
  if (!q) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === "") continue;
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x));
    else p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

async function request<T>(path: string, opts: { method?: string; body?: unknown; query?: Query; auth?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  const token = tokenStore.get();
  if (token && opts.auth !== false) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}${buildQuery(opts.query)}`, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body === undefined ? undefined : JSON.stringify(opts.body),
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Can't reach the BookLeaf API. Check your connection and try again.");
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!res.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: ApiError["details"]; request_id?: string } } | null)?.error;
    if (res.status === 401 && opts.auth !== false && typeof window !== "undefined") {
      tokenStore.clear();
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new ApiError(res.status, err?.code ?? "HTTP_ERROR", err?.message ?? `Request failed (${res.status})`, err?.details, err?.request_id);
  }
  return data as T;
}

/** EventSource can't set headers, so SSE endpoints take the JWT as a query param (documented in the API). */
export function sseUrl(path: string): string | null {
  const token = tokenStore.get();
  return token ? `${API_URL}${path}?token=${encodeURIComponent(token)}` : null;
}

export const api = {
  auth: {
    login: (email: string, password: string) => request<LoginResponse>("/api/v1/auth/login", { method: "POST", body: { email, password }, auth: false }),
    me: () => request<User>("/api/v1/auth/me"),
    logout: () => request<void>("/api/v1/auth/logout", { method: "POST" }),
  },
  author: {
    books: () => request<BooksResponse>("/api/v1/books"),
    tickets: (status?: TicketStatus | "") => request<ListResponse<TicketListItem>>("/api/v1/tickets", { query: { status } }),
    ticket: (id: string) => request<Ticket>(`/api/v1/tickets/${id}`),
    createTicket: (payload: TicketCreate) => request<Ticket>("/api/v1/tickets", { method: "POST", body: payload }),
    reply: (id: string, body: string) => request<Ticket>(`/api/v1/tickets/${id}/messages`, { method: "POST", body: { body } }),
  },
  admin: {
    queue: (f: QueueFilters) => request<ListResponse<TicketListItem>>("/api/v1/admin/tickets", { query: { ...f } }),
    stats: () => request<QueueStats>("/api/v1/admin/tickets/stats"),
    ticket: (id: string) => request<AdminTicket>(`/api/v1/admin/tickets/${id}`),
    update: (id: string, patch: AdminTicketUpdate) => request<AdminTicket>(`/api/v1/admin/tickets/${id}`, { method: "PATCH", body: patch }),
    message: (id: string, kind: MessageKind, body: string) =>
      request<AdminTicket>(`/api/v1/admin/tickets/${id}/messages`, { method: "POST", body: { kind, body } }),
    draft: (id: string, regenerate = false) => request<DraftOut>(`/api/v1/admin/tickets/${id}/ai-draft`, { method: "POST", query: { regenerate } }),
    classify: (id: string) => request<AdminTicket>(`/api/v1/admin/tickets/${id}/ai-classify`, { method: "POST" }),
    users: () => request<User[]>("/api/v1/admin/users"),
    usage: () => request<AiUsage>("/api/v1/admin/ai/usage"),
  },
};
