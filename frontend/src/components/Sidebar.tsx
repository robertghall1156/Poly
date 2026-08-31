"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { useBrand } from "./BrandContext";
import { usePrivacy } from "./PrivacyContext";
import { SearchPalette } from "./SearchPalette";
import { CreateLauncher } from "./CreateLauncher";

interface SubItem {
  label: string;
  tab: string;
}

const PRIMARY: { href: string; label: string; sub?: SubItem[]; defaultTab?: string }[] = [
  { href: "/", label: "Home" },
  {
    href: "/discover",
    label: "Discover",
    defaultTab: "today",
    sub: [
      { label: "Today", tab: "today" },
      { label: "Stories", tab: "all" },
      { label: "Research", tab: "research" },
    ],
  },
  {
    href: "/think",
    label: "Think",
    defaultTab: "ideas",
    sub: [
      { label: "My ideas", tab: "ideas" },
      { label: "Positions", tab: "positions" },
      { label: "Beliefs", tab: "beliefs" },
    ],
  },
  { href: "/create", label: "Create" },
  {
    href: "/library",
    label: "Library",
    defaultTab: "content",
    sub: [
      { label: "Content", tab: "content" },
      { label: "Videos", tab: "videos" },
      { label: "Images", tab: "images" },
      { label: "Book", tab: "book" },
    ],
  },
  { href: "/calendar", label: "Calendar" },
];

function NavItem({ href, label, active }: { href: string; label: string; active: boolean }) {
  return (
    <Link
      href={href}
      className={cn(
        "mx-3 block border-l-[3px] py-2 pl-[13px] pr-2.5 font-heading text-xs uppercase tracking-[0.09em] transition-colors",
        active ? "border-accent bg-accent-soft text-accent" : "border-transparent text-ink hover:bg-ink/5",
      )}
    >
      {label}
    </Link>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const params = useSearchParams();
  const { brand } = useBrand();
  const { privacy } = usePrivacy();
  const [searchOpen, setSearchOpen] = React.useState(false);
  const [createOpen, setCreateOpen] = React.useState(false);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCreateOpen((o) => !o);
      } else if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setSearchOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const isActive = (href: string) => (href === "/" ? pathname === "/" : pathname.startsWith(href));
  const cloud = privacy?.cloud_ai_permitted;

  return (
    <aside className="flex h-screen w-[216px] shrink-0 flex-col border-r-2 border-divider bg-paper pb-3 pt-[18px]">
      <div className="flex items-baseline gap-2 px-4 pb-[18px]">
        <span className="font-heading text-[21px] uppercase leading-none tracking-[-0.02em] text-ink">{brand.logo_text || "Poly"}</span>
        <span className="h-2 w-2 bg-accent" aria-hidden />
      </div>

      <div className="px-3 pb-1.5">
        <button
          type="button"
          onClick={() => setCreateOpen(true)}
          data-testid="topbar-create"
          className="flex w-full items-center justify-between bg-accent px-2.5 py-2 font-heading text-xs uppercase tracking-[0.09em] text-paper hover:bg-accent-strong"
        >
          <span>Create</span>
          <span className="text-[11px] font-normal normal-case tracking-normal opacity-75">⌘K</span>
        </button>
      </div>

      <div className="px-3 pb-3.5">
        <button
          type="button"
          onClick={() => setSearchOpen(true)}
          className="flex w-full items-center gap-2 border border-divider px-2.5 py-1.5 text-left text-xs text-zinc-500 hover:border-zinc-400 hover:text-zinc-700"
        >
          <Search className="h-3 w-3" />
          <span className="flex-1">Search</span>
          <span className="text-[10px] opacity-70">⌘/</span>
        </button>
      </div>

      <nav className="flex flex-1 flex-col gap-px overflow-y-auto">
        {PRIMARY.map((n) => {
          const active = isActive(n.href);
          const currentTab = active && n.sub ? (n.sub.some((s) => s.tab === params.get("tab")) ? (params.get("tab") as string) : n.defaultTab) : null;
          return (
            <React.Fragment key={n.href}>
              <NavItem href={n.href} label={n.label} active={active} />
              {active && n.sub ? (
                <div className="flex flex-col gap-px pb-1.5">
                  {n.sub.map((s) => {
                    const on = currentTab === s.tab;
                    return (
                      <Link
                        key={s.tab}
                        href={`${n.href}?tab=${s.tab}`}
                        className={cn(
                          "mx-3 block py-1 pl-[29px] pr-2.5 text-[13px] transition-colors",
                          on ? "font-semibold text-ink" : "font-normal text-muted hover:text-ink",
                        )}
                      >
                        {s.label}
                      </Link>
                    );
                  })}
                </div>
              ) : null}
            </React.Fragment>
          );
        })}
      </nav>

      <div className="mx-3 mt-3 border-t border-divider pt-3">
        {privacy ? (
          <Link
            href="/settings?tab=privacy"
            className={cn("mb-2 flex items-center gap-1.5 px-2.5 text-[10px] uppercase tracking-[0.08em]", cloud ? "text-highlight-strong" : "text-zinc-500 hover:text-zinc-700")}
            title={cloud ? "Cloud AI is permitted: some actions may send content to external providers" : "All AI runs on this machine"}
          >
            <span className={cn("h-1.5 w-1.5 rounded-full", cloud ? "bg-highlight" : "bg-accent")} aria-hidden />
            {cloud ? "Cloud AI enabled" : "Local AI only"}
          </Link>
        ) : (
          <span className="mb-2 flex items-center gap-1.5 px-2.5 text-[10px] uppercase tracking-[0.08em] text-zinc-400">
            <span className="h-1.5 w-1.5 rounded-full bg-zinc-300" aria-hidden />
            Backend unreachable
          </span>
        )}
        <div className="flex flex-col gap-1.5 px-2.5 pt-1">
          <Link href="/analytics" className={cn("text-xs", isActive("/analytics") ? "text-accent" : "text-muted hover:text-ink")}>
            Analytics
          </Link>
          <Link href="/settings" className={cn("text-xs", isActive("/settings") ? "text-accent" : "text-muted hover:text-ink")}>
            Settings
          </Link>
        </div>
      </div>

      <SearchPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
      <CreateLauncher open={createOpen} onClose={() => setCreateOpen(false)} />
    </aside>
  );
}
