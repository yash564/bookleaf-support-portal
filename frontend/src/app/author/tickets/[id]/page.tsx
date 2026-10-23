"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Paperclip } from "lucide-react";
import { api } from "@/lib/api";
import { useLiveEvents } from "@/lib/realtime";
import { STATUS_LABEL, fmtBytes, fmtDateTime, statusTone } from "@/lib/format";
import { useToast } from "@/components/toast";
import { Badge, Button, Card, ErrorNote, LiveDot, Spinner, Textarea } from "@/components/ui";
import { Thread } from "@/components/thread";

export default function AuthorTicketPage() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const toast = useToast();
  const [reply, setReply] = useState("");
  const q = useQuery({ queryKey: ["author", "ticket", id], queryFn: () => api.author.ticket(id), refetchInterval: 30_000 });
  const { live } = useLiveEvents(`/api/v1/tickets/${id}/events`, () => {
    qc.invalidateQueries({ queryKey: ["author", "ticket", id] });
    qc.invalidateQueries({ queryKey: ["author", "tickets"] });
  });
  const send = useMutation({
    mutationFn: () => api.author.reply(id, reply),
    onSuccess: (t) => {
      qc.setQueryData(["author", "ticket", id], t);
      setReply("");
    },
    onError: (e) => toast.push({ tone: "error", title: "Couldn't send", body: e instanceof Error ? e.message : "" }),
  });

  if (q.isPending) return <Spinner />;
  if (q.error) return <ErrorNote error={q.error} />;
  const t = q.data;
  const closed = t.status === "CLOSED";

  return (
    <div className="mx-auto max-w-3xl">
      <Link href="/author/tickets" className="mb-3 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800"><ArrowLeft className="h-4 w-4" /> My tickets</Link>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-xs font-mono text-slate-400">#{t.number}</div>
          <h1 className="text-lg font-semibold text-slate-900">{t.subject}</h1>
          <div className="mt-1 text-xs text-slate-500">{t.book ? t.book.title : "General / Account"} · {t.category_label} · raised {fmtDateTime(t.created_at)}</div>
        </div>
        <div className="flex items-center gap-2">
          <LiveDot live={live} />
          <Badge tone={statusTone[t.status]}>{STATUS_LABEL[t.status]}</Badge>
        </div>
      </div>

      <Card className="mb-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{t.description}</p>
        {t.attachments.length > 0 && (
          <ul className="mt-3 flex flex-wrap gap-2">
            {t.attachments.map((a) => (
              <li key={a.id} className="flex items-center gap-1 rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600"><Paperclip className="h-3 w-3" /> {a.filename} <span className="text-slate-400">{fmtBytes(a.size_bytes)}</span></li>
            ))}
          </ul>
        )}
      </Card>

      <Thread messages={t.messages} viewer="AUTHOR" emptyText={t.status === "OPEN" ? "No reply yet. Our team usually responds within 48 hours; you&apos;ll see it here without refreshing." : "No messages."} />

      <Card className="mt-4" title={closed ? "This ticket is closed" : t.status === "RESOLVED" ? "Resolved — still need help?" : "Add a follow-up"}>
        {closed ? (
          <p className="text-sm text-slate-600">Closed tickets can&apos;t be reopened. <Link href="/author/tickets/new" className="text-brand-700 underline">Raise a new query</Link> and reference #{t.number}.</p>
        ) : (
          <form onSubmit={(e) => { e.preventDefault(); if (reply.trim()) send.mutate(); }} className="space-y-3">
            <Textarea rows={4} value={reply} onChange={(e) => setReply(e.target.value)} placeholder={t.status === "RESOLVED" ? "Replying will reopen this ticket." : "Write your message…"} maxLength={5000} />
            <div className="flex justify-end"><Button type="submit" loading={send.isPending} disabled={!reply.trim()}>Send</Button></div>
          </form>
        )}
      </Card>
    </div>
  );
}
