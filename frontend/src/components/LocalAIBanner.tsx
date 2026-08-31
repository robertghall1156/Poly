"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { Button } from "./ui/button";

type Status = {
  chat_ready: boolean;
  any_runtime_running: boolean;
  hint: string;
  runtimes: { runtime: string; endpoint: string; running: boolean }[];
};

/**
 * Poly thinks with local models only. When none is reachable every generate/think action
 * fails, so say so once, at the top, with the fix — rather than letting the owner discover
 * it one failed job at a time.
 */
export function LocalAIBanner() {
  const [status, setStatus] = React.useState<Status | null>(null);
  const [checking, setChecking] = React.useState(false);

  const check = React.useCallback(async () => {
    try {
      setStatus(await api.localAIStatus());
    } catch {
      setStatus(null); // API itself is down — the page's own error handling covers that
    }
  }, []);

  React.useEffect(() => {
    check();
    const t = setInterval(check, 60_000);
    return () => clearInterval(t);
  }, [check]);

  const recheck = async () => {
    setChecking(true);
    try {
      await api.refreshLocalAI();
      await check();
    } catch {
      /* surfaced by the status line below */
    } finally {
      setChecking(false);
    }
  };

  if (!status || status.chat_ready) return null;

  return (
    <div className="mb-6 border-2 border-highlight bg-highlight-soft px-4 py-3">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <p className="kicker text-highlight-strong">Local AI is offline</p>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="secondary" onClick={recheck} disabled={checking}>
            {checking ? "Checking…" : "Check again"}
          </Button>
          <Link href="/settings?tab=local-ai" className="text-[13px] font-heading text-accent hover:underline">
            Local AI settings
          </Link>
        </div>
      </div>
      <p className="mt-1 max-w-[70ch] text-[13px] text-ink">{status.hint}</p>
      {status.runtimes.length ? (
        <p className="meta mt-2">
          {status.runtimes.map((r) => `${r.runtime} ${r.running ? "running" : "not running"} (${r.endpoint})`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}
