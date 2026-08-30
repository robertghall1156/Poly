"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, BookOpen, Brain, CalendarDays, Clapperboard, FileText, FlaskConical, Home, Layers, Newspaper, Settings, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/today", label: "Today", icon: Sun },
  { href: "/stories", label: "Stories", icon: Newspaper },
  { href: "/think", label: "Think", icon: Brain },
  { href: "/principles", label: "Principles", icon: Layers },
  { href: "/research", label: "Research", icon: FlaskConical },
  { href: "/content", label: "Content", icon: FileText },
  { href: "/videos", label: "Videos", icon: Clapperboard },
  { href: "/book", label: "Book", icon: BookOpen },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="flex h-screen w-52 shrink-0 flex-col border-r border-zinc-200 bg-white">
      <div className="flex h-12 items-center gap-2 border-b border-zinc-200 px-4">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-accent" />
        <span className="text-sm font-semibold tracking-tight text-zinc-900">Poly</span>
        <span className="ml-auto text-[10px] uppercase tracking-wider text-zinc-400">local</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {NAV.map((n) => {
          const active = n.href === "/" ? pathname === "/" : pathname.startsWith(n.href);
          const Icon = n.icon;
          return (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "mx-2 flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] transition-colors",
                active ? "bg-zinc-100 font-medium text-zinc-900" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
              )}
            >
              <Icon className={cn("h-4 w-4", active ? "text-accent-strong" : "text-zinc-400")} />
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-zinc-200 px-4 py-2 text-[11px] leading-snug text-zinc-400">Think before you publish.</div>
    </aside>
  );
}
