"use client";

import Link from "next/link";
import { useState } from "react";

import { ErrorState, Loading, PageHeader, StatusBadge } from "@/components/common";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api, ApiError } from "@/lib/api";
import type { ApplicationRow, ResumeVersion } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, score } from "@/lib/utils";

const STATUSES = ["not_applied", "applied", "screening", "interviewing", "offer", "rejected", "withdrawn", "archived"];

export default function Applications() {
  const rows = useApi<ApplicationRow[]>("/applications");
  const versions = useApi<ResumeVersion[]>("/resumes");
  const [error, setError] = useState<ApiError | null>(null);

  async function update(jobId: string, body: Record<string, unknown>) {
    setError(null);
    try {
      await api.put(`/applications/${jobId}`, body);
      rows.reload();
    } catch (e) {
      setError(e as ApiError);
    }
  }

  return (
    <>
      <PageHeader title="Application tracker" description="Record where you applied and which exact resume version you sent. This tool never submits applications for you." />
      <ErrorState error={error} />
      {rows.loading && <Loading />}
      <ErrorState error={rows.error} />
      {rows.data && rows.data.length === 0 && (
        <Alert variant="info">
          <AlertDescription>Analyse a job first; it will appear here.</AlertDescription>
        </Alert>
      )}
      {rows.data && rows.data.length > 0 && (
        <Card className="py-2">
          <CardContent className="px-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Role</TableHead>
                  <TableHead className="text-right">Fit</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Resume sent</TableHead>
                  <TableHead>Applied</TableHead>
                  <TableHead className="min-w-48">Notes</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.data.map((a) => {
                  const options = (versions.data ?? []).filter((v) => v.job_id === a.job_id);
                  return (
                    <TableRow key={a.job_id}>
                      <TableCell>
                        <Link href={`/jobs/${a.job_id}`} className="font-medium hover:underline">
                          {a.title || "Untitled role"}
                        </Link>
                        <div className="text-muted-foreground text-xs">{a.company ?? ""}</div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">{score(a.job_fit)}</TableCell>
                      <TableCell>
                        <select
                          aria-label="Application status"
                          value={a.application_status}
                          onChange={(e) => update(a.job_id, { status: e.target.value })}
                          className="border-input bg-card h-8 rounded-md border px-2 text-xs"
                        >
                          {STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s.replaceAll("_", " ")}
                            </option>
                          ))}
                        </select>
                      </TableCell>
                      <TableCell>
                        <select
                          aria-label="Resume version sent"
                          value={a.submitted_version_id ?? ""}
                          onChange={(e) => e.target.value && update(a.job_id, { resume_version_id: e.target.value })}
                          className="border-input bg-card h-8 max-w-44 rounded-md border px-2 text-xs"
                        >
                          <option value="">—</option>
                          {options.map((v) => (
                            <option key={v.id} value={v.id}>
                              v{v.version_no} ({v.status})
                            </option>
                          ))}
                        </select>
                        {a.submitted_version_id && (
                          <Link href={`/resumes/${a.submitted_version_id}`} className="text-primary ml-2 text-xs hover:underline">
                            open
                          </Link>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-xs">
                        {a.applied_at ? formatDate(a.applied_at) : <StatusBadge status="not_applied" />}
                      </TableCell>
                      <TableCell>
                        <Input defaultValue={a.notes} className="h-8 text-xs" placeholder="Add a note" onBlur={(e) => e.target.value !== a.notes && update(a.job_id, { notes: e.target.value })} />
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </>
  );
}
