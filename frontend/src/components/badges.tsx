import { Badge } from "./ui/badge";
import { cn, labelFormat, labelStatus } from "@/lib/utils";

const STATUS_VARIANT: Record<string, "neutral" | "outline" | "accent" | "warn" | "success" | "danger" | "amber" | "violet" | "blue"> = {
  // content pipeline
  IDEA: "neutral",
  RESEARCHING: "blue",
  POSITION_DEVELOPED: "violet",
  SCRIPTING: "amber",
  RECORDED: "amber",
  EDITING: "amber",
  READY: "accent",
  PUBLISHED: "success",
  // principles
  provisional: "amber",
  established: "success",
  retired: "neutral",
  // stories
  new: "accent",
  developing: "blue",
  ignored: "neutral",
  // sessions
  active: "accent",
  completed: "success",
  abandoned: "neutral",
  draft: "amber",
  approved: "success",
  // transcripts
  none: "neutral",
  queued: "blue",
  running: "blue",
  done: "success",
  failed: "danger",
  error: "danger",
  // jobs
  succeeded: "success",
  // clips
  suggested: "neutral",
  selected: "blue",
  rendered: "success",
  dismissed: "neutral",
  // fact check
  not_run: "neutral",
  pending: "amber",
  fact_checked: "success",
  overridden: "warn",
};

export function StatusBadge({ status, className }: { status: string | null | undefined; className?: string }) {
  if (!status) return null;
  return (
    <Badge variant={STATUS_VARIANT[status] ?? "outline"} className={className}>
      {labelStatus(status)}
    </Badge>
  );
}

export function FormatBadge({ format, className }: { format: string | null | undefined; className?: string }) {
  if (!format) return null;
  return (
    <Badge variant="outline" className={cn("font-normal", className)}>
      {labelFormat(format)}
    </Badge>
  );
}

const CLAIM_TYPE_VARIANT: Record<string, "neutral" | "accent" | "amber" | "violet" | "blue" | "warn"> = {
  FACT: "accent",
  ANALYSIS: "blue",
  OPINION: "amber",
  COUNTERFACTUAL: "violet",
  PREDICTION: "warn",
};

/** Plain English for the machine taxonomy. Nobody reads "COUNTERFACTUAL" and thinks faster. */
const CLAIM_TYPE_LABEL: Record<string, string> = {
  FACT: "Reported",
  ANALYSIS: "Interpretation",
  OPINION: "Opinion",
  COUNTERFACTUAL: "Disputed",
  PREDICTION: "Forecast",
};

export function ClaimTypeBadge({ type }: { type: string }) {
  return <Badge variant={CLAIM_TYPE_VARIANT[type] ?? "neutral"}>{CLAIM_TYPE_LABEL[type] ?? labelFormat(type)}</Badge>;
}

const FC_VARIANT: Record<string, "success" | "amber" | "neutral" | "violet" | "danger" | "warn"> = {
  VERIFIED: "success",
  SUPPORTED_BUT_UNCERTAIN: "amber",
  OPINION: "neutral",
  COUNTERFACTUAL: "violet",
  UNVERIFIED: "danger",
  OUTDATED: "warn",
};

export const FACT_CHECK_STATUSES = ["VERIFIED", "SUPPORTED_BUT_UNCERTAIN", "OPINION", "COUNTERFACTUAL", "UNVERIFIED", "OUTDATED"];

export const FACT_CHECK_LABEL: Record<string, string> = {
  VERIFIED: "Checks out",
  SUPPORTED_BUT_UNCERTAIN: "Partly supported",
  OPINION: "Opinion",
  COUNTERFACTUAL: "Contradicted",
  UNVERIFIED: "Not checked",
  OUTDATED: "Out of date",
};

export function ClaimBadge({ status }: { status: string }) {
  return <Badge variant={FC_VARIANT[status] ?? "neutral"}>{FACT_CHECK_LABEL[status] ?? labelFormat(status)}</Badge>;
}

export function FactCheckDot({ status, className }: { status: string; className?: string }) {
  const color = { fact_checked: "bg-accent", overridden: "bg-highlight", pending: "bg-highlight/60", not_run: "bg-zinc-300" }[status] ?? "bg-zinc-300";
  return <span title={`Fact check: ${labelStatus(status)}`} className={cn("inline-block h-2 w-2 rounded-full", color, className)} />;
}

const RELATION_VARIANT: Record<string, "accent" | "warn" | "neutral" | "violet" | "success"> = {
  supports: "success",
  relates: "accent",
  challenges: "warn",
  contradicts: "warn",
  tests: "violet",
};

export function RelationBadge({ relation }: { relation: string }) {
  return <Badge variant={RELATION_VARIANT[relation] ?? "neutral"}>{relation}</Badge>;
}

export function Confidence({ value, className }: { value: number | null | undefined; className?: string }) {
  if (value == null) return <span className="text-zinc-400">—</span>;
  const p = Math.round(value * 100);
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)} title={`Confidence ${p}%`}>
      <span className="inline-block h-1.5 w-12 overflow-hidden bg-ink/12">
        <span className="block h-full bg-accent" style={{ width: `${p}%` }} />
      </span>
      <span className="font-mono text-[11px] text-zinc-600">{p}%</span>
    </span>
  );
}

export function Relevance({ value }: { value: number }) {
  const p = Math.round(value * 100);
  const tone = value >= 0.6 ? "text-accent-strong" : value >= 0.35 ? "text-zinc-700" : "text-zinc-400";
  return <span className={cn("font-mono text-[11px] tabular-nums", tone)}>{p}</span>;
}
