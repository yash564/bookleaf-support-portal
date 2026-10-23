"use client";

/** Subscribe to a backend SSE stream and run `onEvent` for every ticket signal.
 *  The payload is only a signal; callers invalidate React Query caches and refetch via REST.
 *  EventSource reconnects on its own; while disconnected, the caller's `refetchInterval` polling is the fallback. */

import { useEffect, useRef, useState } from "react";
import { sseUrl } from "./api";

export const TICKET_EVENTS = ["ticket.created", "ticket.updated", "ticket.classified", "message.created", "note.created"] as const;
export type TicketEvent = { type: string; ticket_id: string; number: number; status: string; at: string };

export function useLiveEvents(path: string | null, onEvent: (e: TicketEvent) => void): { live: boolean } {
  const [live, setLive] = useState(false);
  const handler = useRef(onEvent);
  useEffect(() => {
    handler.current = onEvent;
  });

  useEffect(() => {
    if (!path) return;
    const url = sseUrl(path);
    if (!url || typeof EventSource === "undefined") return;
    const es = new EventSource(url);
    const listener = (ev: MessageEvent) => {
      try {
        handler.current(JSON.parse(ev.data) as TicketEvent);
      } catch {}
    };
    es.addEventListener("ready", () => setLive(true));
    for (const name of TICKET_EVENTS) es.addEventListener(name, listener as EventListener);
    es.onerror = () => setLive(false);
    return () => {
      es.close();
      setLive(false);
    };
  }, [path]);

  return { live };
}
