"use client";

import { Lock } from "lucide-react";
import { fmtDateTime } from "@/lib/format";
import type { Message, Role } from "@/lib/types";
import { cx } from "./ui";

/** Conversation thread. Internal notes only ever arrive for admins (the API strips them for authors). */
export function Thread({ messages, viewer, emptyText }: { messages: Message[]; viewer: Role; emptyText: string }) {
  if (messages.length === 0) return <p className="rounded-lg border border-dashed border-slate-300 px-4 py-6 text-center text-sm text-slate-500">{emptyText}</p>;
  return (
    <ol className="space-y-3">
      {messages.map((m) => {
        const mine = viewer === "AUTHOR" ? m.kind === "AUTHOR_MESSAGE" : m.kind !== "AUTHOR_MESSAGE";
        const note = m.kind === "INTERNAL_NOTE";
        return (
          <li key={m.id} className={cx("flex", mine ? "justify-end" : "justify-start")}>
            <div className={cx("max-w-[85%] rounded-lg px-4 py-3 text-sm shadow-sm ring-1", note ? "bg-amber-50 ring-amber-200" : mine ? "bg-brand-50 ring-brand-100" : "bg-white ring-slate-200")}>
              <div className="mb-1 flex items-center gap-2 text-xs text-slate-500">
                {note && <Lock className="h-3 w-3 text-amber-700" />}
                <span className="font-medium text-slate-700">{note ? `Internal note · ${m.sender_name ?? "staff"}` : m.kind === "ADMIN_REPLY" ? `${m.sender_name ?? "BookLeaf"} · BookLeaf Support` : m.sender_name ?? "Author"}</span>
                <span>{fmtDateTime(m.created_at)}</span>
              </div>
              <p className="whitespace-pre-wrap leading-relaxed text-slate-800">{m.body}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
