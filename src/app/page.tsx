import { Details } from "@/components/cinematic/details";
import { Hero } from "@/components/cinematic/hero";
import { Nav } from "@/components/cinematic/nav";
import { Outro } from "@/components/cinematic/outro";
import { Preloader } from "@/components/cinematic/preloader";
import { Specs } from "@/components/cinematic/specs";
import { Story } from "@/components/cinematic/story";
import { Timeline } from "@/components/cinematic/timeline";
import { education, profile, skills } from "@/content/profile";
import { SITE_URL } from "@/lib/site";

/**
 * Structured data for search engines. A Person entity is what a portfolio
 * should declare; it feeds knowledge panels and lets Google tie the site to
 * the LinkedIn profile via `sameAs`.
 */
const personJsonLd = {
  "@context": "https://schema.org",
  "@type": "Person",
  name: profile.name,
  jobTitle: profile.title,
  description: profile.tagline,
  url: `${SITE_URL}/`,
  email: `mailto:${profile.email}`,
  address: {
    "@type": "PostalAddress",
    addressLocality: "Buffalo",
    addressRegion: "NY",
    addressCountry: "US",
  },
  sameAs: profile.links
    .filter((link) => link.href.startsWith("http"))
    .map((link) => link.href),
  alumniOf: education.map((entry) => ({
    "@type": "CollegeOrUniversity",
    name: entry.institution,
  })),
  knowsAbout: skills.flatMap((group) => group.items),
};

export default function Home() {
  return (
    <>
      <script
        type="application/ld+json"
        // `<` is escaped so no string in the payload can close the tag.
        dangerouslySetInnerHTML={{
          __html: JSON.stringify(personJsonLd).replace(/</g, "\\u003c"),
        }}
      />
      <Preloader />
      <Nav />
      <main>
        <Hero />
        <Story />
        <Details />
        <Specs />
        <Timeline />
      </main>
      <Outro />
    </>
  );
}
