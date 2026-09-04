import type { Metadata } from "next";
import { Inter, Newsreader } from "next/font/google";
import { profile } from "@/content/profile";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const newsreader = Newsreader({
  variable: "--font-newsreader",
  subsets: ["latin"],
  // Optical size trimmed for display use; italics unused.
  style: ["normal"],
});

export const metadata: Metadata = {
  title: `${profile.name} — ${profile.title}`,
  description: profile.tagline,
  openGraph: {
    title: `${profile.name} — ${profile.title}`,
    description: profile.tagline,
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${newsreader.variable} h-full scroll-smooth antialiased`}
    >
      <head>
        {/* Scroll reveals start at opacity 0 and are animated in by Motion.
            Without JS they would never appear, so force the final state. */}
        <noscript>
          <style>{`.js-reveal { opacity: 1 !important; transform: none !important; clip-path: none !important; }`}</style>
        </noscript>
      </head>
      <body className="flex min-h-full flex-col font-sans">{children}</body>
    </html>
  );
}
