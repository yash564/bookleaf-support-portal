"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { BookOpen } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate, inr } from "@/lib/format";
import type { Book } from "@/lib/types";
import { Badge, Button, EmptyState, ErrorNote, PageHeader, Spinner, Stat } from "@/components/ui";

function PendingCell({ b, threshold }: { b: Book; threshold: number }) {
  const pending = Number(b.royalty_pending);
  if (!b.is_published) return <span className="text-slate-400">—</span>;
  if (pending === 0) return <span className="text-slate-500">Nothing pending</span>;
  return (
    <div>
      <div className="font-medium text-amber-700">{inr(pending)}</div>
      <div className="text-xs text-slate-500">{pending < threshold ? `Below ₹${threshold.toLocaleString("en-IN")} — rolls to next quarter` : b.last_payout_date ? "Due next payout" : "First payout pending"}</div>
    </div>
  );
}

export default function MyBooksPage() {
  const q = useQuery({ queryKey: ["author", "books"], queryFn: api.author.books });
  if (q.isPending) return <Spinner label="Loading your books…" />;
  if (q.error) return <ErrorNote error={q.error} />;
  const { items, summary } = q.data;
  const threshold = Number(summary.payout_threshold);

  return (
    <>
      <PageHeader title="My Books" subtitle={`${summary.published_books} published · ${summary.in_production_books} in production`} action={<Link href="/author/tickets/new"><Button>Raise a query</Button></Link>} />

      {items.length > 0 && (
        <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Copies sold" value={summary.total_copies_sold.toLocaleString("en-IN")} />
          <Stat label="Royalty earned" value={inr(summary.total_royalty_earned)} />
          <Stat label="Royalty paid" value={inr(summary.total_royalty_paid)} />
          <Stat label="Royalty pending" value={inr(summary.total_royalty_pending)} tone={Number(summary.total_royalty_pending) > 0 ? "warning" : undefined}
            hint={summary.pending_below_threshold ? `Below the ₹${threshold.toLocaleString("en-IN")} payout threshold; rolls over` : Number(summary.total_royalty_pending) > 0 ? "Paid within 45 days of quarter end" : "All settled"} />
        </div>
      )}

      {items.length === 0 ? (
        <EmptyState icon={<BookOpen className="h-8 w-8" />} title="No books on your account yet" body="Once your manuscript is received, your titles and royalty details will appear here." action={<Link href="/author/tickets/new"><Button variant="secondary">Ask us a question</Button></Link>} />
      ) : (
        <div className="overflow-hidden rounded-lg bg-white shadow-sm ring-1 ring-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Published</th>
                <th className="px-4 py-3 text-right">MRP</th>
                <th className="px-4 py-3 text-right">Sold</th>
                <th className="px-4 py-3 text-right">Earned</th>
                <th className="px-4 py-3 text-right">Paid</th>
                <th className="px-4 py-3">Pending</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {items.map((b) => (
                <tr key={b.id} className="align-top hover:bg-slate-50/60">
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-900">{b.title}</div>
                    <div className="text-xs text-slate-500">{b.genre ?? "—"} · ISBN {b.isbn ?? "pending"}</div>
                    {b.is_published && b.available_on.length > 0 && <div className="mt-1 text-xs text-slate-500">On {b.available_on.join(", ")}</div>}
                  </td>
                  <td className="px-4 py-3">{b.is_published ? <Badge tone="success">Published & Live</Badge> : <Badge tone="info">{b.status.replace("In Production - ", "In production · ")}</Badge>}</td>
                  <td className="px-4 py-3 whitespace-nowrap">{fmtDate(b.publication_date)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{inr(b.mrp)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{b.is_published ? b.copies_sold.toLocaleString("en-IN") : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{b.is_published ? inr(b.royalty_earned) : "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {b.is_published ? inr(b.royalty_paid) : "—"}
                    {b.last_payout_date && <div className="text-xs text-slate-500">last {fmtDate(b.last_payout_date)}</div>}
                  </td>
                  <td className="px-4 py-3"><PendingCell b={b} threshold={threshold} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-4 text-xs text-slate-500">Royalties are 80% of net profit (MRP minus printing, platform commission and shipping), calculated quarterly and paid within 45 days of quarter end. Amounts under ₹1,000 roll over.</p>
    </>
  );
}
