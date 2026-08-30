"use client";

import * as React from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { useAction, useApi } from "@/lib/hooks";
import type { AllSettings, ContentSettings, GithubSettings, MediaSettings, NewsSettings } from "@/lib/types";
import { cn, labelFormat, relTime } from "@/lib/utils";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Field, Input, Select } from "../ui/input";
import { Switch } from "../ui/switch";
import { ErrorNotice, Notice } from "../ui/notice";
import { Panel } from "../ui/section";

const TOPICS = ["government", "elections", "congress", "presidency", "courts", "taxes", "wealth", "corporate power", "labor", "executive compensation", "ai", "automation", "healthcare", "education", "immigration", "defense", "veterans", "foreign policy", "technology", "economic policy", "housing", "energy", "infrastructure"];
const PLATFORMS = ["youtube", "podcast", "youtube_short", "tiktok", "instagram_reel", "x_post", "x_thread", "facebook_post", "instagram_post", "linkedin_post", "newsletter", "article"];

function useSaver<T extends object>(key: string, initial: T, onChanged: () => void) {
  const [v, setV] = React.useState<T>(initial);
  const [dirty, setDirty] = React.useState(false);
  const [saved, setSaved] = React.useState(false);
  const act = useAction();
  React.useEffect(() => {
    setV(initial);
    setDirty(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(initial)]);
  const set = (patch: Partial<T>) => {
    setV((p) => ({ ...p, ...patch }));
    setDirty(true);
    setSaved(false);
  };
  const save = async () => {
    const r = await act.run(() => api.patchSettings(key, v as unknown as Record<string, unknown>));
    if (r) {
      setDirty(false);
      setSaved(true);
      onChanged();
    }
  };
  return { v, set, save, dirty, saved, act };
}

function SaveBar({ s }: { s: { save: () => void; dirty: boolean; saved: boolean; act: { busy: boolean; error: string | null } } }) {
  return (
    <div className="mt-3 flex items-center gap-2">
      <Button variant="default" onClick={s.save} loading={s.act.busy} disabled={!s.dirty}>
        Save
      </Button>
      {s.saved ? <span className="text-xs text-emerald-700">Saved.</span> : null}
      <ErrorNotice error={s.act.error} />
    </div>
  );
}

function ChipSelect({ options, value, onChange, label }: { options: string[]; value: string[]; onChange: (v: string[]) => void; label?: (s: string) => string }) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map((o) => {
        const on = value.includes(o);
        return (
          <button key={o} type="button" onClick={() => onChange(on ? value.filter((x) => x !== o) : [...value, o])} className={cn("rounded-full border px-2 py-0.5 text-xs", on ? "border-zinc-800 bg-zinc-800 text-white" : "border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50")}>
            {label ? label(o) : o}
          </button>
        );
      })}
    </div>
  );
}

export function NewsTab({ settings, onChanged }: { settings: AllSettings; onChanged: () => void }) {
  const s = useSaver<NewsSettings>("news", settings.news, onChanged);
  const status = useApi(() => api.ingestStatus(), []);
  return (
    <div className="space-y-4">
      <Panel title="Topic preferences">
        <ChipSelect options={[...new Set([...TOPICS, ...s.v.topic_preferences])]} value={s.v.topic_preferences} onChange={(v) => s.set({ topic_preferences: v })} />
        <p className="mt-2 text-xs text-zinc-500">Leave empty to weight all topics equally. Selected topics boost relevance scoring.</p>
      </Panel>
      <Panel title="Ingest">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Max articles per feed">
            <Input type="number" min={1} value={s.v.max_articles_per_feed} onChange={(e) => s.set({ max_articles_per_feed: Number(e.target.value) })} />
          </Field>
          <Field label="Lookback days">
            <Input type="number" min={1} value={s.v.lookback_days} onChange={(e) => s.set({ lookback_days: Number(e.target.value) })} />
          </Field>
          <Field label={`Relevance threshold ${s.v.relevance_threshold}`}>
            <input type="range" min={0} max={1} step={0.05} value={s.v.relevance_threshold} onChange={(e) => s.set({ relevance_threshold: Number(e.target.value) })} className="mt-2 w-full" />
          </Field>
        </div>
        <p className="mt-2 text-xs text-zinc-500">Scheduled daily ingest at {settings.env.daily_ingest} (server local time).</p>
        <SaveBar s={s} />
      </Panel>
      <Panel title="Providers">
        <div className="flex flex-wrap gap-2">
          {(status.data?.providers ?? []).map((p) => (
            <span key={p.name} className="inline-flex items-center gap-1.5 rounded border border-zinc-200 bg-white px-2 py-1 text-xs">
              {p.name}
              <Badge variant={p.available ? "success" : "neutral"}>{p.available ? "available" : p.requires_key ? "needs key" : "unavailable"}</Badge>
            </span>
          ))}
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          {status.data?.last_ingest?.at ? `Last ingest ${relTime(status.data.last_ingest.at)}.` : "No ingest yet."}{" "}
          Manage feeds under{" "}
          <Link href="/research?tab=feeds" className="text-accent-strong hover:underline">
            Research → Feeds
          </Link>
          .
        </p>
      </Panel>
    </div>
  );
}

export function MediaTab({ settings, onChanged }: { settings: AllSettings; onChanged: () => void }) {
  const s = useSaver<MediaSettings>("media", settings.media, onChanged);
  const ff = settings.env.ffmpeg;
  return (
    <div className="space-y-4">
      <Panel title="Transcription">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Mode">
            <Select value={s.v.transcription_mode} onChange={(e) => s.set({ transcription_mode: e.target.value })} className="w-full">
              {["auto", "mlx_whisper", "faster_whisper", "whisper_cpp"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Model" hint="e.g. small, medium, large-v3">
            <Input value={s.v.transcription_model} onChange={(e) => s.set({ transcription_model: e.target.value })} placeholder={settings.env.transcription_recommendation.default_model} />
          </Field>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          Recommended on this machine: {settings.env.transcription_recommendation.runtime} — {settings.env.transcription_recommendation.why}
        </p>
      </Panel>
      <Panel title="Rendering">
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Default video size">
            <Select value={s.v.default_video_size} onChange={(e) => s.set({ default_video_size: e.target.value })} className="w-full">
              {["1080x1920", "1080x1350", "1080x1080", "1920x1080"].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Caption style">
            <Select value={s.v.caption_style} onChange={(e) => s.set({ caption_style: e.target.value })} className="w-full">
              {["bold_pop", "clean", "boxed"].map((v) => (
                <option key={v} value={v}>
                  {v}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Face tracking">
            <div className="pt-1.5">
              <Switch checked={s.v.face_tracking} onChange={(v) => s.set({ face_tracking: v })} label={s.v.face_tracking ? "on" : "off"} />
            </div>
          </Field>
        </div>
        <SaveBar s={s} />
      </Panel>
      <Panel title="FFmpeg">
        {ff.ok ? <Badge variant="success">available</Badge> : <Badge variant="danger">not found — install ffmpeg to index and render video</Badge>}
        <div className="mt-1 font-mono text-xs text-zinc-500">
          ffmpeg: {ff.ffmpeg ?? "—"} · ffprobe: {ff.ffprobe ?? "—"}
        </div>
      </Panel>
    </div>
  );
}

export function ContentTab({ settings, onChanged }: { settings: AllSettings; onChanged: () => void }) {
  const s = useSaver<ContentSettings>("content", settings.content, onChanged);
  return (
    <div className="space-y-4">
      <Panel title="Default platforms">
        <ChipSelect options={[...new Set([...PLATFORMS, ...s.v.default_platforms])]} value={s.v.default_platforms} onChange={(v) => s.set({ default_platforms: v })} label={labelFormat} />
      </Panel>
      <Panel title="Branding">
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Brand name">
            <Input value={s.v.brand_name} onChange={(e) => s.set({ brand_name: e.target.value })} />
          </Field>
          <Field label="Watermark text">
            <Input value={s.v.watermark_text} onChange={(e) => s.set({ watermark_text: e.target.value })} />
          </Field>
          <Field label="Watermark image path" className="md:col-span-2">
            <Input value={s.v.watermark_path} onChange={(e) => s.set({ watermark_path: e.target.value })} placeholder="/absolute/path/logo.png" />
          </Field>
          <Field label="Primary color">
            <div className="flex gap-2">
              <input type="color" value={s.v.primary_color} onChange={(e) => s.set({ primary_color: e.target.value })} className="h-8 w-10 rounded border border-zinc-300" />
              <Input value={s.v.primary_color} onChange={(e) => s.set({ primary_color: e.target.value })} />
            </div>
          </Field>
          <Field label="Accent color">
            <div className="flex gap-2">
              <input type="color" value={s.v.accent_color} onChange={(e) => s.set({ accent_color: e.target.value })} className="h-8 w-10 rounded border border-zinc-300" />
              <Input value={s.v.accent_color} onChange={(e) => s.set({ accent_color: e.target.value })} />
            </div>
          </Field>
        </div>
        <SaveBar s={s} />
      </Panel>
    </div>
  );
}

export function GithubTab({ settings, onChanged }: { settings: AllSettings; onChanged: () => void }) {
  const s = useSaver<GithubSettings>("github", settings.github, onChanged);
  return (
    <Panel title="Repository">
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Owner">
          <Input value={s.v.owner} onChange={(e) => s.set({ owner: e.target.value })} />
        </Field>
        <Field label="Repo">
          <Input value={s.v.repo} onChange={(e) => s.set({ repo: e.target.value })} />
        </Field>
        <Field label="Default branch">
          <Input value={s.v.default_branch} onChange={(e) => s.set({ default_branch: e.target.value })} />
        </Field>
      </div>
      <p className="mt-2 text-xs text-zinc-500">Informational only. Poly does not push, pull or publish anything to GitHub.</p>
      <SaveBar s={s} />
    </Panel>
  );
}

export function KeysTab({ settings }: { settings: AllSettings }) {
  const env = settings.env;
  const rows = [
    ["ANTHROPIC_API_KEY", env.anthropic_key_present, "Claude models (cloud AI)"],
    ["OPENAI_API_KEY", env.openai_key_present, "OpenAI models (cloud AI)"],
    ["BRAVE_API_KEY", env.brave_key_present, "Brave news search provider"],
    ["TAVILY_API_KEY", env.tavily_key_present, "Tavily research provider"],
    ["NEWSAPI_KEY", env.newsapi_key_present, "NewsAPI provider"],
  ] as const;
  return (
    <div className="space-y-4">
      <Panel title="API keys">
        <table className="w-full text-[13px]">
          <tbody>
            {rows.map(([k, present, desc]) => (
              <tr key={k} className="border-b border-zinc-100 last:border-b-0">
                <td className="py-1.5 font-mono text-xs">{k}</td>
                <td className="py-1.5 text-xs text-zinc-500">{desc}</td>
                <td className="py-1.5 text-right">
                  <Badge variant={present ? (k.includes("ANTHROPIC") || k.includes("OPENAI") ? "warn" : "success") : "neutral"}>{present ? "present" : "absent"}</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
      <Notice>
        Keys live in the backend <code className="font-mono">.env</code> file and are read only at startup; they are never stored in the database or displayed here. Cloud AI is disabled by default — a present key does nothing until you enable cloud AI under Privacy &amp; Network.
      </Notice>
      <Panel title="Environment">
        <dl className="grid grid-cols-[10rem_1fr] gap-y-1 text-xs">
          <dt className="text-zinc-500">Database</dt>
          <dd className="font-mono">
            {env.database} · {env.database_url_masked} {env.pgvector ? "· pgvector" : ""}
          </dd>
          <dt className="text-zinc-500">Data directory</dt>
          <dd className="font-mono">{env.data_dir}</dd>
          <dt className="text-zinc-500">Platform</dt>
          <dd className="font-mono">
            {env.platform}
            {env.apple_silicon ? " (Apple Silicon)" : ""}
          </dd>
          <dt className="text-zinc-500">Ollama URL</dt>
          <dd className="font-mono">{env.ollama_url}</dd>
          <dt className="text-zinc-500">OpenAI-compatible URLs</dt>
          <dd className="font-mono">{env.openai_compat_urls.join(", ") || "—"}</dd>
        </dl>
      </Panel>
    </div>
  );
}
