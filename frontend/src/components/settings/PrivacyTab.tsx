"use client";

import * as React from "react";
import { api } from "@/lib/api";
import { useAction } from "@/lib/hooks";
import type { AllSettings, Privacy } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Dialog } from "../ui/dialog";
import { Switch } from "../ui/switch";
import { ErrorNotice, Notice } from "../ui/notice";
import { Panel } from "../ui/section";
import { usePrivacy } from "../PrivacyContext";

export function PrivacyTab({ settings, onChanged }: { settings: AllSettings | null; onChanged: () => void }) {
  const ctx = usePrivacy();
  const [privacy, setPrivacy] = React.useState<Privacy | null>(settings?.privacy ?? null);
  const [confirm, setConfirm] = React.useState(false);
  const act = useAction();
  React.useEffect(() => {
    if (settings?.privacy) setPrivacy(settings.privacy);
  }, [settings]);

  const update = async (body: Partial<Privacy> & { confirm_cloud?: boolean }) => {
    const r = await act.run(() => api.patchPrivacy(body));
    if (r) {
      setPrivacy(r);
      ctx.reload();
      onChanged();
    }
    return r;
  };

  if (!privacy) return null;
  const env = settings?.env;
  const cloudOn = privacy.cloud_ai_permitted;
  return (
    <div className="space-y-4">
      <div className={cn("rounded-md border px-4 py-3", cloudOn ? "border-warn bg-warn-soft" : "border-zinc-200 bg-white")}>
        <p className={cn("text-sm font-semibold", cloudOn ? "text-[#9a3a1c]" : "text-zinc-900")}>{cloudOn ? "Cloud AI is permitted. Content may leave this machine." : "Everything stays on this machine."}</p>
        <p className="mt-0.5 text-xs text-zinc-600">{cloudOn ? "Any action that can call a cloud provider is highlighted in orange throughout the app." : "Local AI only. Private material never leaves the machine unless you explicitly allow cloud AI below."}</p>
      </div>
      <ErrorNotice error={act.error} />
      <Panel>
        <div className="divide-y divide-zinc-200">
          <Row title="Local AI only" desc="Route every AI task to local runtimes. When on, cloud AI is never used even if a key is present.">
            <Switch checked={privacy.local_ai_only} onChange={(v) => update({ local_ai_only: v })} />
          </Row>
          <Row title="Allow internet research" desc="Fetch RSS feeds, articles and primary sources from the web. Required for news ingest. No content of yours is sent; only requests for public pages.">
            <Switch checked={privacy.allow_internet_research} onChange={(v) => update({ allow_internet_research: v })} />
          </Row>
          <Row title="Allow cloud AI" desc="Permit Anthropic or OpenAI as a fallback or override. Requires explicit confirmation and an API key in .env.">
            <Switch
              warn
              checked={privacy.allow_cloud_ai}
              onChange={(v) => {
                if (v) setConfirm(true);
                else update({ allow_cloud_ai: false });
              }}
            />
          </Row>
        </div>
      </Panel>
      <Panel title="Keys present in .env">
        <div className="flex flex-wrap gap-2 text-xs">
          <Key name="ANTHROPIC_API_KEY" present={env?.anthropic_key_present} />
          <Key name="OPENAI_API_KEY" present={env?.openai_key_present} />
          <Key name="BRAVE_API_KEY" present={env?.brave_key_present} />
          <Key name="TAVILY_API_KEY" present={env?.tavily_key_present} />
          <Key name="NEWSAPI_KEY" present={env?.newsapi_key_present} />
        </div>
        <p className="mt-2 text-xs text-zinc-500">Keys are read from the backend .env file and are never shown or stored in the database.</p>
      </Panel>
      <Notice>Poly never posts political content automatically, never profiles voters, and never fabricates quotes, statistics or images presented as real.</Notice>

      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Enable cloud AI?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Keep local only
            </Button>
            <Button
              variant="warn"
              loading={act.busy}
              onClick={async () => {
                const r = await update({ allow_cloud_ai: true, confirm_cloud: true });
                if (r) setConfirm(false);
              }}
            >
              I understand — enable cloud AI
            </Button>
          </>
        }
      >
        <div className="space-y-2 text-[13px] text-zinc-800">
          <p className="font-medium text-[#9a3a1c]">When cloud AI is permitted, the following can be sent to Anthropic or OpenAI:</p>
          <ul className="list-disc space-y-1 pl-5">
            <li>Story summaries, article text and extracted claims being analysed</li>
            <li>Your Think Mode answers and the resulting position briefs</li>
            <li>Your principles (titles, positions, rationale) used as context</li>
            <li>Scripts and content packages during generation and fact checking</li>
          </ul>
          <p>Video files and transcripts are still processed locally. Cloud calls are only made when a local model is unavailable or you explicitly override, and every such action is marked in orange.</p>
          {!settings?.env.anthropic_key_present && !settings?.env.openai_key_present ? <p className="rounded border border-zinc-200 bg-zinc-50 p-2 text-xs text-zinc-600">No cloud API key is present in .env, so nothing can actually be sent until you add one.</p> : null}
          {privacy.local_ai_only ? <p className="rounded border border-zinc-200 bg-zinc-50 p-2 text-xs text-zinc-600">“Local AI only” is still on. Cloud AI is not permitted until you also turn that off.</p> : null}
        </div>
      </Dialog>
    </div>
  );
}

function Row({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-4 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-zinc-900">{title}</p>
        <p className="text-xs text-zinc-500">{desc}</p>
      </div>
      {children}
    </div>
  );
}

function Key({ name, present }: { name: string; present?: boolean }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded border border-zinc-200 bg-white px-2 py-1 font-mono">
      {name}
      <Badge variant={present ? "warn" : "neutral"}>{present ? "present" : "absent"}</Badge>
    </span>
  );
}
