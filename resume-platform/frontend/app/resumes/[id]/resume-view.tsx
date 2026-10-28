"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowDown, ArrowUp, CheckCircle2, Download, FileArchive, Pencil, RotateCcw, Trash2 } from "lucide-react";

import { DISCLAIMER, DiffText, ErrorState, Loading, PageHeader, ScoreCardView, ScoreStat, SeverityBadge, Spinner, StatusBadge } from "@/components/common";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Comparison, ResumeBullet, ResumeVersion } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate } from "@/lib/utils";

export function ResumeView({ id }: { id: string }) {
  const router = useRouter();
  const v = useApi<ResumeVersion>(`/resumes/${id}`);
  const cmp = useApi<Comparison>(`/resumes/${id}/comparison`);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<ApiError | null>(null);

  async function run(label: string, fn: () => Promise<ResumeVersion>) {
    setBusy(label);
    setError(null);
    try {
      const out = await fn();
      if (out.id !== id) router.push(`/resumes/${out.id}`);
      else v.setData(out);
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(null);
    }
  }
  const edit = (ops: Record<string, unknown>[]) => run("Saving a new version…", () => api.post<ResumeVersion>(`/resumes/${id}/edits`, { ops }));

  if (v.loading) return <Loading />;
  if (v.error) return <ErrorState error={v.error} />;
  const r = v.data!;
  const content = r.content!;
  const val = r.validation!;
  const pdf = r.files.find((f) => f.kind === "pdf");
  const pending = (r.change_log ?? []).filter((c) => c.requires_approval);
  const unsupported = val.integrity.unsupported;
  const pageCount = Math.max(1, ...val.ats.filter((a) => a.document_kind === "pdf").map((a) => a.page_count || 1));

  return (
    <>
      <PageHeader
        title={`${content.header.target_title} · v${r.version_no}`}
        description={
          <>
            Created {formatDate(r.created_at)} · <StatusBadge status={r.status} />
            {r.job_id && (
              <>
                {" "}
                · <Link className="text-primary hover:underline" href={`/jobs/${r.job_id}`}>match report</Link>
              </>
            )}
          </>
        }
        actions={
          <>
            <Button variant="outline" asChild>
              <a href={`/api/resumes/${id}/export.zip`}>
                <FileArchive /> Download all
              </a>
            </Button>
            <Button
              disabled={!!busy || r.status === "approved" || unsupported > 0}
              onClick={() => run("Approving…", () => api.post<ResumeVersion>(`/resumes/${id}/approve`))}
              title={unsupported > 0 ? "Remove unsupported claims first" : ""}
            >
              {busy === "Approving…" ? <Spinner /> : <CheckCircle2 />} {r.status === "approved" ? "Approved" : "Approve final changes"}
            </Button>
          </>
        }
      />
      <ErrorState error={error} />
      {busy && (
        <div className="text-muted-foreground mb-3 flex items-center gap-2 text-sm">
          <Spinner /> {busy}
        </div>
      )}
      {unsupported > 0 && (
        <Alert variant="destructive" className="mb-4">
          <AlertTitle>{unsupported} claim(s) are not supported by your profile</AlertTitle>
          <AlertDescription>Approval is blocked until they are removed or backed by evidence. See the Validation tab.</AlertDescription>
        </Alert>
      )}
      {pending.length > 0 && r.status !== "approved" && (
        <Alert variant="warning" className="mb-4">
          <AlertTitle>{pending.length} wording change(s) await your approval</AlertTitle>
          <AlertDescription>They passed the fact check, but you have not approved them yet. Review them in Compare, edit if needed, then approve.</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <ScoreStat label="Resume alignment" value={r.summary_scores.resume_alignment} hint="How well this resume shows your fit" />
        <ScoreStat label="ATS parsing" value={r.summary_scores.ats_parsing} hint="Fields recovered after re-extraction" />
        <ScoreStat label="Evidence integrity" value={r.summary_scores.evidence_integrity} suffix="%" hint={`${val.integrity.unverified} claim(s) still unverified`} />
        <ScoreStat label="Job fit" value={r.summary_scores.job_fit} hint="Whole profile vs posting" />
      </div>
      <p className="text-muted-foreground mt-2 text-xs">{DISCLAIMER}</p>

      <Tabs defaultValue="preview" className="mt-6">
        <TabsList>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="compare">Compare</TabsTrigger>
          <TabsTrigger value="edit">Edit</TabsTrigger>
          <TabsTrigger value="validation">Validation</TabsTrigger>
          <TabsTrigger value="scores">Scores</TabsTrigger>
          <TabsTrigger value="export">Export</TabsTrigger>
        </TabsList>

        <TabsContent value="preview">
          <Card className="py-3">
            <CardContent className="space-y-3 px-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-muted-foreground text-xs">
                  Rendered from the generated PDF itself ({pageCount} page{pageCount > 1 ? "s" : ""}, {content.layout.body_font_size} pt body, {content.layout.font_family} font).
                </p>
                {pdf && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={`${pdf.url}?inline=true`} target="_blank" rel="noreferrer">
                      Open PDF
                    </a>
                  </Button>
                )}
              </div>
              {Array.from({ length: pageCount }, (_, i) => (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  key={i}
                  alt={`Page ${i + 1} of the generated resume`}
                  src={`/api/resumes/${id}/preview.png?page=${i + 1}&dpi=130`}
                  className="mx-auto w-full max-w-[850px] rounded-md border shadow-sm"
                />
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="compare">
          {cmp.loading && <Loading />}
          {cmp.data && <CompareView cmp={cmp.data} />}
        </TabsContent>

        <TabsContent value="edit">
          <EditView version={r} edit={edit} disabled={!!busy} />
        </TabsContent>

        <TabsContent value="validation" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Quality review · {val.qa.score.toFixed(0)}/100</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {val.qa.issues.length === 0 && <p className="text-muted-foreground text-sm">No issues.</p>}
              {val.qa.issues.map((i, k) => (
                <div key={k} className="flex gap-2 text-sm">
                  <SeverityBadge severity={i.severity} />
                  <span>
                    <span className="text-muted-foreground">{i.location}:</span> {i.message}
                    {i.suggestion && <span className="text-muted-foreground"> — {i.suggestion}</span>}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="py-2">
            <CardHeader className="pt-3">
              <CardTitle className="text-base">Evidence trace</CardTitle>
              <CardDescription>Every statement and the profile record it comes from.</CardDescription>
            </CardHeader>
            <CardContent className="px-2">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Section</TableHead>
                    <TableHead>Claim</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {val.integrity.claims.map((c, k) => (
                    <TableRow key={k}>
                      <TableCell className="text-muted-foreground text-xs">{c.location}</TableCell>
                      <TableCell className="text-sm">
                        {c.text}
                        {c.detail && <div className="text-muted-foreground mt-0.5 text-xs">{c.detail}</div>}
                      </TableCell>
                      <TableCell>
                        <Badge variant={c.status === "supported_verified" ? "success" : c.status === "supported_unverified" ? "warning" : "destructive"}>{c.status.replaceAll("_", " ")}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            {val.ats.map((a) => (
              <Card key={a.extractor + a.document_kind}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {a.extractor} · {a.document_kind.toUpperCase()} · {a.score.toFixed(1)}
                  </CardTitle>
                  <CardDescription>Field-by-field parse of the generated file.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-1 text-xs">
                  {a.fields.map((f) => (
                    <div key={f.field} className="flex items-start justify-between gap-2">
                      <span className="font-mono">{f.field}</span>
                      <StatusBadge status={f.status} />
                    </div>
                  ))}
                  {a.checks.map((c) => (
                    <div key={c.name} className="flex items-start justify-between gap-2">
                      <span>
                        {c.name.replaceAll("_", " ")} <span className="text-muted-foreground">{c.detail}</span>
                      </span>
                      <StatusBadge status={c.status} />
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Independent validators</CardTitle>
              <CardDescription>External scores appear only when a service actually returned one.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {val.external.map((e) => (
                <div key={e.adapter} className="flex flex-wrap items-center justify-between gap-2 rounded-md border p-2">
                  <span>
                    <span className="font-medium">{e.adapter}</span> <span className="text-muted-foreground">({e.category})</span>
                    <div className="text-muted-foreground text-xs">{e.detail}</div>
                  </span>
                  <span className="flex items-center gap-2">
                    {e.score !== null && <Badge variant="outline">{e.score.toFixed(1)}</Badge>}
                    <StatusBadge status={e.status} />
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="scores" className="space-y-4">
          {r.scores && (
            <div className="grid gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Resume alignment · {r.scores.resume_alignment.total.toFixed(1)}</CardTitle>
                </CardHeader>
                <CardContent>
                  <ScoreCardView card={r.scores.resume_alignment} />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Revision cycles</CardTitle>
                  <CardDescription>Stop reason: {r.scores.stop_reason.replaceAll("_", " ")}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 text-sm">
                  {r.scores.iterations.map((it) => (
                    <div key={it.iteration} className="rounded-md border p-2">
                      <div className="font-medium">Cycle {it.iteration}</div>
                      <div className="text-muted-foreground text-xs">
                        alignment {it.scores.resume_alignment?.toFixed(1)} · ATS {it.scores.ats_parsing?.toFixed(1)} · integrity {it.scores.evidence_integrity?.toFixed(1)} · QA {it.scores.qa?.toFixed(0)} · critical {it.scores.critical_issues}
                      </div>
                      {it.actions.length > 0 && (
                        <ul className="mt-1 list-disc pl-5 text-xs">
                          {it.actions.map((a, k) => (
                            <li key={k}>{a}</li>
                          ))}
                        </ul>
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          )}
        </TabsContent>

        <TabsContent value="export">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Files for this version</CardTitle>
              <CardDescription>Stored locally and kept with this version, so you can always recover exactly what you sent.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-2 sm:grid-cols-2">
              {r.files.map((f) => (
                <a key={f.id} href={f.url} className="hover:bg-muted/50 flex items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                  <span className="min-w-0">
                    <span className="block font-medium">{f.kind.replaceAll("_", " ")}</span>
                    <span className="text-muted-foreground block truncate text-xs">{f.filename}</span>
                  </span>
                  <Download className="size-4 shrink-0" />
                </a>
              ))}
            </CardContent>
          </Card>
          <Button
            variant="ghost"
            className="text-destructive mt-4"
            onClick={async () => {
              if (!confirm("Delete this resume version and its files?")) return;
              await api.del(`/resumes/${id}`);
              router.push(r.job_id ? `/jobs/${r.job_id}` : "/resumes");
            }}
          >
            <Trash2 /> Delete this version
          </Button>
        </TabsContent>
      </Tabs>
    </>
  );
}

function CompareView({ cmp }: { cmp: Comparison }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Master resume (source)</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="text-muted-foreground max-h-[28rem] overflow-auto text-xs whitespace-pre-wrap">{cmp.original_text}</pre>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Tailored resume</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="max-h-[28rem] overflow-auto text-xs whitespace-pre-wrap">{cmp.tailored_text}</pre>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Bullet changes</CardTitle>
          <CardDescription>
            <span className="diff-insert px-1">added</span> and <span className="diff-delete px-1">removed</span> words against your original wording. Each bullet links to its evidence record.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {cmp.bullets.map((b) => (
            <div key={b.target} className="rounded-lg border p-3 text-sm">
              <div className="mb-1 flex flex-wrap items-center gap-1.5">
                <Badge variant="outline">{b.origin.replace("_", " ")}</Badge>
                {b.approved ? <Badge variant="success">approved</Badge> : <Badge variant="warning">needs approval</Badge>}
                {b.position_before !== null && b.position_before !== b.position_after && (
                  <Badge variant="muted">
                    moved {b.position_before + 1} → {(b.position_after ?? 0) + 1}
                  </Badge>
                )}
                <span className="text-muted-foreground font-mono text-[10px]">{b.achievement_ids.join(", ")}</span>
              </div>
              {b.before.trim() === b.after.trim() ? <p>{b.after}</p> : <DiffText tokens={b.tokens} />}
            </div>
          ))}
        </CardContent>
      </Card>
      {cmp.omitted.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Left out of this version</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5 text-sm">
            {cmp.omitted.map((o, i) => (
              <div key={i}>
                <Badge variant="muted" className="mr-2">
                  {o.item_type}
                </Badge>
                {o.text.slice(0, 120)}
                <span className="text-muted-foreground"> — {o.reason}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function EditView({ version, edit, disabled }: { version: ResumeVersion; edit: (ops: Record<string, unknown>[]) => void; disabled: boolean }) {
  const content = version.content!;
  const [title, setTitle] = useState(content.header.target_title);
  const entries: { key: string; heading: string; bullets: ResumeBullet[] }[] = [
    ...content.experience.map((e) => ({ key: e.role_id, heading: `${e.title}, ${e.organization} (${e.date_range})`, bullets: e.bullets })),
    ...content.projects.map((p) => ({ key: p.project_id, heading: p.name, bullets: p.bullets })),
  ];
  return (
    <div className="space-y-4">
      <Alert variant="info">
        <AlertDescription>
          Every edit saves a new version and is re-checked against your evidence. Employers, titles and dates come from your profile and cannot be edited here; correct them in the master profile.
        </AlertDescription>
      </Alert>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Target title</CardTitle>
          <CardDescription>The posting&apos;s exact title, shown under your name. Only use a title you can back up in an interview.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Input value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button variant="outline" disabled={disabled || title === content.header.target_title} onClick={() => edit([{ op: "set_target_title", title }])}>
            Save
          </Button>
        </CardContent>
      </Card>
      {entries.map((e) => (
        <Card key={e.key}>
          <CardHeader>
            <CardTitle className="text-base">{e.heading}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {e.bullets.map((b, i) => (
              <BulletEditor key={b.id} bullet={b} index={i} total={e.bullets.length} edit={edit} disabled={disabled} />
            ))}
          </CardContent>
        </Card>
      ))}
      {content.omitted.filter((o) => o.item_type === "bullet").length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Restore a left-out bullet</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {content.omitted
              .filter((o) => o.item_type === "bullet")
              .map((o) => (
                <div key={o.item_id} className="flex items-start justify-between gap-3 text-sm">
                  <span>{o.text}</span>
                  <Button size="sm" variant="outline" disabled={disabled} onClick={() => edit([{ op: "restore_bullet", achievement_id: o.item_id }])}>
                    <RotateCcw /> Restore
                  </Button>
                </div>
              ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function BulletEditor({ bullet, index, total, edit, disabled }: { bullet: ResumeBullet; index: number; total: number; edit: (ops: Record<string, unknown>[]) => void; disabled: boolean }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(bullet.text);
  return (
    <div className="rounded-lg border p-3 text-sm">
      {editing ? (
        <div className="space-y-2">
          <Textarea value={text} onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2">
            <Button size="sm" disabled={disabled} onClick={() => edit([{ op: "set_bullet_text", bullet_id: bullet.id, text }])}>
              Save as new version
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p>{bullet.text}</p>
      )}
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {!bullet.approved && <Badge variant="warning">needs approval</Badge>}
        {bullet.flags
          .filter((f) => f.severity !== "info")
          .map((f, i) => (
            <Badge key={i} variant="destructive">
              {f.message}
            </Badge>
          ))}
        <span className="ml-auto flex gap-1">
          <Button size="icon" variant="ghost" aria-label="Move up" disabled={disabled || index === 0} onClick={() => edit([{ op: "move_bullet", bullet_id: bullet.id, to: index - 1 }])}>
            <ArrowUp />
          </Button>
          <Button size="icon" variant="ghost" aria-label="Move down" disabled={disabled || index === total - 1} onClick={() => edit([{ op: "move_bullet", bullet_id: bullet.id, to: index + 1 }])}>
            <ArrowDown />
          </Button>
          <Button size="icon" variant="ghost" aria-label="Edit" disabled={disabled} onClick={() => setEditing(true)}>
            <Pencil />
          </Button>
          <Button size="icon" variant="ghost" aria-label="Remove" disabled={disabled} onClick={() => edit([{ op: "remove_bullet", bullet_id: bullet.id }])}>
            <Trash2 />
          </Button>
        </span>
      </div>
    </div>
  );
}
