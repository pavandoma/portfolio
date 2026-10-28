"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Check, FileUp, GitBranch, Pencil, Plus, Sparkles, Trash2, Undo2, X } from "lucide-react";

import { ErrorState, Loading, PageHeader, SeverityBadge, Spinner, VerificationBadge } from "@/components/common";
import { FileDrop } from "@/components/file-drop";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Achievement, CandidateProfile, Issue, ProfileResponse, Project, Role, SystemStatus } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate } from "@/lib/utils";

type Mutate = (fn: () => Promise<ProfileResponse>) => Promise<void>;

export default function ProfilePage() {
  const profile = useApi<ProfileResponse>("/profile");
  const status = useApi<SystemStatus>("/system/status");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const mutate: Mutate = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      profile.setData(await fn());
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  };

  const importResume = (file: File) => mutate(() => api.upload<ProfileResponse>("/profile/import", file));

  if (profile.loading) return <Loading />;
  if (profile.error && profile.error.status !== 404) return <ErrorState error={profile.error} />;

  if (!profile.data) {
    return (
      <>
        <PageHeader title="Master profile" description="Upload your current resume. It becomes the single source of truth for every tailored version." />
        <FileDrop accept=".pdf,.docx,.txt" onFile={importResume} disabled={busy} label={busy ? "Reading your resume…" : "Upload your master resume"} />
        <div className="mt-4">
          <ErrorState error={error} title="Import failed" />
        </div>
      </>
    );
  }

  const { profile: p, completeness: c, revision } = profile.data;
  const llmOn = !!status.data?.llm.available;
  const openIssues = p.issues.filter((i) => i.status === "open");

  return (
    <>
      <PageHeader
        title={p.personal.name || "Master profile"}
        description={`Revision ${revision.number} · ${revision.reason}. Every change creates a new revision; the original wording is always kept.`}
        actions={
          <>
            <UploadButton label="Re-import resume" accept=".pdf,.docx,.txt" onFile={importResume} disabled={busy} />
            <UploadButton label="Add wording pack" accept=".yaml,.yml,.json" onFile={(f) => mutate(() => api.upload<ProfileResponse>("/profile/suggestion-pack", f))} disabled={busy} />
          </>
        }
      />
      <div className="mb-4 grid gap-4 sm:grid-cols-3">
        <Card className="py-4">
          <CardContent>
            <div className="text-muted-foreground text-xs uppercase">Completeness</div>
            <div className="mt-1 text-2xl font-semibold">{c.score}%</div>
            <Progress value={c.score} className="mt-2" />
          </CardContent>
        </Card>
        <Card className="py-4">
          <CardContent>
            <div className="text-muted-foreground text-xs uppercase">Achievements reviewed</div>
            <div className="mt-1 text-2xl font-semibold">
              {c.achievements_reviewed} / {c.achievements_total}
            </div>
          </CardContent>
        </Card>
        <Card className="py-4">
          <CardContent>
            <div className="text-muted-foreground text-xs uppercase">Open issues</div>
            <div className="mt-1 text-2xl font-semibold">
              {c.open_issues} <span className="text-destructive text-sm font-normal">{c.critical_issues} critical</span>
            </div>
          </CardContent>
        </Card>
      </div>
      <ErrorState error={error} />
      {busy && (
        <div className="text-muted-foreground mb-3 flex items-center gap-2 text-sm">
          <Spinner /> Saving…
        </div>
      )}

      <Tabs defaultValue={openIssues.length ? "issues" : "experience"}>
        <TabsList>
          <TabsTrigger value="issues">Review ({openIssues.length})</TabsTrigger>
          <TabsTrigger value="experience">Experience & projects</TabsTrigger>
          <TabsTrigger value="skills">Skills</TabsTrigger>
          <TabsTrigger value="personal">Personal & eligibility</TabsTrigger>
          <TabsTrigger value="education">Education</TabsTrigger>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="history">History & data</TabsTrigger>
        </TabsList>
        <TabsContent value="issues">
          <IssuesPanel profile={p} issues={openIssues} mutate={mutate} />
        </TabsContent>
        <TabsContent value="experience" className="space-y-4">
          {p.roles.map((r) => (
            <ParentCard key={r.id} parent={r} kind="role" mutate={mutate} llmOn={llmOn} />
          ))}
          {p.projects.map((pr) => (
            <ParentCard key={pr.id} parent={pr} kind="project" mutate={mutate} llmOn={llmOn} />
          ))}
        </TabsContent>
        <TabsContent value="skills">
          <SkillsPanel profile={p} mutate={mutate} />
        </TabsContent>
        <TabsContent value="personal">
          <PersonalPanel profile={p} mutate={mutate} />
        </TabsContent>
        <TabsContent value="education">
          <EducationPanel profile={p} mutate={mutate} />
        </TabsContent>
        <TabsContent value="evidence">
          <EvidencePanel profile={p} mutate={mutate} />
        </TabsContent>
        <TabsContent value="history" className="space-y-4">
          <HistoryPanel />
          <DeleteAllData />
        </TabsContent>
      </Tabs>
    </>
  );
}

function UploadButton({ label, accept, onFile, disabled }: { label: string; accept: string; onFile: (f: File) => void; disabled?: boolean }) {
  return (
    <Button variant="outline" asChild disabled={disabled}>
      <label className="cursor-pointer">
        <FileUp /> {label}
        <input
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onFile(f);
            e.target.value = "";
          }}
        />
      </label>
    </Button>
  );
}

const patchItem = (id: string, patch: Record<string, unknown>) => api.patch<ProfileResponse>(`/profile/items/${id}`, { patch });

function IssuesPanel({ profile, issues, mutate }: { profile: CandidateProfile; issues: Issue[]; mutate: Mutate }) {
  if (issues.length === 0) {
    return (
      <Alert variant="info">
        <AlertDescription>Nothing waiting for review. Claims you verified are marked as such on every resume&apos;s evidence report.</AlertDescription>
      </Alert>
    );
  }
  const order = { critical: 0, warning: 1, info: 2 };
  const sorted = [...issues].sort((a, b) => order[a.severity] - order[b.severity]);
  const setIssue = (id: string, status: string) => mutate(() => api.post<ProfileResponse>(`/profile/issues/${id}`, { status }));
  return (
    <div className="space-y-3">
      {sorted.map((i) => {
        const ach = i.target_id ? findAchievement(profile, i.target_id) : null;
        return (
          <Card key={i.id} className="gap-3 py-4">
            <CardContent className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={i.severity} />
                <Badge variant="outline">{i.kind.replaceAll("_", " ")}</Badge>
              </div>
              <p className="text-sm">{i.message}</p>
              {ach && <p className="text-muted-foreground border-l-2 pl-3 text-xs italic">{ach.original_text}</p>}
              <div className="flex flex-wrap gap-2">
                {i.target_id && i.kind !== "conflict" && (
                  <>
                    <Button size="sm" variant="outline" onClick={() => mutate(() => patchItem(i.target_id!, { verification: "verified" }))}>
                      <Check /> It&apos;s accurate
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => mutate(() => patchItem(i.target_id!, { verification: "rejected" }))}>
                      <X /> Not accurate, don&apos;t use
                    </Button>
                  </>
                )}
                {i.kind === "conflict" && i.field?.startsWith("personal.") &&
                  i.options.map((opt) => (
                    <Button key={opt} size="sm" variant="outline" onClick={() => mutate(async () => {
                      await api.patch(`/profile/personal`, { [i.field!.split(".")[1]]: opt });
                      return api.post<ProfileResponse>(`/profile/issues/${i.id}`, { status: "resolved", resolution: opt });
                    })}>
                      Use {opt}
                    </Button>
                  ))}
                {i.field === "employment_type" &&
                  i.options.map((opt) => (
                    <Button key={opt} size="sm" variant="outline" onClick={() => mutate(async () => {
                      await patchItem(i.target_id!, { employment_type: opt });
                      return api.post<ProfileResponse>(`/profile/issues/${i.id}`, { status: "resolved", resolution: opt });
                    })}>
                      {opt.replaceAll("_", " ")}
                    </Button>
                  ))}
                <Button size="sm" variant="ghost" onClick={() => setIssue(i.id, "dismissed")}>
                  Dismiss
                </Button>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function findAchievement(p: CandidateProfile, id: string): Achievement | null {
  for (const parent of [...p.roles, ...p.projects]) {
    const a = parent.achievements.find((x) => x.id === id);
    if (a) return a;
  }
  return null;
}

function ParentCard({ parent, kind, mutate, llmOn }: { parent: Role | Project; kind: "role" | "project"; mutate: Mutate; llmOn: boolean }) {
  const [adding, setAdding] = useState(false);
  const [text, setText] = useState("");
  const title = kind === "role" ? `${(parent as Role).title}, ${(parent as Role).organization}` : (parent as Project).name;
  const sub = kind === "role" ? `${(parent as Role).date_text} · ${(parent as Role).location ?? ""}` : `${(parent as Project).context} project`;
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          {title} <VerificationBadge status={parent.verification} />
        </CardTitle>
        <CardDescription>{sub}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {parent.achievements.map((a) => (
          <AchievementRow key={a.id} a={a} mutate={mutate} llmOn={llmOn} />
        ))}
        {adding ? (
          <div className="space-y-2 rounded-lg border p-3">
            <Label>New achievement (you confirm it is accurate)</Label>
            <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Action verb + what you did + how + result. Use real numbers only." />
            <div className="flex gap-2">
              <Button size="sm" disabled={text.trim().length < 10} onClick={() => mutate(() => api.post<ProfileResponse>("/profile/achievements", { parent_id: parent.id, text })).then(() => { setAdding(false); setText(""); })}>
                Save
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setAdding(false)}>
                Cancel
              </Button>
            </div>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setAdding(true)}>
            <Plus /> Add achievement
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

function AchievementRow({ a, mutate, llmOn }: { a: Achievement; mutate: Mutate; llmOn: boolean }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(a.text);
  const [wording, setWording] = useState("");
  const serious = a.flags.filter((f) => f.severity !== "info");
  return (
    <div className="rounded-lg border p-3">
      <div className="flex flex-wrap items-center gap-2">
        <VerificationBadge status={a.verification} />
        {a.allowed_usage !== "any" && <Badge variant="warning">{a.allowed_usage.replaceAll("_", " ")}</Badge>}
        {a.metrics.map((m) => (
          <Badge key={m.raw} variant="outline">
            {m.raw}
          </Badge>
        ))}
      </div>
      {editing ? (
        <div className="mt-2 space-y-2">
          <Textarea value={draft} onChange={(e) => setDraft(e.target.value)} />
          <p className="text-muted-foreground text-xs">A correction becomes the wording used on resumes; the original stays on record as the source.</p>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => mutate(() => patchItem(a.id, { text: draft })).then(() => setEditing(false))}>
              Save correction
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <p className="mt-2 text-sm">{a.text}</p>
      )}
      {a.text !== a.original_text && <p className="text-muted-foreground mt-1 text-xs">Original: {a.original_text}</p>}
      {serious.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs">
          {serious.map((f, i) => (
            <li key={i} className={f.severity === "critical" ? "text-destructive" : "text-[oklch(0.45_0.1_70)]"}>
              {f.message}
            </li>
          ))}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        <Button size="sm" variant="outline" onClick={() => mutate(() => patchItem(a.id, { verification: "verified" }))}>
          <Check /> Verify
        </Button>
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          <Pencil /> Correct
        </Button>
        <Button size="sm" variant="outline" onClick={() => mutate(() => patchItem(a.id, { verification: "rejected" }))}>
          <X /> Reject
        </Button>
        {a.verification !== "unverified" && (
          <Button size="sm" variant="ghost" onClick={() => mutate(() => patchItem(a.id, { verification: "unverified" }))}>
            <Undo2 /> Reset
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={!llmOn} title={llmOn ? "" : "Configure an LLM provider to enable suggestions"} onClick={() => mutate(() => api.post<ProfileResponse>(`/profile/achievements/${a.id}/suggest`))}>
          <Sparkles /> Suggest wording
        </Button>
      </div>
      {a.variants.length > 0 && (
        <details className="mt-3">
          <summary className="text-primary cursor-pointer text-xs font-medium">Alternative wording ({a.variants.length})</summary>
          <div className="mt-2 space-y-2">
            {a.variants.map((v) => (
              <div key={v.id} className="bg-muted/40 rounded-md p-2 text-sm">
                <div className="mb-1 flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline">{v.origin.replace("_", " ")}</Badge>
                  {v.emphasis.includes("summary") && <Badge variant="muted">summary line</Badge>}
                  {v.fact_check && !v.fact_check.passed ? <Badge variant="destructive">failed fact check</Badge> : <Badge variant="success">facts preserved</Badge>}
                  {v.approved ? <Badge variant="success">approved</Badge> : <Badge variant="warning">pending approval</Badge>}
                </div>
                <p>{v.text}</p>
                {v.fact_check && !v.fact_check.passed && <p className="text-destructive mt-1 text-xs">{v.fact_check.problems.join("; ")}</p>}
                {(!v.fact_check || v.fact_check.passed) && (
                  <Button size="sm" variant="ghost" className="mt-1" onClick={() => mutate(() => api.post<ProfileResponse>(`/profile/achievements/${a.id}/variants/${v.id}/approval`, { approved: !v.approved }))}>
                    {v.approved ? "Withdraw approval" : "Approve wording"}
                  </Button>
                )}
              </div>
            ))}
          </div>
        </details>
      )}
      <div className="mt-3 flex gap-2">
        <Input value={wording} onChange={(e) => setWording(e.target.value)} placeholder="Add your own wording (checked against the original)" className="h-8 text-xs" />
        <Button size="sm" variant="outline" disabled={wording.trim().length < 10} onClick={() => mutate(() => api.post<ProfileResponse>(`/profile/achievements/${a.id}/variants`, { text: wording })).then(() => setWording(""))}>
          Add
        </Button>
      </div>
    </div>
  );
}

function SkillsPanel({ profile, mutate }: { profile: CandidateProfile; mutate: Mutate }) {
  return (
    <Card className="py-2">
      <CardContent className="px-2">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Skill</TableHead>
              <TableHead>Source</TableHead>
              <TableHead>Evidence</TableHead>
              <TableHead>Status</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {profile.skills.map((s) => (
              <TableRow key={s.id}>
                <TableCell className="font-medium">
                  {s.display}
                  {s.display !== s.name && <span className="text-muted-foreground ml-1 text-xs">({s.name})</span>}
                </TableCell>
                <TableCell className="text-muted-foreground text-xs">{s.derived_from_bullets ? "found in bullets" : s.category ?? "skills list"}</TableCell>
                <TableCell>
                  {s.evidence_achievement_ids.length > 0 ? (
                    <Badge variant="success">{s.evidence_achievement_ids.length} bullet(s)</Badge>
                  ) : (
                    <Badge variant="warning">listed only</Badge>
                  )}
                </TableCell>
                <TableCell>
                  <VerificationBadge status={s.verification} />
                </TableCell>
                <TableCell className="text-right whitespace-nowrap">
                  <Button size="sm" variant="ghost" onClick={() => mutate(() => patchItem(s.id, { verification: "verified" }))}>
                    Verify
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => mutate(() => patchItem(s.id, { verification: "rejected" }))}>
                    Remove
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function PersonalPanel({ profile, mutate }: { profile: CandidateProfile; mutate: Mutate }) {
  const p = profile.personal;
  const [form, setForm] = useState({ name: p.name, email: p.email ?? "", phone: p.phone ?? "", location: p.location ?? "" });
  const [links, setLinks] = useState(p.links.map((l) => `${l.label}|${l.url}`).join("\n"));
  const wa = profile.work_authorization;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Contact details</CardTitle>
          <CardDescription>Shown in the resume header (never in a page header or footer).</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {(["name", "email", "phone", "location"] as const).map((k) => (
            <div key={k} className="space-y-1">
              <Label htmlFor={k} className="capitalize">
                {k}
              </Label>
              <Input id={k} value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} placeholder={k === "location" ? "City, ST" : ""} />
            </div>
          ))}
          <div className="space-y-1">
            <Label htmlFor="links">Links (one per line: Label|https://…)</Label>
            <Textarea id="links" value={links} onChange={(e) => setLinks(e.target.value)} className="min-h-20 font-mono text-xs" />
          </div>
          <Button
            onClick={() =>
              mutate(() =>
                api.patch<ProfileResponse>("/profile/personal", {
                  ...form,
                  links: links
                    .split("\n")
                    .map((l) => l.trim())
                    .filter(Boolean)
                    .map((l) => {
                      const [label, url] = l.includes("|") ? l.split("|") : ["Website", l];
                      return { label: label.trim(), url: url.trim() };
                    }),
                }),
              )
            }
          >
            Save contact details
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Work authorization</CardTitle>
          <CardDescription>Used only to evaluate eligibility gates in postings. Never printed on a resume.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <select
            value={wa.status}
            onChange={(e) => mutate(() => api.patch<ProfileResponse>("/profile/work-authorization", { status: e.target.value }))}
            className="border-input bg-card h-9 w-full rounded-md border px-3 text-sm"
          >
            {[
              ["unknown", "Not specified"],
              ["citizen", "Citizen"],
              ["permanent_resident", "Permanent resident"],
              ["authorized_no_sponsorship", "Authorized, no sponsorship needed"],
              ["authorized_requires_future_sponsorship", "Authorized now, will need sponsorship later"],
              ["requires_sponsorship", "Requires sponsorship"],
            ].map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!!wa.has_security_clearance}
              onChange={(e) => mutate(() => api.patch<ProfileResponse>("/profile/work-authorization", { has_security_clearance: e.target.checked }))}
            />
            I hold an active security clearance
          </label>
        </CardContent>
      </Card>
    </div>
  );
}

function EducationPanel({ profile, mutate }: { profile: CandidateProfile; mutate: Mutate }) {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Education</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {profile.education.map((e) => (
            <div key={e.id} className="flex items-start justify-between gap-3 rounded-lg border p-3 text-sm">
              <div>
                <div className="font-medium">{e.degree}</div>
                <div className="text-muted-foreground">
                  {e.institution} · {e.date_text} · {e.status}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <VerificationBadge status={e.verification} />
                <Button size="sm" variant="ghost" onClick={() => mutate(() => patchItem(e.id, { verification: "verified" }))}>
                  Verify
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Certifications</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {profile.certifications.map((c) => (
            <div key={c.id} className="flex items-start justify-between gap-3 rounded-lg border p-3 text-sm">
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-muted-foreground">
                  {c.detail} · {c.date_text}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <VerificationBadge status={c.verification} />
                <Button size="sm" variant="ghost" onClick={() => mutate(() => patchItem(c.id, { verification: "verified" }))}>
                  Verify
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function EvidencePanel({ profile, mutate }: { profile: CandidateProfile; mutate: Mutate }) {
  const [repo, setRepo] = useState("");
  const [note, setNote] = useState({ title: "", uri: "", description: "" });
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Add supporting evidence</CardTitle>
          <CardDescription>Repositories support technology claims. Metrics stay unverified until you confirm them.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="repo">GitHub repository</Label>
            <div className="flex gap-2">
              <Input id="repo" value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="https://github.com/you/project" />
              <Button variant="outline" disabled={!repo.includes("github.com/")} onClick={() => mutate(() => api.post<ProfileResponse>("/profile/evidence/github", { url: repo })).then(() => setRepo(""))}>
                <GitBranch /> Link
              </Button>
            </div>
          </div>
          <div className="space-y-2">
            <Label>Link or note (certificate URL, publication, demo)</Label>
            <Input value={note.title} onChange={(e) => setNote({ ...note, title: e.target.value })} placeholder="Title" />
            <Input value={note.uri} onChange={(e) => setNote({ ...note, uri: e.target.value })} placeholder="https://… (optional)" />
            <Textarea value={note.description} onChange={(e) => setNote({ ...note, description: e.target.value })} placeholder="What it shows" className="min-h-16" />
            <Button variant="outline" disabled={note.title.length < 2} onClick={() => mutate(() => api.post<ProfileResponse>("/profile/evidence", { kind: note.uri ? "link" : "note", ...note, uri: note.uri || null })).then(() => setNote({ title: "", uri: "", description: "" }))}>
              Add evidence
            </Button>
          </div>
          <div className="space-y-1">
            <Label>Supporting document</Label>
            <UploadButton label="Upload document" accept=".pdf,.docx,.txt" onFile={(f) => mutate(() => api.upload<ProfileResponse>("/profile/documents", f))} />
            <p className="text-muted-foreground text-xs">Another resume version or a LinkedIn export. Differences in titles or contact details are raised for you to resolve.</p>
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Evidence on file ({profile.evidence.length})</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {profile.evidence.length === 0 && <p className="text-muted-foreground text-sm">None yet.</p>}
          {profile.evidence.map((e) => (
            <div key={e.id} className="rounded-lg border p-3 text-sm">
              <div className="flex items-center gap-2 font-medium">
                <Badge variant="outline">{e.kind}</Badge> {e.uri ? <a className="hover:underline" href={e.uri} target="_blank" rel="noreferrer">{e.title}</a> : e.title}
              </div>
              {e.description && <p className="text-muted-foreground mt-1 text-xs">{e.description}</p>}
              {e.technologies.length > 0 && <p className="text-muted-foreground mt-1 text-xs">Technologies: {e.technologies.join(", ")}</p>}
              <p className="text-muted-foreground mt-1 text-xs">Linked to {e.linked_ids.length} achievement(s)</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function HistoryPanel() {
  const revs = useApi<{ id: string; number: number; reason: string; created_at: string }[]>("/profile/revisions");
  const audit = useApi<{ id: string; entity_type: string; action: string; created_at: string; actor: string }[]>("/audit?limit=60");
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Profile revisions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5 text-sm">
          {revs.data?.map((r) => (
            <div key={r.id} className="flex justify-between gap-3">
              <span>
                <span className="font-medium">#{r.number}</span> {r.reason}
              </span>
              <span className="text-muted-foreground shrink-0 text-xs">{formatDate(r.created_at)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audit trail</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1.5 text-sm">
          {audit.data?.map((a) => (
            <div key={a.id} className="flex justify-between gap-3">
              <span>
                {a.entity_type} · {a.action.replaceAll("_", " ")}
              </span>
              <span className="text-muted-foreground shrink-0 text-xs">{formatDate(a.created_at)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

const PURGE_PHRASE = "DELETE ALL MY DATA";

function DeleteAllData() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const purge = async () => {
    setBusy(true);
    setError(null);
    try {
      await api.post("/system/purge", { confirm: text });
      router.push("/");
    } catch (e) {
      setError(e as ApiError);
      setBusy(false);
    }
  };

  return (
    <Card className="border-destructive/40">
      <CardHeader>
        <CardTitle className="text-base">Delete all my data</CardTitle>
        <CardDescription>
          Permanently removes your profile and its revisions, uploaded documents, jobs, match reports, resume versions,
          generated files and application history from this machine. Download anything you want to keep first.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <Label htmlFor="purge-confirm">
          Type <span className="font-mono">{PURGE_PHRASE}</span> to confirm
        </Label>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Input id="purge-confirm" value={text} onChange={(e) => setText(e.target.value)} autoComplete="off" className="sm:max-w-xs" />
          <Button variant="destructive" disabled={text !== PURGE_PHRASE || busy} onClick={purge}>
            {busy ? <Spinner /> : <Trash2 className="size-4" />} Delete everything
          </Button>
        </div>
        <ErrorState error={error} title="Deletion failed" />
      </CardContent>
    </Card>
  );
}
