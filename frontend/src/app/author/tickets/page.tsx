"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { useLiveEvents } from "@/lib/realtime";
import { PRIORITY_LABEL, STATUSES, STATUS_LABEL, priorityTone, relTime, statusTone } from "@/lib/format";
import type { TicketStatus } from "@/lib/types";
import { Badge, Button, EmptyState, ErrorNote, LiveDot, PageHeader, Spinner, cx } from "@/components/ui";

export default function MyTicketsPage() {
  const [status, setStatus] = useState<TicketStatus | "">("");
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["author", "tickets", status], queryFn: () => api.author.tickets(status), refetchInterval: 30_000 });
  const { live } = useLiveEvents("/api/v1/tickets/events/stream", () => qc.invalidateQueries({ queryKey: ["author", "tickets"] }));

  return (
    <>
      <PageHeader title="My Tickets" subtitle={<span className="flex items-center gap-3">Every query you&apos;ve raised, with replies from the BookLeaf team. <LiveDot live={live} /></span>} action={<Link href="/author/tickets/new"><Button>New query</Button></Link>} />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {(["", ...STATUSES] as const).map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={cx("rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", status === s ? "bg-brand-700 text-white ring-brand-700" : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50")}>
            {s === "" ? "All" : STATUS_LABEL[s]}
          </button>
        ))}
      </div>
      {q.isPending ? (
        <Spinner />
      ) : q.error ? (
        <ErrorNote error={q.error} />
      ) : q.data.items.length === 0 ? (
        <EmptyState icon={<Inbox className="h-8 w-8" />} title={status ? `No ${STATUS_LABEL[status].toLowerCase()} tickets` : "You haven't raised any queries yet"} body="Questions about royalties, ISBNs, printing or distribution? We typically reply within 48 hours." action={<Link href="/author/tickets/new"><Button variant="secondary">Raise a query</Button></Link>} />
      ) : (
        <ul className="divide-y divide-slate-100 overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
          {q.data.items.map((t) => (
            <li key={t.id}>
              <Link href={`/author/tickets/${t.id}`} className="flex flex-col gap-2 px-4 py-3 hover:bg-slate-50 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-400">#{t.number}</span>
                    <span className="truncate font-medium text-slate-900">{t.subject}</span>
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">
                    {t.book ? t.book.title : "General / Account"} · {t.category_label} · updated {relTime(t.last_activity_at)}
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="flex items-center gap-1"><MessageSquare className="h-3.5 w-3.5" /> {t.message_count}</span>
                  <Badge tone={priorityTone[t.priority]}>{PRIORITY_LABEL[t.priority]}</Badge>
                  <Badge tone={statusTone[t.status]}>{STATUS_LABEL[t.status]}</Badge>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
