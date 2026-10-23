"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Paperclip, X } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import { useToast } from "@/components/toast";
import { Button, Card, Field, Input, PageHeader, Select, Textarea } from "@/components/ui";

const GENERAL = "__general__";

export default function NewTicketPage() {
  const router = useRouter();
  const qc = useQueryClient();
  const toast = useToast();
  const books = useQuery({ queryKey: ["author", "books"], queryFn: api.author.books });
  const [bookId, setBookId] = useState(GENERAL);
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const create = useMutation({
    mutationFn: () =>
      api.author.createTicket({
        book_id: bookId === GENERAL ? null : bookId,
        subject,
        description,
        // UI-only attachments per the brief: we send metadata so the ops team sees what was offered.
        attachments: files.map((f) => ({ filename: f.name, mime_type: f.type || null, size_bytes: f.size })),
      }),
    onSuccess: (t) => {
      qc.invalidateQueries({ queryKey: ["author", "tickets"] });
      toast.push({ tone: "success", title: `Ticket #${t.number} submitted`, body: "We'll classify it right away and reply within 48 hours." });
      router.push(`/author/tickets/${t.id}`);
    },
    onError: (e) => {
      if (e instanceof ApiError) setErrors(e.fieldErrors());
      toast.push({ tone: "error", title: "Couldn't submit", body: e instanceof Error ? e.message : "Unknown error" });
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    const next: Record<string, string> = {};
    if (subject.trim().length < 3) next.subject = "Please give a short subject (3+ characters).";
    if (description.trim().length < 10) next.description = "Please describe the issue in a bit more detail (10+ characters).";
    setErrors(next);
    if (Object.keys(next).length === 0) create.mutate();
  }

  return (
    <>
      <PageHeader title="Submit a support query" subtitle="Tell us what's going on; the more specific, the faster we can help." />
      <form onSubmit={onSubmit} className="max-w-2xl">
        <Card>
          <div className="space-y-5">
            <Field label="What is this about?" htmlFor="book" hint="Pick the book, or choose General for account-level questions (royalty bank details, author bio, packages).">
              <Select id="book" value={bookId} onChange={(e) => setBookId(e.target.value)} disabled={books.isPending}>
                <option value={GENERAL}>General / Account Level</option>
                {books.data?.items.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.title} {b.is_published ? "" : `— ${b.status}`}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Subject" htmlFor="subject" error={errors.subject}>
              <Input id="subject" maxLength={200} value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Royalty for Q3 not received" />
            </Field>
            <Field label="Describe the issue" htmlFor="description" error={errors.description} hint="Include dates, amounts, platform names, or order numbers where you can.">
              <Textarea id="description" maxLength={5000} rows={7} value={description} onChange={(e) => setDescription(e.target.value)} />
              <div className="text-right text-xs text-slate-400">{description.length}/5000</div>
            </Field>
            <Field label="Attachments (optional)" htmlFor="files" hint="Photos of print defects, screenshots of listings. Up to 5 files.">
              <label htmlFor="files" className="flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-slate-300 px-3 py-3 text-sm text-slate-600 hover:bg-slate-50">
                <Paperclip className="h-4 w-4" /> Choose files…
                <input id="files" type="file" multiple className="sr-only" onChange={(e) => setFiles((xs) => [...xs, ...Array.from(e.target.files ?? [])].slice(0, 5))} />
              </label>
              {files.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {files.map((f, i) => (
                    <li key={`${f.name}-${i}`} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-1.5 text-sm">
                      <span className="truncate">{f.name} <span className="text-slate-400">{fmtBytes(f.size)}</span></span>
                      <button type="button" onClick={() => setFiles((xs) => xs.filter((_, j) => j !== i))} className="text-slate-400 hover:text-slate-700" aria-label="Remove"><X className="h-4 w-4" /></button>
                    </li>
                  ))}
                </ul>
              )}
            </Field>
            <div className="flex items-center justify-end gap-2 pt-2">
              <Button type="button" variant="ghost" onClick={() => router.back()}>Cancel</Button>
              <Button type="submit" loading={create.isPending}>Submit query</Button>
            </div>
          </div>
        </Card>
      </form>
    </>
  );
}
