"use client";

import { useEffect, useLayoutEffect, useRef, useState, type MouseEvent } from "react";
import { useLenis } from "@/components/site/smooth-scroll";

const links = [
  { href: "#home", label: "Home" },
  { href: "#about", label: "About" },
  { href: "#capabilities", label: "Capabilities" },
  { href: "#skills", label: "Skills" },
  { href: "#projects", label: "Projects" },
  { href: "#blogs", label: "Blogs" },
];

/** Smooth, non-bouncy settle shared by the nav's moving parts. */
const settle = "ease-[cubic-bezier(0.22,1,0.36,1)]";

/** Strong ease-out (quart): moves off at once, then settles gently, no overshoot. */
const easeOut = (t: number) => 1 - (1 - t) ** 4;

/** With reduced transparency, blurred surfaces turn solid. */
const solidIfAsked =
  "[@media(prefers-reduced-transparency:reduce)]:bg-gray-900 [@media(prefers-reduced-transparency:reduce)]:backdrop-blur-none";

/**
 * Floating header: logo on the left, the section links in a centred pill,
 * and a quiet text link beside one filled action on the right.
 *
 * The bar itself has no background; the floating pieces get one once the
 * page scrolls so the links stay readable over content. A highlight slides
 * between links to show the section in view. On small screens the links move
 * into a menu that grows out of its button and shrinks back into it.
 */
export function SiteNav({
  base = "",
  current = "#home",
}: {
  /** Prefix for section links, e.g. "/" on a blog post. */
  base?: string;
  /** Link highlighted before any section is observed. */
  current?: string;
}) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(current);

  // Sliding highlight: measured from the active link, so it moves from where
  // it is now to the new link instead of jumping.
  const linkRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pill, setPill] = useState<{ x: number; w: number } | null>(null);
  const [pillReady, setPillReady] = useState(false);

  const lenis = useLenis();
  // While a header click is scrolling the page, the highlight stays on the
  // destination instead of flicking through every section passed on the way.
  const steering = useRef(false);
  const steerTimer = useRef<number | undefined>(undefined);

  /**
   * Glide to a section instead of jumping. Distance sets the length (0.6 s
   * for a neighbour, up to 1.4 s end to end); a wheel or touch takes over
   * mid-flight. With reduced motion Lenis is off and the browser jumps.
   * Links to another page (a blog post's header) navigate normally.
   */
  const go = (e: MouseEvent<HTMLAnchorElement>, hash: string) => {
    if (base) return;
    const el = document.querySelector<HTMLElement>(hash);
    if (!el) return;
    e.preventDefault();
    setOpen(false);
    setActive(hash);
    history.replaceState(null, "", hash);

    const margin = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
    const top = hash === "#home" ? 0 : el.getBoundingClientRect().top + window.scrollY - margin;
    if (!lenis) {
      window.scrollTo({ top, behavior: "auto" });
      return;
    }
    const distance = Math.abs(top - window.scrollY);
    steering.current = true;
    lenis.scrollTo(top, {
      duration: Math.min(1.4, 0.6 + distance / 5000),
      easing: easeOut,
      onComplete: () => {
        steering.current = false;
      },
    });
    // Hand the highlight back even if the glide is interrupted.
    window.clearTimeout(steerTimer.current);
    steerTimer.current = window.setTimeout(() => {
      steering.current = false;
    }, 1600);
  };

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    // A section counts as current when it crosses the middle of the viewport.
    const io = new IntersectionObserver(
      (entries) => {
        if (steering.current) return;
        for (const e of entries) if (e.isIntersecting) setActive(`#${e.target.id}`);
      },
      { rootMargin: "-45% 0px -50% 0px" },
    );
    for (const l of links) {
      const el = document.querySelector(l.href);
      if (el) io.observe(el);
    }

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);

    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("keydown", onKey);
      io.disconnect();
    };
  }, []);

  useLayoutEffect(() => {
    const measure = () => {
      const el = linkRefs.current[active];
      if (el && el.offsetWidth) setPill({ x: el.offsetLeft, w: el.offsetWidth });
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [active]);

  // Turn the slide on only after the first placement, so the highlight
  // doesn't sweep in from the left edge on load.
  useEffect(() => {
    if (!pill || pillReady) return;
    const id = requestAnimationFrame(() => setPillReady(true));
    return () => cancelAnimationFrame(id);
  }, [pill, pillReady]);

  const glass = `rounded-full border backdrop-blur-md transition-colors duration-300 ${solidIfAsked} ${
    scrolled ? "border-white/10 bg-gray-900/80" : "border-transparent bg-transparent"
  }`;

  return (
    // The header is a transparent box as tall as the menu (the menu stays in
    // the layout so it can animate closed). It must not catch taps meant for
    // the page beneath, so only its actual controls take pointer events.
    <header className="pointer-events-none fixed inset-x-0 top-0 z-50 px-4 pt-4">
      <nav className="relative mx-auto flex h-14 max-w-7xl items-center justify-between">
        <a
          href={`${base}#home`}
          onClick={(e) => go(e, "#home")}
          className={`pointer-events-auto px-4 py-2 font-mono text-sm font-semibold text-white active:scale-95 ${glass}`}
        >
          <span className="text-emerald-400">&lt;</span>Pavan
          <span className="text-emerald-400">/&gt;</span>
        </a>

        {/* Centred link pill */}
        <ul
          className={`pointer-events-auto absolute left-1/2 hidden -translate-x-1/2 items-center gap-1 rounded-full border p-1 backdrop-blur-md transition-colors duration-300 lg:flex ${solidIfAsked} ${
            scrolled ? "border-white/10 bg-gray-900/80" : "border-white/10 bg-white/5"
          }`}
        >
          {pill && (
            <span
              aria-hidden="true"
              className={`pointer-events-none absolute inset-y-1 left-0 rounded-full bg-emerald-400/15 ${
                pillReady
                  ? `transition-[translate,width] duration-500 ${settle} motion-reduce:transition-none`
                  : ""
              }`}
              style={{ width: pill.w, translate: `${pill.x}px 0` }}
            />
          )}
          {links.map((l) => {
            const current = active === l.href;
            return (
              // No positioning on the <li>: links must measure from the <ul>.
              <li key={l.href}>
                <a
                  ref={(el) => {
                    linkRefs.current[l.href] = el;
                  }}
                  href={`${base}${l.href}`}
                  onClick={(e) => go(e, l.href)}
                  aria-current={current ? "location" : undefined}
                  className={`relative block rounded-full px-4 py-2 text-sm transition-[color,background-color,scale] duration-200 active:scale-95 ${
                    current ? "text-emerald-300" : "text-gray-300 hover:bg-white/5 hover:text-white"
                  }`}
                >
                  {l.label}
                </a>
              </li>
            );
          })}
        </ul>

        <div className={`pointer-events-auto flex items-center gap-1 p-1 ${glass}`}>
          <a
            href={`${base}#contact`}
            onClick={(e) => go(e, "#contact")}
            className="rounded-full bg-emerald-400 px-5 py-2 text-sm font-medium text-black transition-[translate,scale,background-color,box-shadow] duration-300 ease-out motion-safe:hover:-translate-y-0.5 hover:bg-emerald-300 hover:shadow-lg hover:shadow-emerald-500/30 active:translate-y-0 active:scale-95 motion-reduce:translate-none"
          >
            Contact me
          </a>
          <button
            type="button"
            className={`flex h-11 w-11 items-center justify-center rounded-full border border-white/10 bg-gray-900/80 text-gray-300 backdrop-blur-md transition-[scale,color] duration-150 active:scale-90 lg:hidden ${solidIfAsked}`}
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            aria-controls="site-menu"
            onClick={() => setOpen((v) => !v)}
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true">
              {open ? <path d="M6 6l12 12M18 6 6 18" /> : <path d="M4 7h16M4 12h16M4 17h16" />}
            </svg>
          </button>
        </div>
      </nav>

      {/* Mobile menu: grows from the menu button (top right) and shrinks back
          into it on close. Always mounted so closing can animate; `inert`
          keeps it out of the tab order while hidden. */}
      <ul
        id="site-menu"
        inert={!open}
        className={`mx-auto mt-2 max-w-7xl origin-top-right space-y-1 rounded-3xl border border-white/10 bg-gray-900/95 p-2 backdrop-blur-md transition-[opacity,scale,translate,visibility] duration-300 ${settle} motion-reduce:scale-100 motion-reduce:translate-none lg:hidden ${solidIfAsked} ${
          open
            ? "pointer-events-auto visible scale-100 opacity-100"
            : "invisible -translate-y-1 scale-95 opacity-0"
        }`}
      >
        {links.map((l) => (
          <li key={l.href}>
            <a
              href={`${base}${l.href}`}
              onClick={(e) => {
                setOpen(false);
                go(e, l.href);
              }}
              className={`block rounded-2xl px-4 py-3 transition-[background-color,scale] duration-150 active:scale-[0.98] ${
                active === l.href ? "bg-emerald-400/15 text-emerald-300" : "text-gray-200 hover:bg-white/5"
              }`}
            >
              {l.label}
            </a>
          </li>
        ))}
      </ul>
    </header>
  );
}
