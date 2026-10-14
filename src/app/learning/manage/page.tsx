import type { Metadata } from "next";
import { Nav } from "@/components/cinematic/nav";
import { LearningLog } from "@/components/learning/learning-log";

// Unlisted editing page: nothing links here, and changes need the passphrase.
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
