"use client";

import { AlertTriangle, Loader2 } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import type { DiffToken, ScoreCard } from "@/lib/types";
import { cn } from "@/lib/utils";

export function PageHeader({ title, description, actions }: { title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground mt-1 max-w-3xl text-sm">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="space-y-3" aria-busy="true">
      <div className="text-muted-foreground flex items-center gap-2 text-sm">
        <Loader2 className="size-4 animate-spin" /> {label}
      </div>
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

export function ErrorState({ error, title = "Something went wrong" }: { error: { message: string } | null; title?: string }) {
  if (!error) return null;
  return (
    <Alert variant="destructive">
      <AlertTitle className="flex items-center gap-2">
        <AlertTriangle className="size-4" /> {title}
      </AlertTitle>
      <AlertDescription className="text-destructive/90">{error.message}</AlertDescription>
    </Alert>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("size-4 animate-spin", className)} />;
}

const LEVEL_VARIANT = { direct: "success", partial: "warning", related: "outline", none: "destructive", unknown: "muted" } as const;

export function LevelBadge({ level, label }: { level: keyof typeof LEVEL_VARIANT; label?: string }) {
  return <Badge variant={LEVEL_VARIANT[level] ?? "muted"}>{label ?? level}</Badge>;
}

const VERIF_VARIANT: Record<string, "success" | "warning" | "destructive" | "muted" | "outline"> = {
  verified: "success", user_corrected: "success", unverified: "muted", needs_review: "warning", rejected: "destructive",
};

export function VerificationBadge({ status }: { status: string }) {
  return <Badge variant={VERIF_VARIANT[status] ?? "muted"}>{status.replace("_", " ")}</Badge>;
}

export function SeverityBadge({ severity }: { severity: string }) {
  const v = severity === "critical" ? "destructive" : severity === "warning" ? "warning" : "muted";
  return <Badge variant={v}>{severity}</Badge>;
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, "success" | "warning" | "destructive" | "muted" | "outline" | "secondary"> = {
    pass: "success", ok: "success", met: "success", approved: "success", applied: "secondary", offer: "success",
    warn: "warning", unclear: "warning", needs_user_input: "warning", draft: "muted", interviewing: "secondary",
    fail: "destructive", not_met: "destructive", error: "destructive", rejected: "destructive",
    unavailable: "outline", not_authorized: "outline", skipped: "outline",
  };
  return <Badge variant={map[status] ?? "outline"}>{status.replaceAll("_", " ")}</Badge>;
}

export function ScoreStat({ label, value, hint, suffix = "" }: { label: string; value: number | null | undefined; hint?: string; suffix?: string }) {
  const tone = value === null || value === undefined ? "text-muted-foreground" : value >= 80 ? "text-success" : value >= 60 ? "text-foreground" : "text-[oklch(0.5_0.12_60)]";
  return (
    <div className="bg-card rounded-xl border p-4">
      <div className="text-muted-foreground text-xs font-medium tracking-wide uppercase">{label}</div>
      <div className={cn("mt-1 text-3xl font-semibold tabular-nums", tone)}>
        {value === null || value === undefined ? "—" : value.toFixed(value % 1 === 0 ? 0 : 1)}
        {value !== null && value !== undefined && <span className="text-muted-foreground ml-0.5 text-base font-normal">{suffix}</span>}
      </div>
      {hint && <div className="text-muted-foreground mt-1 text-xs leading-snug">{hint}</div>}
    </div>
  );
}

export function ScoreCardView({ card }: { card: ScoreCard }) {
  return (
    <div className="space-y-4">
      {card.dimensions.map((d) => (
        <div key={d.key} className="space-y-1.5">
          <div className="flex items-baseline justify-between gap-3 text-sm">
            <span className="font-medium">{d.label}</span>
            <span className="text-muted-foreground shrink-0 tabular-nums">
              {d.points.toFixed(1)} / {d.weight} pts
            </span>
          </div>
          <Progress value={Math.round(d.score * 100)} aria-label={d.label} />
          <p className="text-muted-foreground text-xs">{d.explanation}</p>
          {d.details.length > 0 && (
            <details className="text-xs">
              <summary className="text-primary cursor-pointer select-none">Details</summary>
              <ul className="text-muted-foreground mt-1 list-disc space-y-0.5 pl-5">
                {d.details.map((x, i) => (
                  <li key={i}>{x}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      ))}
      {card.notes.map((n, i) => (
        <p key={i} className="text-muted-foreground border-l-2 pl-3 text-xs">
          {n}
        </p>
      ))}
    </div>
  );
}

export function DiffText({ tokens }: { tokens: DiffToken[] }) {
  return (
    <span>
      {tokens.map((t, i) =>
        t.op === "equal" ? <span key={i}>{t.text}</span> : <span key={i} className={t.op === "insert" ? "diff-insert" : "diff-delete"}>{t.text}</span>,
      )}
    </span>
  );
}

export const DISCLAIMER =
  "Scores are transparent heuristics computed by this tool. They are not an employer's ATS score and do not predict interview chances.";
