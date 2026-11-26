import type { ReactNode } from "react";
import { Nunito, Poppins } from "next/font/google";
import { SiteNav } from "./nav";

// Poppins for headings, Nunito for everything else.
const poppins = Poppins({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-poppins",
});
const nunito = Nunito({ subsets: ["latin"], variable: "--font-nunito" });

/** Deterministic star field, so server and client render the same dots. */
const stars = (() => {
  let seed = 7;
  const rand = () => ((seed = (seed * 16807) % 2147483647) - 1) / 2147483646;
  return Array.from({ length: 110 }, () => ({
    x: rand() * 100,
    y: rand() * 100,
    s: rand() < 0.15 ? 2 : 1,
    o: 0.15 + rand() * 0.5,
  }));
})();

export const githubIcon = (className = "h-4 w-4") => (
  <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
    <path d="M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.68-1.28-1.68-1.05-.72.08-.7.08-.7 1.16.08 1.77 1.19 1.77 1.19 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.69 5.39-5.26 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5Z" />
  </svg>
);

/**
 * Everything the site's pages share: the fonts, the star field pinned
 * behind the page, and the header.
 *
 * `base` prefixes the header's section links, so on a blog post they point
 * back to the home page's sections; `current` is the link highlighted first.
 */
export function SiteShell({
  children,
  base = "",
  current,
}: {
  children: ReactNode;
  base?: string;
  current?: string;
}) {
  return (
    <div
      className={`${poppins.variable} ${nunito.variable} relative min-h-svh bg-black [&_:focus-visible]:outline-2! [&_:focus-visible]:outline-offset-2! [--ring:var(--color-emerald-400)] font-[family-name:var(--font-nunito)] text-gray-200 [color-scheme:dark] [&_h1]:font-[family-name:var(--font-poppins)] [&_h2]:font-[family-name:var(--font-poppins)] [&_h3]:font-[family-name:var(--font-poppins)]`}
    >
      {/* Star field pinned to the viewport: it stays put while the page
          scrolls over it. */}
      <div className="pointer-events-none fixed inset-0" aria-hidden="true">
        {stars.map((st, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-white"
            style={{
              left: `${st.x}%`,
              top: `${st.y}%`,
              width: st.s,
              height: st.s,
              opacity: st.o,
            }}
          />
        ))}
      </div>

      <SiteNav base={base} current={current} />
      {children}
    </div>
  );
}
