"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Link2, Search } from "lucide-react";

import { ErrorState, PageHeader, Spinner } from "@/components/common";
import { FileDrop } from "@/components/file-drop";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { api, ApiError } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function NewJob() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function done(job: Job) {
    router.push(`/jobs/${job.id}${job.duplicate ? "?duplicate=1" : ""}`);
  }

  async function submit(mode: "text" | "url") {
    setBusy(true);
    setError(null);
    try {
      const body = mode === "text" ? { text, title: title || undefined, company: company || undefined, url: url || undefined } : { url, title: title || undefined, company: company || undefined };
      await done(await api.post<Job>("/jobs", body));
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function upload(file: File) {
    setBusy(true);
    setError(null);
    try {
      await done(await api.upload<Job>("/jobs/upload", file, { title, company, url }));
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="New job analysis" description="Paste a posting, give its URL, or upload it. The text is treated as untrusted input: instructions hidden in it are reported and ignored." />
      <Card>
        <CardContent className="pt-1">
          <Tabs defaultValue="text">
            <TabsList>
              <TabsTrigger value="text">Paste text</TabsTrigger>
              <TabsTrigger value="url">From URL</TabsTrigger>
              <TabsTrigger value="file">Upload file</TabsTrigger>
            </TabsList>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="title">Exact job title (optional)</Label>
                <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Detected automatically" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="company">Company (optional)</Label>
                <Input id="company" value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Detected automatically" />
              </div>
            </div>
            <TabsContent value="text" className="space-y-3">
              <Textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste the full job description…" className="min-h-72 font-mono text-xs" />
              <div className="space-y-1.5">
                <Label htmlFor="url-opt">Posting URL (optional, used to detect duplicates)</Label>
                <Input id="url-opt" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
              </div>
              <Button onClick={() => submit("text")} disabled={busy || text.trim().length < 80}>
                {busy ? <Spinner /> : <Search />} Analyse posting
              </Button>
            </TabsContent>
            <TabsContent value="url" className="space-y-3">
              <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://company.com/careers/job/123" />
              <Alert variant="info">
                <AlertDescription>
                  The page is fetched by your local backend (public addresses only). If the site needs JavaScript and a Firecrawl key is configured, Firecrawl renders it; only the URL is sent to Firecrawl.
                </AlertDescription>
              </Alert>
              <Button onClick={() => submit("url")} disabled={busy || !url.startsWith("http")}>
                {busy ? <Spinner /> : <Link2 />} Fetch and analyse
              </Button>
            </TabsContent>
            <TabsContent value="file">
              <FileDrop accept=".pdf,.docx,.txt,.md" onFile={upload} disabled={busy} label={busy ? "Analysing…" : "Upload the job description"} />
            </TabsContent>
          </Tabs>
          <div className="mt-4">
            <ErrorState error={error} title="Could not analyse the posting" />
          </div>
        </CardContent>
      </Card>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-base">What happens next</CardTitle>
          <CardDescription>
            Requirements are split into mandatory, preferred, responsibilities and context, keeping the posting&apos;s wording. Each one is matched against evidence in your profile, and eligibility gates (years, degree, work authorization) are reported separately from the score.
          </CardDescription>
        </CardHeader>
      </Card>
    </>
  );
}
