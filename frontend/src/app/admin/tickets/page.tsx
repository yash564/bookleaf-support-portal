"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Inbox, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useLiveEvents } from "@/lib/realtime";
import { CATEGORIES, CATEGORY_LABEL, PRIORITIES, PRIORITY_LABEL, STATUSES, STATUS_LABEL, ageOf, priorityTone, relTime, statusTone } from "@/lib/format";
import type { QueueFilters, TicketStatus } from "@/lib/types";
import { Badge, Button, EmptyState, ErrorNote, Input, LiveDot, PageHeader, Select, Spinner, Stat, cx } from "@/components/ui";

const DEFAULT: QueueFilters = { status: ["OPEN", "IN_PROGRESS"], category: "", priority: "", assigned: "", q: "", created_from: "", created_to: "", sort: "urgency", limit: 50, offset: 0 };

export default function QueuePage() {
  const qc = useQueryClient();
  const [f, setF] = useState<QueueFilters>(DEFAULT);
  const [search, setSearch] = useState("");
  const set = (patch: Partial<QueueFilters>) => setF((x) => ({ ...x, ...patch, offset: 0 }));

  const list = useQuery({ queryKey: ["admin", "tickets", f], queryFn: () => api.admin.queue(f), refetchInterval: 30_000, placeholderData: (prev) => prev });
  const stats = useQuery({ queryKey: ["admin", "stats"], queryFn: api.admin.stats, refetchInterval: 30_000 });
  const { live } = useLiveEvents("/api/v1/admin/tickets/events", () => {
    qc.invalidateQueries({ queryKey: ["admin", "tickets"] });
    qc.invalidateQueries({ queryKey: ["admin", "stats"] });
  });

  const toggleStatus = (s: TicketStatus) => {
    const cur = f.status ?? [];
    set({ status: cur.includes(s) ? cur.filter((x) => x !== s) : [...cur, s] });
  };
  const s = stats.data;
  const unresolved = s ? s.by_status.OPEN + s.by_status.IN_PROGRESS : 0;

  return (
    <>
      <PageHeader title="Ticket queue" subtitle={<span className="flex items-center gap-3">Most urgent and oldest unresolved tickets first. <LiveDot live={live} /></span>} />

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Unresolved" value={unresolved} hint={s ? `${s.by_status.OPEN} open · ${s.by_status.IN_PROGRESS} in progress` : ""} />
        <Stat label="Critical / High" value={s ? s.open_by_priority.CRITICAL + s.open_by_priority.HIGH : "–"} tone={s && s.open_by_priority.CRITICAL > 0 ? "danger" : undefined} hint={s ? `${s.open_by_priority.CRITICAL} critical` : ""} />
        <Stat label="Unassigned" value={s?.unassigned_open ?? "–"} tone={s && s.unassigned_open > 0 ? "warning" : undefined} hint="open tickets with no owner" />
        <Stat label="Oldest waiting" value={s?.oldest_open_created_at ? ageOf(s.oldest_open_created_at) : "–"} hint={s?.oldest_open_created_at ? `since ${relTime(s.oldest_open_created_at)}` : "queue is clear"} />
      </div>

      <div className="mb-4 rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex flex-wrap gap-1">
            {STATUSES.map((st) => (
              <button key={st} onClick={() => toggleStatus(st)} className={cx("rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", f.status?.includes(st) ? "bg-brand-700 text-white ring-brand-700" : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50")}>{STATUS_LABEL[st]}</button>
            ))}
          </div>
          <span className="mx-1 hidden h-5 w-px bg-slate-200 sm:block" />
          <div className="flex gap-1">
            {([["", "All"], ["me", "Mine"], ["unassigned", "Unassigned"]] as const).map(([v, l]) => (
              <button key={v} onClick={() => set({ assigned: v })} className={cx("rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset", f.assigned === v ? "bg-slate-800 text-white ring-slate-800" : "bg-white text-slate-600 ring-slate-300 hover:bg-slate-50")}>{l}</button>
            ))}
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-6">
          <Select value={f.category} onChange={(e) => set({ category: e.target.value as QueueFilters["category"] })}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{CATEGORY_LABEL[c]}</option>)}
          </Select>
          <Select value={f.priority} onChange={(e) => set({ priority: e.target.value as QueueFilters["priority"] })}>
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p} value={p}>{PRIORITY_LABEL[p]}</option>)}
          </Select>
          <Input type="date" value={f.created_from} onChange={(e) => set({ created_from: e.target.value })} title="Created from" />
          <Input type="date" value={f.created_to} onChange={(e) => set({ created_to: e.target.value })} title="Created to" />
          <form className="relative col-span-2 md:col-span-1" onSubmit={(e) => { e.preventDefault(); set({ q: search }); }}>
            <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
            <Input className="pl-8" placeholder="Search #, subject, author" value={search} onChange={(e) => setSearch(e.target.value)} onBlur={() => set({ q: search })} />
          </form>
          <Select value={f.sort} onChange={(e) => set({ sort: e.target.value as QueueFilters["sort"] })}>
            <option value="urgency">Sort: urgency</option>
            <option value="oldest">Sort: oldest</option>
            <option value="newest">Sort: newest</option>
            <option value="activity">Sort: last activity</option>
          </Select>
        </div>
        {JSON.stringify(f) !== JSON.stringify(DEFAULT) && (
          <div className="mt-2 text-right"><Button size="sm" variant="ghost" onClick={() => { setF(DEFAULT); setSearch(""); }}>Reset filters</Button></div>
        )}
      </div>

      {list.isPending ? (
        <Spinner />
      ) : list.error ? (
        <ErrorNote error={list.error} />
      ) : list.data.items.length === 0 ? (
        <EmptyState icon={<Inbox className="h-8 w-8" />} title="No tickets match" body="Try widening the status filter or clearing the search." />
      ) : (
        <div className="overflow-x-auto rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2.5">Priority</th>
                <th className="px-3 py-2.5">Ticket</th>
                <th className="px-3 py-2.5">Author</th>
                <th className="px-3 py-2.5">Category</th>
                <th className="px-3 py-2.5">Status</th>
                <th className="px-3 py-2.5">Owner</th>
                <th className="px-3 py-2.5 text-right">Waiting</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {list.data.items.map((t) => {
                const unresolved = t.status === "OPEN" || t.status === "IN_PROGRESS";
                const hot = unresolved && (t.priority === "CRITICAL" || t.priority === "HIGH");
                return (
                  <tr key={t.id} className={cx("hover:bg-slate-50", hot && "bg-rose-50/30")}>
                    <td className="px-3 py-2.5"><Badge tone={priorityTone[t.priority]}>{PRIORITY_LABEL[t.priority]}</Badge></td>
                    <td className="max-w-[360px] px-3 py-2.5">
                      <Link href={`/admin/tickets/${t.id}`} className="block">
                        <div className="flex items-center gap-2"><span className="font-mono text-xs text-slate-400">#{t.number}</span><span className="truncate font-medium text-slate-900 hover:underline">{t.subject}</span></div>
                        <div className="truncate text-xs text-slate-500">{t.book ? t.book.title : "General / Account"} · {t.message_count} msg</div>
                      </Link>
                    </td>
                    <td className="px-3 py-2.5 whitespace-nowrap">
                      <div>{t.author?.name}</div>
                      <div className="text-xs text-slate-500">{t.author?.city}</div>
                    </td>
                    <td className="px-3 py-2.5 text-xs text-slate-700">{t.category_label}</td>
                    <td className="px-3 py-2.5"><Badge tone={statusTone[t.status]}>{STATUS_LABEL[t.status]}</Badge></td>
                    <td className="px-3 py-2.5 text-xs">{t.assigned_to ? t.assigned_to.name : <span className="text-amber-700">Unassigned</span>}</td>
                    <td className="px-3 py-2.5 text-right text-xs text-slate-600 whitespace-nowrap" title={`Created ${relTime(t.created_at)}`}>
                      <span className={cx(unresolved && ageOf(t.created_at).endsWith("d") && parseInt(ageOf(t.created_at)) >= 2 && "font-semibold text-rose-700")}>{ageOf(t.created_at)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <div className="flex items-center justify-between border-t border-slate-100 px-3 py-2 text-xs text-slate-500">
            <span>{list.data.total} ticket{list.data.total === 1 ? "" : "s"}</span>
            <div className="flex gap-1">
              <Button size="sm" variant="ghost" disabled={(f.offset ?? 0) === 0} onClick={() => setF((x) => ({ ...x, offset: Math.max(0, (x.offset ?? 0) - (x.limit ?? 50)) }))}>Prev</Button>
              <Button size="sm" variant="ghost" disabled={(f.offset ?? 0) + (f.limit ?? 50) >= list.data.total} onClick={() => setF((x) => ({ ...x, offset: (x.offset ?? 0) + (x.limit ?? 50) }))}>Next</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
