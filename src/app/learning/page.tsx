import type { Metadata } from "next";
import { Nav } from "@/components/cinematic/nav";
import { LearningLog } from "@/components/learning/learning-log";
import { learning } from "@/content/learning";
import { profile } from "@/content/profile";

export const metadata: Metadata = {
  title: "Learning log",
  description: `${learning.intro} By ${profile.name}.`,
  alternates: { canonical: "/learning/" },
  openGraph: { url: "/learning/", title: `Learning log — ${profile.name}` },
};

export default function LearningPage() {
  return (
    <>
      <Nav />
      <main>
        <LearningLog />
      </main>
    </>
  );
}
