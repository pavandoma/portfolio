"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Download, Sparkles } from "lucide-react";

import { ErrorState, Loading, PageHeader, Spinner, StatusBadge } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import type { Preset, ResumeVersion } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, score } from "@/lib/utils";

export default function Resumes() {
  const router = useRouter();
  const versions = useApi<ResumeVersion[]>("/resumes");
  const presets = useApi<Preset[]>("/variants");
  const [variant, setVariant] = useState("ai-engineer");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function generateVariant() {
    setBusy(true);
    setError(null);
    try {
      const version = await api.post<{ id: string }>("/resumes", { variant });
      router.push(`/resumes/${version.id}`);
    } catch (e) {
      setError(e as ApiError);
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Resumes & exports" description="Every generated version, with its PDF, DOCX, JSON and evaluation reports. Versions are never overwritten." />
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Reusable variant resumes</CardTitle>
          <CardDescription>A general resume aimed at a target category when you do not have a specific posting. Categories are targets, not proof of qualification.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <select value={variant} onChange={(e) => setVariant(e.target.value)} className="border-input bg-card h-9 rounded-md border px-3 text-sm">
            {presets.data?.map((p) => (
              <option key={p.key} value={p.key}>
                {p.title}
              </option>
            ))}
          </select>
          <Button onClick={generateVariant} disabled={busy}>
            {busy ? <Spinner /> : <Sparkles />} Generate variant
          </Button>
        </CardContent>
        <CardContent>
          <ErrorState error={error} />
        </CardContent>
      </Card>
      {versions.loading && <Loading />}
      <ErrorState error={versions.error} />
      <div className="space-y-3">
        {versions.data?.length === 0 && <p className="text-muted-foreground text-sm">No resumes yet.</p>}
        {versions.data?.map((v) => (
          <Card key={v.id} className="gap-3 py-4">
            <CardContent className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <div className="min-w-0">
                <Link href={`/resumes/${v.id}`} className="font-medium hover:underline">
                  {v.target_title} · v{v.version_no}
                </Link>
                <div className="text-muted-foreground text-xs">
                  {v.variant ? `Variant: ${v.variant}` : "Job-specific"} · {formatDate(v.created_at)}
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  <StatusBadge status={v.status} />
                  <Badge variant="outline">alignment {score(v.summary_scores.resume_alignment)}</Badge>
                  <Badge variant="outline">ATS parse {score(v.summary_scores.ats_parsing)}</Badge>
                  <Badge variant="outline">integrity {score(v.summary_scores.evidence_integrity)}%</Badge>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {v.files
                  .filter((f) => ["pdf", "docx", "json", "evaluation_report"].includes(f.kind))
                  .map((f) => (
                    <Button key={f.id} variant="outline" size="sm" asChild>
                      <a href={f.url}>
                        <Download /> {f.kind === "evaluation_report" ? "Report" : f.kind.toUpperCase()}
                      </a>
                    </Button>
                  ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  );
}
