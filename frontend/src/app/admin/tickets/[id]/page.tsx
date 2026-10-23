"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Lock, Paperclip, RefreshCw, Sparkles, Wand2 } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useLiveEvents } from "@/lib/realtime";
import { AI_STATUS_LABEL, CATEGORIES, CATEGORY_LABEL, PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, fmtBytes, fmtDate, fmtDateTime, inr, priorityTone, statusTone } from "@/lib/format";
import type { AdminTicket, AdminTicketUpdate, Book, MessageKind } from "@/lib/types";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, ErrorNote, Field, LiveDot, Select, Spinner, Textarea, cx } from "@/components/ui";
import { Thread } from "@/components/thread";

export default function AdminTicketPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const { user } = useAuth();
  const key = ["admin", "ticket", id];

  const q = useQuery({ queryKey: key, queryFn: () => api.admin.ticket(id), refetchInterval: 30_000 });
  const admins = useQuery({ queryKey: ["admin", "users"], queryFn: api.admin.users });
  const { live } = useLiveEvents(`/api/v1/admin/tickets/${id}/events`, () => {
    qc.invalidateQueries({ queryKey: key });
    qc.invalidateQueries({ queryKey: ["admin", "tickets"] });
  });

  const afterChange = (t: AdminTicket) => {
    qc.setQueryData(key, t);
    qc.invalidateQueries({ queryKey: ["admin", "tickets"] });
    qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  };
  const fail = (title: string) => (e: unknown) => toast.push({ tone: "error", title, body: e instanceof Error ? e.message : "" });

  const update = useMutation({ mutationFn: (patch: AdminTicketUpdate) => api.admin.update(id, patch), onSuccess: afterChange, onError: fail("Update failed") });
  const reclassify = useMutation({ mutationFn: () => api.admin.classify(id), onSuccess: (t) => { afterChange(t); toast.push({ tone: "success", title: "Re-classified", body: `${CATEGORY_LABEL[t.category]} · ${PRIORITY_LABEL[t.priority]}` }); }, onError: fail("AI unavailable") });

  // ----- composer -----
  const [mode, setMode] = useState<MessageKind>("ADMIN_REPLY");
  // `null` = untouched: the composer shows the ticket's cached AI draft (if any) until the admin types.
  const [body, setBody] = useState<string | null>(null);
  const [fromAi, setFromAi] = useState(false);
  const [draftNote, setDraftNote] = useState<string | null>(null);
  const draft = useMutation({
    mutationFn: (regenerate: boolean) => api.admin.draft(id, regenerate),
    onSuccess: (d) => {
      setBody(d.draft);
      setFromAi(true);
      setMode("ADMIN_REPLY");
      setDraftNote(d.cached ? `Cached draft from ${fmtDateTime(d.generated_at)} (no tokens spent)` : `Fresh draft from ${d.model} · review before sending`);
      qc.invalidateQueries({ queryKey: key });
    },
    onError: (e) => {
      const msg = e instanceof ApiError && e.status === 503 ? "The AI assistant is unavailable right now (not configured, rate-limited or down). Write the reply manually." : e instanceof Error ? e.message : "";
      setDraftNote(null);
      toast.push({ tone: "error", title: "No AI draft", body: msg });
    },
  });
  const send = useMutation({
    mutationFn: (text: string) => api.admin.message(id, mode, text),
    onSuccess: (t) => { afterChange(t); setBody(""); setFromAi(false); setDraftNote(null); toast.push({ tone: "success", title: mode === "ADMIN_REPLY" ? "Reply sent to the author" : "Internal note added" }); },
    onError: fail("Couldn't send"),
  });

  if (q.isPending) return <Spinner />;
  if (q.error) return <ErrorNote error={q.error} />;
  const t = q.data;
  const book = t.book;
  const busy = update.isPending;
  const cachedDraft = t.status !== "CLOSED" ? t.ai_draft : null;
  const shown = body ?? cachedDraft ?? "";
  const aiBacked = fromAi || (body === null && !!cachedDraft);
  const note = draftNote ?? (body === null && cachedDraft ? `Cached draft from ${fmtDateTime(t.ai.draft_generated_at)}` : null);

  return (
    <div>
      <Link href="/admin/tickets" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="h-4 w-4" /> Queue</Link>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2"><span className="font-mono text-xs text-slate-400">#{t.number}</span><Badge tone={priorityTone[t.priority]}>{PRIORITY_LABEL[t.priority]}</Badge><Badge tone={statusTone[t.status]}>{STATUS_LABEL[t.status]}</Badge></div>
          <h1 className="mt-1 text-lg font-semibold text-slate-900">{t.subject}</h1>
          <div className="mt-0.5 text-xs text-slate-500">{t.author?.name} · {book ? book.title : "General / Account"} · raised {fmtDateTime(t.created_at)}</div>
        </div>
        <div className="flex items-center gap-2">
          <LiveDot live={live} />
          {t.assigned_to?.id !== user?.id && t.status !== "CLOSED" && <Button size="sm" variant="secondary" loading={busy} onClick={() => update.mutate({ assigned_to_id: user!.id })}>Assign to me</Button>}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        {/* ---------- left: conversation + composer ---------- */}
        <div className="space-y-4">
          <Card>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{t.description}</p>
            {t.attachments.length > 0 && (
              <ul className="mt-3 flex flex-wrap gap-2">{t.attachments.map((a) => <li key={a.id} className="flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600"><Paperclip className="h-3 w-3" /> {a.filename} <span className="text-slate-400">{fmtBytes(a.size_bytes)}</span></li>)}</ul>
            )}
          </Card>

          <Thread messages={t.messages} viewer="ADMIN" emptyText="No replies yet." />

          <Card
            title={
              <span className="flex gap-1">
                {(["ADMIN_REPLY", "INTERNAL_NOTE"] as const).map((k) => (
                  <button key={k} onClick={() => setMode(k)} className={cx("rounded-md px-2.5 py-1 text-xs font-medium", mode === k ? (k === "INTERNAL_NOTE" ? "bg-amber-100 text-amber-900" : "bg-brand-50 text-brand-800") : "text-slate-500 hover:bg-slate-100")}>
                    {k === "ADMIN_REPLY" ? "Reply to author" : <span className="flex items-center gap-1"><Lock className="h-3 w-3" /> Internal note</span>}
                  </button>
                ))}
              </span>
            }
            action={
              mode === "ADMIN_REPLY" && (
                <div className="flex gap-1">
                  <Button size="sm" variant="secondary" loading={draft.isPending} onClick={() => draft.mutate(false)} title="Generate (or load the cached) AI draft">
                    <Sparkles className="h-3.5 w-3.5" /> AI draft
                  </Button>
                  {t.ai_draft && (
                    <Button size="sm" variant="ghost" loading={draft.isPending} onClick={() => draft.mutate(true)} title="Spend tokens on a fresh draft">
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              )
            }
          >
            {aiBacked && mode === "ADMIN_REPLY" && (
              <div className="mb-2 flex items-center gap-2 rounded-md bg-violet-50 px-3 py-1.5 text-xs text-violet-800 ring-1 ring-inset ring-violet-200">
                <Wand2 className="h-3.5 w-3.5" /> AI draft grounded in the knowledge base and this author&apos;s data. {note} — edit freely before sending.
              </div>
            )}
            <Textarea rows={9} value={shown} onChange={(e) => setBody(e.target.value)} placeholder={mode === "ADMIN_REPLY" ? "Write to the author, or click “AI draft”…" : "Private note for the team (never shown to the author)"} className={mode === "INTERNAL_NOTE" ? "bg-amber-50/40" : ""} maxLength={5000} />
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span>{mode === "ADMIN_REPLY" ? "Sending a reply moves the ticket to In progress and assigns it to you if unowned." : "Internal notes are visible to staff only."}</span>
              <Button loading={send.isPending} disabled={!shown.trim() || t.status === "CLOSED"} onClick={() => send.mutate(shown)} variant={mode === "INTERNAL_NOTE" ? "secondary" : "primary"}>
                {mode === "ADMIN_REPLY" ? "Send reply" : "Add note"}
              </Button>
            </div>
          </Card>
        </div>

        {/* ---------- right: triage + context ---------- */}
        <div className="space-y-4">
          <Card title="Triage" action={<Button size="sm" variant="ghost" loading={reclassify.isPending} onClick={() => reclassify.mutate()} title="Re-run AI classification"><RefreshCw className="h-3.5 w-3.5" /> Re-run AI</Button>}>
            <div className="space-y-3">
              <Field label="Status">
                <Select value={t.status} disabled={busy} onChange={(e) => update.mutate({ status: e.target.value as AdminTicket["status"] })}>
                  {STATUSES.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
                </Select>
              </Field>
              <Field label="Category" hint={t.ai.category && t.ai.category !== t.category ? `AI suggested ${CATEGORY_LABEL[t.ai.category]}` : undefined}>
                <Select value={t.category} disabled={busy} onChange={(e) => update.mutate({ category: e.target.value as AdminTicket["category"] })}>
                  {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
                </Select>
              </Field>
              <Field label="Priority" hint={t.ai.priority && t.ai.priority !== t.priority ? `AI suggested ${PRIORITY_LABEL[t.ai.priority]}` : undefined}>
                <Select value={t.priority} disabled={busy} onChange={(e) => update.mutate({ priority: e.target.value as AdminTicket["priority"] })}>
                  {PRIORITIES.map((p) => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
                </Select>
              </Field>
              <Field label="Assigned to">
                <Select value={t.assigned_to?.id ?? ""} disabled={busy || admins.isPending} onChange={(e) => update.mutate({ assigned_to_id: e.target.value || null })}>
                  <option value="">Unassigned</option>
                  {admins.data?.map((a) => <option key={a.id} value={a.id}>{a.name}{a.id === user?.id ? " (me)" : ""}</option>)}
                </Select>
              </Field>
              <div className="rounded-md bg-slate-50 p-3 text-xs">
                <div className="mb-1 flex items-center justify-between">
                  <span className="font-medium text-slate-700">{AI_STATUS_LABEL[t.ai.status]}</span>
                  {t.ai.confidence !== null && <Badge tone={t.ai.confidence >= 0.8 ? "success" : t.ai.confidence >= 0.5 ? "warning" : "danger"}>{Math.round(t.ai.confidence * 100)}% confident</Badge>}
                </div>
                {t.ai.reasoning && <p className="text-slate-600">{t.ai.reasoning}</p>}
                {(t.ai.category_overridden || t.ai.priority_overridden) && (
                  <p className="mt-1 text-amber-700">Admin override: {[t.ai.category_overridden && "category", t.ai.priority_overridden && "priority"].filter(Boolean).join(" & ")}.</p>
                )}
              </div>
            </div>
          </Card>

          <Card title="Author">
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Name</dt><dd className="font-medium">{t.author?.name}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Email</dt><dd className="truncate">{t.author?.email}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">City</dt><dd>{t.author?.city ?? "—"}</dd></div>
              <div className="flex justify-between gap-2"><dt className="text-slate-500">Author id</dt><dd className="font-mono text-xs">{t.author?.id}</dd></div>
            </dl>
          </Card>

          <Card title={book ? "Book" : "Scope"}>
            {t.book_detail ? (
              <BookFacts b={t.book_detail} />
            ) : (
              <p className="text-sm text-slate-600">General / account-level query — no specific book.</p>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

/** Real numbers from the database, so the admin can verify what the AI draft claims. */
function BookFacts({ b }: { b: Book }) {
  const pending = Number(b.royalty_pending);
  return (
    <dl className="space-y-1 text-sm">
      <div className="flex justify-between gap-2"><dt className="text-slate-500">Title</dt><dd className="text-right font-medium">{b.title}</dd></div>
      <div className="flex justify-between gap-2"><dt className="text-slate-500">Status</dt><dd className="text-right">{b.is_published ? <Badge tone="success">Published & Live</Badge> : <Badge tone="info">{b.status}</Badge>}</dd></div>
      {b.is_published ? (
        <>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">ISBN</dt><dd className="font-mono text-xs">{b.isbn}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Published</dt><dd>{fmtDate(b.publication_date)}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">MRP · royalty/copy</dt><dd>{inr(b.mrp)} · {inr(b.royalty_per_copy)}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Sold · earned</dt><dd>{b.copies_sold} · {inr(b.royalty_earned)}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Paid</dt><dd>{inr(b.royalty_paid)}{b.last_payout_date ? ` (last ${fmtDate(b.last_payout_date)})` : " (never)"}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Pending</dt><dd className={cx(pending > 0 && "font-medium text-amber-700")}>{inr(b.royalty_pending)}{pending > 0 && pending < 1000 ? " · below ₹1,000, rolls over" : ""}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-slate-500">Print partner</dt><dd>{b.print_partner ?? "In-House"}</dd></div>
          <div className="pt-1 text-xs text-slate-500">Listed on {b.available_on.length ? b.available_on.join(", ") : "no platforms yet"}</div>
        </>
      ) : (
        <p className="pt-1 text-xs text-slate-500">In production: no ISBN, MRP or sales yet.</p>
      )}
    </dl>
  );
}
