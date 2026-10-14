import type { Metadata } from "next";
import { Nav } from "@/components/cinematic/nav";
import { LearningLog } from "@/components/learning/learning-log";

// Reached only through the host's login (see public/learning/manage/.htaccess).
// Kept out of search results and the sitemap; the public page is /learning/.
export const metadata: Metadata = {
  title: "Learning log — manage",
  robots: { index: false, follow: false },
};

export default function ManageLearningPage() {
  return (
    <>
      <Nav />
      <main>
        <LearningLog editable />
      </main>
    </>
  );
}
