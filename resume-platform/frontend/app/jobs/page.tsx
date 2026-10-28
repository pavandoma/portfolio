"use client";

import Link from "next/link";
import { FilePlus2 } from "lucide-react";

import { ErrorState, Loading, PageHeader, StatusBadge } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { ApplicationRow } from "@/lib/types";
import { useApi } from "@/lib/use-api";
import { formatDate, score } from "@/lib/utils";

export default function Jobs() {
  const { data, error, loading } = useApi<ApplicationRow[]>("/applications");
  return (
    <>
      <PageHeader
        title="Jobs & matches"
        description="Every analysed posting with its job-fit score and the resumes generated for it."
        actions={
          <Button asChild>
            <Link href="/jobs/new">
              <FilePlus2 /> New analysis
            </Link>
          </Button>
        }
      />
      {loading && <Loading />}
      <ErrorState error={error} />
      {data && (
        <Card className="py-2">
          <CardContent className="px-2">
            {data.length === 0 ? (
              <p className="text-muted-foreground p-4 text-sm">No jobs analysed yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Role</TableHead>
                    <TableHead>Company</TableHead>
                    <TableHead className="text-right">Job fit</TableHead>
                    <TableHead className="text-right">Best alignment</TableHead>
                    <TableHead>Resumes</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Analysed</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.map((a) => (
                    <TableRow key={a.job_id}>
                      <TableCell className="font-medium">
                        <Link className="hover:underline" href={`/jobs/${a.job_id}`}>
                          {a.title || "Untitled role"}
                        </Link>
                      </TableCell>
                      <TableCell>{a.company ?? "—"}</TableCell>
                      <TableCell className="text-right tabular-nums">{score(a.job_fit)}</TableCell>
                      <TableCell className="text-right tabular-nums">{score(a.latest_alignment)}</TableCell>
                      <TableCell>{a.resume_versions}</TableCell>
                      <TableCell>
                        <StatusBadge status={a.application_status} />
                      </TableCell>
                      <TableCell className="text-muted-foreground">{formatDate(a.analyzed_at)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </>
  );
}
