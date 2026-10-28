"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Briefcase, FilePlus2, FileText, FolderDown, LayoutDashboard, Menu, UserRound, X } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/profile", label: "Master profile", icon: UserRound },
  { href: "/jobs/new", label: "New job analysis", icon: FilePlus2 },
  { href: "/jobs", label: "Jobs & matches", icon: Briefcase },
  { href: "/resumes", label: "Resumes & exports", icon: FolderDown },
  { href: "/applications", label: "Application tracker", icon: FileText },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  if (href === "/jobs") return pathname === "/jobs" || (pathname.startsWith("/jobs/") && !pathname.startsWith("/jobs/new"));
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  const nav = (
    <nav className="flex flex-col gap-1">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          onClick={() => setOpen(false)}
          className={cn(
            "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
            isActive(pathname, href) ? "bg-white/12 text-white" : "text-sidebar-foreground/75 hover:bg-white/6 hover:text-white",
          )}
        >
          <Icon className="size-4" />
          {label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[15rem_1fr]">
      <aside className="bg-sidebar text-sidebar-foreground hidden flex-col gap-6 p-4 md:flex md:sticky md:top-0 md:h-dvh">
        <Brand />
        {nav}
        <p className="text-sidebar-foreground/50 mt-auto text-xs leading-relaxed">
          Local-first. Your documents stay on this machine unless you turn on an external service.
        </p>
      </aside>
      <header className="bg-sidebar text-sidebar-foreground sticky top-0 z-30 flex items-center justify-between px-4 py-3 md:hidden">
        <Brand />
        <button aria-label={open ? "Close menu" : "Open menu"} onClick={() => setOpen((o) => !o)} className="rounded-md p-1.5 hover:bg-white/10">
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </header>
      {open && <div className="bg-sidebar text-sidebar-foreground sticky top-[52px] z-20 border-t border-white/10 p-3 md:hidden">{nav}</div>}
      <main className="min-w-0 px-4 py-6 md:px-8 md:py-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  );
}

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight text-white">
      <span className="grid size-7 place-items-center rounded-md bg-white/15 text-xs">RI</span>
      Resume Intelligence
    </Link>
  );
}
