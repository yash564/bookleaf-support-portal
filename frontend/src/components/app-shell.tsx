"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BookOpen, Inbox, LogOut, PlusCircle, BarChart3 } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { cx } from "./ui";
import type { ReactNode } from "react";

const NAV = {
  AUTHOR: [
    { href: "/author/books", label: "My Books", icon: BookOpen },
    { href: "/author/tickets", label: "My Tickets", icon: Inbox },
    { href: "/author/tickets/new", label: "New Query", icon: PlusCircle },
  ],
  ADMIN: [
    { href: "/admin/tickets", label: "Queue", icon: Inbox },
    { href: "/admin/usage", label: "AI Usage", icon: BarChart3 },
  ],
};

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const path = usePathname();
  if (!user) return null;
  const items = NAV[user.role];
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-4 px-4">
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center gap-2 font-semibold text-brand-800">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-brand-700 text-xs font-bold text-white">BL</span>
              BookLeaf <span className="hidden text-slate-400 sm:inline">· {user.role === "ADMIN" ? "Ops" : "Author"} portal</span>
            </Link>
            <nav className="hidden items-center gap-1 sm:flex">
              {items.map(({ href, label, icon: Icon }) => {
                const active = href === "/author/tickets" ? path === href || /^\/author\/tickets\/(?!new)/.test(path) : path.startsWith(href);
                return (
                  <Link key={href} href={href} className={cx("flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm", active ? "bg-brand-50 text-brand-800" : "text-slate-600 hover:bg-slate-100")}>
                    <Icon className="h-4 w-4" /> {label}
                  </Link>
                );
              })}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-600 sm:inline">{user.name}</span>
            <button onClick={logout} className="flex items-center gap-1 rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800" title="Sign out">
              <LogOut className="h-4 w-4" /> <span className="hidden sm:inline">Sign out</span>
            </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-2 py-1 sm:hidden">
          {items.map(({ href, label }) => (
            <Link key={href} href={href} className={cx("rounded-md px-3 py-1.5 text-sm whitespace-nowrap", path.startsWith(href) ? "bg-brand-50 text-brand-800" : "text-slate-600")}>
              {label}
            </Link>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}
