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
      // The theme script below changes `data-theme` before React hydrates;
      // this tells React to accept the DOM rather than flag a mismatch.
      suppressHydrationWarning
    >
      <head>
        {/* Runs synchronously while the HTML parses, before first paint, so a
            saved light preference never flashes dark. Dark needs no attribute. */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch(e){}})();`,
          }}
        />
        {/* The preloader is server-rendered so content never flashes before
            the sequence. Without JS nothing would ever lift it. */}
        <noscript>
          <style>{`[data-preloader] { display: none !important; }`}</style>
        </noscript>
      </head>
      <body className="flex min-h-full flex-col bg-background font-sans text-foreground">
        <SmoothScroll>{children}</SmoothScroll>
      </body>
    </html>
  );
}
