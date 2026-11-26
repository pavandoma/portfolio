import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SmoothScroll } from "@/components/site/smooth-scroll";
import { profile } from "@/content/profile";
import { SITE_URL } from "@/lib/site";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const TITLE = `${profile.name} — ${profile.title}`;
const SITE_NAME = "voiyu";

/**
 * Structured data: the site's name (Google shows it above the result) and
 * the person it belongs to. Built only from the public profile.
 */
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      name: SITE_NAME,
      alternateName: profile.name,
      url: `${SITE_URL}/`,
    },
    {
      "@type": "Person",
      "@id": `${SITE_URL}/#person`,
      name: profile.name,
      jobTitle: profile.title,
      url: `${SITE_URL}/`,
      sameAs: profile.links.filter((l) => l.href.startsWith("http")).map((l) => l.href),
    },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: TITLE, template: `%s — ${profile.name}` },
  description: profile.tagline,
  alternates: { canonical: "/" },
  keywords: [
    "AI engineer",
    "machine learning engineer",
    "retrieval-augmented generation",
    "RAG systems",
    "LLM evaluation",
    "MLOps",
    "data engineer",
    "Buffalo NY",
    profile.name,
  ],
  openGraph: {
    type: "website",
    url: "/",
    siteName: SITE_NAME,
    title: TITLE,
    description: profile.tagline,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: profile.tagline,
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        {/* Scroll reveals start hidden and are shown by JS; without JS, show
            everything in place. */}
        <noscript>
          <style>{`[data-reveal] { opacity: 1 !important; translate: none !important; }`}</style>
        </noscript>
      </head>
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        <SmoothScroll>{children}</SmoothScroll>
      </body>
    </html>
  );
}
