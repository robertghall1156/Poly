import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtDate(iso?: string | null, opts?: Intl.DateTimeFormatOptions): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, opts ?? { year: "numeric", month: "short", day: "numeric" });
}

export function fmtDateTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function relTime(iso?: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  const abs = Math.abs(diff);
  const m = Math.round(abs / 60000);
  const suffix = diff >= 0 ? "ago" : "from now";
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ${suffix}`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h}h ${suffix}`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d ${suffix}`;
  return fmtDate(iso);
}

export function fmtDuration(seconds?: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}

export function fmtTimestamp(seconds: number): string {
  const s = Math.max(0, seconds);
  const m = Math.floor(s / 60);
  const r = s - m * 60;
  return `${String(m).padStart(2, "0")}:${r.toFixed(1).padStart(4, "0")}`;
}

export function fmtBytes(bytes?: number | null): string {
  if (bytes == null) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function fmtNumber(n?: number | null): string {
  if (n == null) return "—";
  return new Intl.NumberFormat().format(n);
}

export function pct(n?: number | null, digits = 0): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function humanize(s?: string | null): string {
  if (!s) return "";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Plain-language, Title Case labels for pipeline and workflow statuses. */
const STATUS_LABEL: Record<string, string> = {
  IDEA: "Idea",
  RESEARCHING: "Researching",
  POSITION_DEVELOPED: "Position developed",
  SCRIPTING: "Scripting",
  RECORDED: "Recorded",
  EDITING: "Editing",
  READY: "Ready",
  PUBLISHED: "Published",
  draft: "Draft",
  approved: "Approved",
  provisional: "Still forming",
  established: "Settled",
  retired: "Retired",
  active: "In progress",
  completed: "Completed",
  abandoned: "Set aside",
  not_run: "Not checked yet",
  pending: "Being checked",
  fact_checked: "Facts checked",
  overridden: "Approved with a note",
};

export function labelStatus(s?: string | null): string {
  if (!s) return "";
  return STATUS_LABEL[s] ?? (s === s.toUpperCase() ? humanize(s.toLowerCase()) : humanize(s));
}

export function labelFormat(s?: string | null): string {
  if (!s) return "";
  const map: Record<string, string> = {
    youtube: "YouTube",
    youtube_short: "YouTube Short",
    tiktok: "TikTok",
    instagram_reel: "Instagram Reel",
    instagram_post: "Instagram Post",
    x_post: "X Post",
    x_thread: "X Thread",
    facebook_post: "Facebook Post",
    linkedin_post: "LinkedIn Post",
  };
  return map[s] ?? humanize(s);
}
