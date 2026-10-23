"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card, ErrorNote, PageHeader, Spinner, Stat } from "@/components/ui";

export default function UsagePage() {
  const q = useQuery({ queryKey: ["admin", "usage"], queryFn: api.admin.usage });
  if (q.isPending) return <Spinner />;
  if (q.error) return <ErrorNote error={q.error} />;
  const u = q.data;
  const calls = u.rows.reduce((a, r) => a + r.calls, 0);
  const tokens = u.rows.reduce((a, r) => a + r.input_tokens + r.output_tokens + r.cache_read_tokens + r.cache_write_tokens, 0);
  const cacheRead = u.rows.reduce((a, r) => a + r.cache_read_tokens, 0);

  return (
    <>
      <PageHeader title="AI usage & cost" subtitle={`Every model call is logged with its token counts. Model: ${u.model}`} />
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Model calls" value={calls} />
        <Stat label="Total tokens" value={tokens.toLocaleString("en-IN")} hint={`${cacheRead.toLocaleString("en-IN")} served from prompt cache`} />
        <Stat label="Estimated cost" value={`$${Number(u.total_cost_usd).toFixed(4)}`} hint={calls ? `≈ $${(Number(u.total_cost_usd) / calls).toFixed(5)} per call` : "no calls yet"} />
        <Stat label="Cache hit rate" value={tokens ? `${Math.round((cacheRead / Math.max(1, cacheRead + u.rows.reduce((a, r) => a + r.input_tokens + r.cache_write_tokens, 0))) * 100)}%` : "–"} hint="of input tokens" />
      </div>
      <Card title="By purpose">
        {u.rows.length === 0 ? (
          <p className="text-sm text-slate-500">No model calls recorded yet. Calls appear here once a ticket is classified or a draft is generated with an API key configured.</p>
        ) : (
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <tr><th className="py-2 pr-4">Purpose</th><th className="py-2 pr-4 text-right">Calls</th><th className="py-2 pr-4 text-right">OK / failed</th><th className="py-2 pr-4 text-right">Input</th><th className="py-2 pr-4 text-right">Output</th><th className="py-2 pr-4 text-right">Cache read</th><th className="py-2 pr-4 text-right">Cache write</th><th className="py-2 text-right">Est. cost</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100 tabular-nums">
              {u.rows.map((r) => (
                <tr key={r.purpose}>
                  <td className="py-2 pr-4 font-medium">{r.purpose === "CLASSIFY" ? "Classification + priority" : "Draft replies"}</td>
                  <td className="py-2 pr-4 text-right">{r.calls}</td>
                  <td className="py-2 pr-4 text-right">{r.ok} / {r.failed}</td>
                  <td className="py-2 pr-4 text-right">{r.input_tokens.toLocaleString("en-IN")}</td>
                  <td className="py-2 pr-4 text-right">{r.output_tokens.toLocaleString("en-IN")}</td>
                  <td className="py-2 pr-4 text-right">{r.cache_read_tokens.toLocaleString("en-IN")}</td>
                  <td className="py-2 pr-4 text-right">{r.cache_write_tokens.toLocaleString("en-IN")}</td>
                  <td className="py-2 text-right">${Number(r.estimated_cost_usd).toFixed(4)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="mt-3 text-xs text-slate-500">{u.pricing_note}</p>
      </Card>
    </>
  );
}
