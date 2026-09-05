"use client";

import { useRef } from "react";
import { useLenis } from "@/components/cinematic/smooth-scroll";
import { ThemeToggle } from "@/components/cinematic/theme-toggle";
import { profile } from "@/content/profile";
import { gsap, useGSAP } from "@/lib/gsap";

const LINKS = [
  { id: "story", label: "Origin" },
  { id: "details", label: "Details" },
  { id: "specs", label: "Spec" },
  { id: "contact", label: "Contact" },
] as const;

/** Within this many px of the top the header is always shown. */
const TOP_ZONE = 80;
/** Scroll travel in one direction before the header reacts. Absorbs jitter. */
const TRAVEL = 24;

export function Nav() {
  const lenis = useLenis();
  const headerRef = useRef<HTMLElement>(null);

  /**
   * Fade out on the way down, back on the way up, always present near the
   * top. Direction is measured from an anchor that resets on every reversal,
   * so a slow wheel or Lenis's per-frame lerp can't flicker it.
   *
   * Listens to the native `window` scroll event unconditionally, not to
   * Lenis. Lenis (in the whole-page mode used here, no wrapped scroll
   * container) animates the real `window.scrollY`, so plain scroll events
   * already fire for it — a separate Lenis-specific listener would just be a
   * second source of the same updates. That used to exist here, gated behind
   * a `lenis` dependency so it could fall back to native scroll before Lenis
   * mounted; logging confirmed the fallback listener could still be attached
   * after the Lenis-backed one took over, so both tracked hidden/direction
   * state independently and issued competing GSAP tweens on the same header
   * element. Removing the branch removes the possibility outright.
   *
   * Keyboard users: a hidden header is `visibility: hidden`, so it leaves the
   * tab order rather than catching invisible focus; PageUp or the arrow keys
   * scroll up and bring it back like any other scroll.
   */
  useGSAP(
    () => {
      const header = headerRef.current;
      if (!header) return;

      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      let hidden = false;
      let lastY = window.scrollY;
      let lastDirection = 0;
      let anchorY = window.scrollY;

      const setHidden = (next: boolean) => {
        if (next === hidden) return;
        hidden = next;
        // autoAlpha also toggles visibility, so a hidden header drops out of
        // the tab order instead of catching invisible focus.
        gsap.to(header, {
          autoAlpha: next ? 0 : 1,
          y: next ? -12 : 0,
          duration: reduce ? 0 : 0.35,
          ease: "power2.out",
          overwrite: true,
        });
      };

      const onScroll = () => {
        const y = window.scrollY;
        const direction = Math.sign(y - lastY);
        if (direction !== 0 && direction !== lastDirection) {
          // Anchor at the previous position, not this one, so the travel of
          // the very first event in a new direction counts. Otherwise a
          // single large jump (a nav click, a keyboard page-down) never
          // registers.
          anchorY = lastY;
          lastDirection = direction;
        }
        const travelled = Math.abs(y - anchorY);

        if (y < TOP_ZONE) setHidden(false);
        else if (direction > 0 && travelled > TRAVEL) setHidden(true);
        else if (direction < 0 && travelled > TRAVEL) setHidden(false);

        lastY = y;
      };

      window.addEventListener("scroll", onScroll, { passive: true });
      return () => window.removeEventListener("scroll", onScroll);
    },
    { scope: headerRef },
  );

  const go = (id: string) => (event: React.MouseEvent<HTMLAnchorElement>) => {
    // Let native anchor behaviour handle it under reduced motion (no Lenis).
    if (!lenis) return;
    event.preventDefault();
    lenis.scrollTo(`#${id}`, { offset: 0, duration: 1.4 });
  };

  return (
    <header
      ref={headerRef}
      data-site-header
      className="pointer-events-none fixed inset-x-0 top-0 z-50"
    >
      {/* Legibility scrim. The header itself has no fill, so without this a
          headline scrolled to the very top shows straight through the nav
          text the instant the header reappears. It fades with the header
          (opacity cascades to children), so it never lingers once hidden. */}
      <div
        aria-hidden="true"
        className="absolute inset-x-0 top-0 z-0 h-24 bg-gradient-to-b from-background via-background/80 to-transparent backdrop-blur-md transition-colors duration-300 sm:h-28"
      />

      <nav
        aria-label="Primary"
        className="relative z-10 flex h-16 items-center justify-between gap-6 px-6 sm:px-10"
      >
        <a
          href="#top"
          onClick={go("top")}
          className="pointer-events-auto py-3 font-mono text-[11px] tracking-[0.18em] whitespace-nowrap uppercase text-foreground"
        >
          {profile.name}
        </a>

        <div className="flex items-center gap-6 sm:gap-8">
          {/* Below `sm` there is no room for four links beside the name; the
              one that matters on a phone is Contact. */}
          <a
            href="#contact"
            onClick={go("contact")}
            className="pointer-events-auto py-3 font-mono text-[11px] tracking-[0.18em] uppercase text-muted transition-colors duration-150 hover:text-foreground sm:hidden"
          >
            Contact
          </a>

          <ul className="pointer-events-auto hidden items-center gap-6 sm:flex sm:gap-8">
            {LINKS.map((link) => (
              <li key={link.id}>
                <a
                  href={`#${link.id}`}
                  onClick={go(link.id)}
                  className="inline-block py-3 font-mono text-[11px] tracking-[0.18em] uppercase text-muted transition-colors duration-150 hover:text-foreground"
                >
                  {link.label}
                </a>
              </li>
            ))}
          </ul>

          <ThemeToggle />
        </div>
      </nav>
    </header>
  );
}
