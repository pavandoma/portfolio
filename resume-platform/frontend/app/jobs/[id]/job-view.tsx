"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { FileText, RefreshCw, Sparkles, Trash2 } from "lucide-react";

import { DISCLAIMER, ErrorState, LevelBadge, Loading, PageHeader, ScoreCardView, ScoreStat, Spinner, StatusBadge } from "@/components/common";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { api, ApiError } from "@/lib/api";
import type { Job, MatchReport, ResumeVersion } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, score } from "@/lib/utils";

export function JobView({ id, duplicate }: { id: string; duplicate: boolean }) {
  const router = useRouter();
  const job = useApi<Job>(`/jobs/${id}`);
  const match = useApi<{ report: MatchReport }>(`/jobs/${id}/match`);
  const versions = useApi<ResumeVersion[]>(`/resumes?job_id=${id}`);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [pageTarget, setPageTarget] = useState("auto");

  async function generate() {
    setBusy("Generating, parsing and checking the resume…");
    setError(null);
    try {
      // One request (a few seconds): background tasks do not survive on serverless hosts such as Vercel.
      const version = await api.post<{ id: string }>("/resumes", {
        job_id: id,
        page_target: pageTarget === "auto" ? undefined : Number(pageTarget),
      });
      router.push(`/resumes/${version.id}`);
    } catch (e) {
      setError(e as ApiError);
      setBusy(null);
    }
  }

  async function rematch() {
    setBusy("Re-scoring…");
    try {
      const r = await api.post<{ report: MatchReport }>(`/jobs/${id}/match`);
      match.setData(r);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    if (!confirm("Delete this job, its match history and every resume generated for it?")) return;
    await api.del(`/jobs/${id}`);
    router.push("/jobs");
  }

  if (job.loading || match.loading) return <Loading label="Analysing…" />;
  if (job.error) return <ErrorState error={job.error} />;
  const j = job.data!;
  const a = j.analysis!;
  const r = match.data?.report;

  return (
    <>
      <PageHeader
        title={j.title || "Untitled role"}
        description={[j.company, j.location, a.work_arrangement !== "unknown" ? a.work_arrangement : null, a.seniority !== "unknown" ? `${a.seniority} level` : null]
          .filter(Boolean)
          .join(" · ")}
        actions={
          <>
            <Button variant="outline" onClick={rematch} disabled={!!busy}>
              <RefreshCw /> Re-score
            </Button>
            <Button variant="outline" onClick={remove} disabled={!!busy}>
              <Trash2 /> Delete
            </Button>
          </>
        }
      />
      {duplicate && (
        <Alert variant="warning" className="mb-4">
          <AlertTitle>Already analysed</AlertTitle>
          <AlertDescription>This posting matches one you analysed before (same URL, company and title, or text), so the existing record is shown.</AlertDescription>
        </Alert>
      )}
      {a.injection_warnings.length > 0 && (
        <Alert variant="warning" className="mb-4">
          <AlertTitle>Ignored suspicious text in the posting</AlertTitle>
          <AlertDescription>
            <ul className="list-disc pl-5">
              {a.injection_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}
      <ErrorState error={error} />
      {match.error && <ErrorState error={match.error} title="Could not score this job" />}

      {r && (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <ScoreStat label="Job fit" value={r.job_fit.total} hint="Your whole profile against this posting" />
            <ScoreStat label="Mandatory gaps" value={r.missing_mandatory.length} hint="Requirements your profile does not show" />
            <ScoreStat label="Gates needing attention" value={r.gates.filter((g) => g.status !== "met").length} hint="Years, degree, authorization; never scored" />
          </div>
          <p className="text-muted-foreground mt-2 text-xs">{DISCLAIMER}</p>

          <Card className="mt-6">
            <CardHeader>
              <CardTitle>Generate a tailored resume</CardTitle>
              <CardDescription>
                Builds from your verified profile, renders PDF and DOCX, re-parses them, checks every claim against your evidence and revises up to three times.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="pages">Page target</Label>
                <select id="pages" value={pageTarget} onChange={(e) => setPageTarget(e.target.value)} className="border-input bg-card h-9 rounded-md border px-3 text-sm">
                  <option value="auto">Automatic</option>
                  <option value="1">One page</option>
                  <option value="2">Two pages</option>
                </select>
              </div>
              <Button onClick={generate} disabled={!!busy}>
                {busy ? <Spinner /> : <Sparkles />} {busy ?? "Generate resume"}
              </Button>
            </CardContent>
            {versions.data && versions.data.length > 0 && (
              <CardContent className="space-y-2">
                {versions.data.map((v) => (
                  <Link key={v.id} href={`/resumes/${v.id}`} className="hover:bg-muted/50 flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                    <span className="flex items-center gap-2 font-medium">
                      <FileText className="size-4" /> Version {v.version_no}
                      <span className="text-muted-foreground font-normal">{formatDate(v.created_at)}</span>
                    </span>
                    <span className="flex flex-wrap gap-2">
                      <Badge variant="outline">alignment {score(v.summary_scores.resume_alignment)}</Badge>
                      <Badge variant="outline">integrity {score(v.summary_scores.evidence_integrity)}%</Badge>
                      <StatusBadge status={v.status} />
                    </span>
                  </Link>
                ))}
              </CardContent>
            )}
          </Card>

          <Tabs defaultValue="requirements" className="mt-6">
            <TabsList>
              <TabsTrigger value="requirements">Requirements</TabsTrigger>
              <TabsTrigger value="score">Score breakdown</TabsTrigger>
              <TabsTrigger value="gates">Eligibility</TabsTrigger>
              <TabsTrigger value="advice">Gaps & advice</TabsTrigger>
              <TabsTrigger value="posting">Posting</TabsTrigger>
            </TabsList>
            <TabsContent value="requirements">
              <Card className="py-2">
                <CardContent className="px-2">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="w-[38%]">Requirement</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Evidence</TableHead>
                        <TableHead>Why</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {r.requirement_matches.map((m) => (
                        <TableRow key={m.requirement_id}>
                          <TableCell>
                            <div>{m.requirement_text}</div>
                          </TableCell>
                          <TableCell>
                            <Badge variant={m.category === "mandatory" ? "secondary" : "outline"}>{m.category}</Badge>
                          </TableCell>
                          <TableCell>
                            <LevelBadge level={m.level} label={m.level_label} />
                          </TableCell>
                          <TableCell className="text-muted-foreground text-xs">
                            {m.explanation}
                            {m.evidence.slice(0, 2).map((e, i) => (
                              <div key={i} className="mt-1 border-l-2 pl-2 italic">
                                {e.excerpt || e.reason}
                              </div>
                            ))}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="score">
              <Card>
                <CardContent>
                  <ScoreCardView card={r.job_fit} />
                  <p className="text-muted-foreground mt-4 text-xs">
                    Scoring {r.scoring_version}; input hash {r.input_hash.slice(0, 12)}. The same profile, posting and weights always give the same result.
                  </p>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="gates">
              <Card>
                <CardContent className="space-y-3">
                  {r.gates.length === 0 && <p className="text-muted-foreground text-sm">No eligibility gates found in this posting.</p>}
                  {r.gates.map((g, i) => (
                    <div key={i} className="rounded-lg border p-3">
                      <div className="flex items-center gap-2">
                        <StatusBadge status={g.status} /> <span className="text-sm font-medium">{g.gate.replaceAll("_", " ")}</span>
                      </div>
                      <p className="mt-1 text-sm">{g.requirement_text}</p>
                      <p className="text-muted-foreground mt-1 text-xs">{g.explanation}</p>
                    </div>
                  ))}
                  <p className="text-muted-foreground text-xs">Gates are never folded into the score, and ambiguous ones are never treated as a rejection.</p>
                </CardContent>
              </Card>
            </TabsContent>
            <TabsContent value="advice">
              <div className="grid gap-4 md:grid-cols-2">
                <ListCard title="Strongest matches" items={r.strengths} empty="Nothing directly demonstrated yet." />
                <ListCard title="Missing mandatory" items={r.missing_mandatory} empty="None." />
                <ListCard title="Missing preferred" items={r.missing_preferred} empty="None." />
                <ListCard title="Recommendations" items={r.recommendations} empty="None." />
              </div>
            </TabsContent>
            <TabsContent value="posting">
              <Card>
                <CardContent>
                  <pre className="text-muted-foreground max-h-[32rem] overflow-auto text-xs whitespace-pre-wrap">{j.raw_text}</pre>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}

function ListCard({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {items.length === 0 ? (
          <p className="text-muted-foreground text-sm">{empty}</p>
        ) : (
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {items.map((x, i) => (
              <li key={i}>{x}</li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
