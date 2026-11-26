import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { SmoothScroll } from "@/components/cinematic/smooth-scroll";
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
    siteName: profile.name,
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
        <SmoothScroll>{children}</SmoothScroll>
      </body>
    </html>
  );
}
