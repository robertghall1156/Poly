"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Brain, CalendarDays, Compass, Home, Library, Settings, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBrand } from "./BrandContext";

const PRIMARY = [
  { href: "/", label: "Home", icon: Home },
  { href: "/discover", label: "Discover", icon: Compass },
  { href: "/think", label: "Think", icon: Brain },
  { href: "/create", label: "Create", icon: Sparkles },
  { href: "/library", label: "Library", icon: Library },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
];

const SECONDARY = [
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

function NavLink({ href, label, icon: Icon, active, quiet }: { href: string; label: string; icon: typeof Home; active: boolean; quiet?: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "mx-2 flex items-center gap-2.5 rounded-md px-2.5 py-1.5 transition-colors",
        quiet ? "text-xs" : "text-[13px]",
        active ? "bg-accent-soft font-medium text-brand" : quiet ? "text-zinc-500 hover:bg-zinc-50 hover:text-zinc-800" : "text-zinc-600 hover:bg-zinc-50 hover:text-zinc-900",
      )}
    >
      <Icon className={cn(quiet ? "h-3.5 w-3.5" : "h-4 w-4", active ? "text-accent-strong" : "text-zinc-400")} />
      {label}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { brand } = useBrand();
  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  return (
    <aside className="flex h-screen w-52 shrink-0 flex-col border-r border-zinc-200 bg-white">
      <div className="flex h-12 items-center gap-2 border-b border-zinc-200 px-4">
        <span className="inline-block h-2.5 w-2.5 rounded-sm bg-accent" />
        <span className="text-sm font-semibold tracking-tight text-brand">{brand.logo_text || "Poly"}</span>
        <span className="ml-auto text-[10px] uppercase tracking-wider text-zinc-400">local</span>
      </div>
      <nav className="flex-1 overflow-y-auto py-2">
        {PRIMARY.map((n) => (
          <NavLink key={n.href} {...n} active={isActive(n.href)} />
        ))}
      </nav>
      <div className="border-t border-zinc-200 py-2">
        {SECONDARY.map((n) => (
          <NavLink key={n.href} {...n} active={isActive(n.href)} quiet />
        ))}
      </div>
      <div className="border-t border-zinc-200 px-4 py-2 text-[11px] leading-snug text-zinc-400">Think before you publish.</div>
    </aside>
  );
}
