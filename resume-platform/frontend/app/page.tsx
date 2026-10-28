"use client";

import Link from "next/link";
import { ArrowRight, FilePlus2, ShieldCheck, UserRound } from "lucide-react";

import { ErrorState, Loading, PageHeader, ScoreStat, SeverityBadge, StatusBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { ApplicationRow, ProfileResponse, ResumeVersion, SystemStatus } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, score } from "@/lib/utils";

export default function Dashboard() {
  const status = useApi<SystemStatus>("/system/status");
  const hasProfile = status.data?.profile.exists;
  const profile = useApi<ProfileResponse>(hasProfile ? "/profile" : null);
  const apps = useApi<ApplicationRow[]>("/applications");
  const resumes = useApi<ResumeVersion[]>("/resumes");

  if (status.loading) return <Loading />;
  if (status.error) return <ErrorState error={status.error} title="Cannot reach the backend" />;
  const s = status.data!;
  const c = s.profile.completeness;

  if (!hasProfile) {
    return (
      <>
        <PageHeader title="Welcome" description="Upload your resume once. Every tailored resume is built from it, and nothing is added that it does not support." />
        <Card>
          <CardHeader>
            <CardTitle>Start with your master resume</CardTitle>
            <CardDescription>The platform extracts your experience, flags claims that need confirmation, and keeps the original wording as the source of truth.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button asChild>
              <Link href="/profile">
                <UserRound /> Upload master resume
              </Link>
            </Button>
          </CardContent>
        </Card>
      </>
    );
  }

  const openIssues = (profile.data?.profile.issues ?? []).filter((i) => i.status === "open" && i.severity !== "info");

  return (
    <>
      <PageHeader
        title="Dashboard"
        description={`Profile revision ${s.profile.revision} for ${s.profile.name}.`}
        actions={
          <Button asChild>
            <Link href="/jobs/new">
              <FilePlus2 /> Analyse a job
            </Link>
          </Button>
        }
      />
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <ScoreStat label="Profile completeness" value={c?.score ?? null} suffix="%" hint={`${c?.achievements_reviewed ?? 0} of ${c?.achievements_total ?? 0} achievements reviewed`} />
        <ScoreStat label="Open issues" value={c?.open_issues ?? 0} hint={`${c?.critical_issues ?? 0} critical`} />
        <ScoreStat label="Jobs analysed" value={s.counts.jobs} />
        <ScoreStat label="Resume versions" value={s.counts.resume_versions} />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Recent job matches</CardTitle>
            <CardDescription>Job fit is computed from your whole master profile.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {apps.loading && <Loading />}
            {apps.data?.length === 0 && <p className="text-muted-foreground text-sm">No jobs yet. Paste a posting to see how well you match.</p>}
            {apps.data?.slice(0, 6).map((a) => (
              <Link key={a.job_id} href={`/jobs/${a.job_id}`} className="hover:bg-muted/50 flex items-center justify-between gap-3 rounded-lg border p-3">
                <div className="min-w-0">
                  <div className="truncate font-medium">{a.title || "Untitled role"}</div>
                  <div className="text-muted-foreground truncate text-xs">
                    {[a.company, a.location].filter(Boolean).join(" · ")} · analysed {formatDate(a.analyzed_at)}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <StatusBadge status={a.application_status} />
                  <div className="w-24 text-right">
                    <div className="text-sm font-semibold tabular-nums">{score(a.job_fit)}</div>
                    <Progress value={a.job_fit ?? 0} className="mt-1 h-1.5" />
                  </div>
                </div>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-4" /> Needs your confirmation
            </CardTitle>
            <CardDescription>Claims are used as written until you verify, correct or reject them.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {openIssues.length === 0 && <p className="text-muted-foreground text-sm">Nothing waiting.</p>}
            {openIssues.slice(0, 6).map((i) => (
              <div key={i.id} className="flex gap-2 text-sm">
                <SeverityBadge severity={i.severity} />
                <span className="line-clamp-2">{i.message}</span>
              </div>
            ))}
            {openIssues.length > 0 && (
              <Button asChild variant="outline" size="sm" className="mt-2">
                <Link href="/profile">
                  Review in master profile <ArrowRight />
                </Link>
              </Button>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Recent resumes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {resumes.data?.length === 0 && <p className="text-muted-foreground text-sm">No resumes generated yet.</p>}
          {resumes.data?.slice(0, 5).map((r) => (
            <Link key={r.id} href={`/resumes/${r.id}`} className="hover:bg-muted/50 flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
              <span className="font-medium">
                {r.target_title} <span className="text-muted-foreground font-normal">v{r.version_no}</span>
              </span>
              <span className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">alignment {score(r.summary_scores.resume_alignment)}</Badge>
                <Badge variant="outline">ATS parse {score(r.summary_scores.ats_parsing)}</Badge>
                <StatusBadge status={r.status} />
              </span>
            </Link>
          ))}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>System</CardTitle>
        </CardHeader>
        <CardContent className="text-muted-foreground grid gap-2 text-sm sm:grid-cols-2">
          <div>Database: {s.database}</div>
          <div>LLM: {s.llm.provider === "none" ? "off (deterministic mode)" : `${s.llm.provider} ${s.llm.model ?? ""} ${s.llm.available ? "" : "(unavailable)"}`}</div>
          <div>External data sharing: {s.external_data_sharing ? "allowed" : "off"}</div>
          <div>Validators: {s.validators.filter((v) => v.available).map((v) => v.name).join(", ")}</div>
        </CardContent>
      </Card>
    </>
  );
}
