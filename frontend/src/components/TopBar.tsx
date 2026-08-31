"use client";

import * as React from "react";
import Link from "next/link";
import { Cloud, Lock, Plus, Search } from "lucide-react";
import { usePrivacy } from "./PrivacyContext";
import { SearchPalette } from "./SearchPalette";
import { CreateLauncher } from "./CreateLauncher";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";

export function TopBar() {
  const { privacy } = usePrivacy();
  const [open, setOpen] = React.useState(false);
  const [create, setCreate] = React.useState(false);
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const cloud = privacy?.cloud_ai_permitted;
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-zinc-200 bg-white px-4">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="flex h-8 w-full max-w-md items-center gap-2 rounded-md border border-zinc-300 bg-zinc-50 px-2.5 text-left text-[13px] text-zinc-500 hover:border-zinc-400"
      >
        <Search className="h-3.5 w-3.5" />
        <span className="flex-1">Search stories, positions, drafts…</span>
        <kbd className="rounded border border-zinc-300 bg-white px-1 font-mono text-[10px] text-zinc-500">⌘K</kbd>
      </button>
      <div className="ml-auto flex items-center gap-2">
        <Button variant="accent" size="md" onClick={() => setCreate(true)} data-testid="topbar-create">
          <Plus className="h-3.5 w-3.5" />
          Create
        </Button>
        {privacy ? (
          <Link
            href="/settings?tab=privacy"
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs font-medium",
              cloud ? "border-warn bg-warn-soft text-[#b3401f]" : "border-zinc-200 bg-zinc-50 text-zinc-700",
            )}
            title={cloud ? "Cloud AI is permitted: some actions may send content to external providers" : "All AI runs on this machine"}
          >
            {cloud ? <Cloud className="h-3.5 w-3.5" /> : <Lock className="h-3.5 w-3.5 text-accent-strong" />}
            {cloud ? "Cloud AI enabled" : "Local AI only"}
          </Link>
        ) : (
          <span className="text-xs text-zinc-400">Backend unreachable</span>
        )}
      </div>
      <SearchPalette open={open} onClose={() => setOpen(false)} />
      <CreateLauncher open={create} onClose={() => setCreate(false)} />
    </header>
  );
}
