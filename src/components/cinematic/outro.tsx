"use client";

import { useRef } from "react";
import { cinematic } from "@/content/cinematic";
import { profile } from "@/content/profile";
import { gsap, useGSAP } from "@/lib/gsap";

export function Outro() {
  const sectionRef = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      gsap.matchMedia().add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from("[data-line]", {
          opacity: 0,
          y: 28,
          stagger: 0.1,
          duration: 0.8,
          ease: "power2.out",
          scrollTrigger: { trigger: sectionRef.current, start: "top 65%" },
        });
      });
    },
    { scope: sectionRef },
  );

  return (
    <footer
      ref={sectionRef}
      id="contact"
      className="flex min-h-svh flex-col justify-between bg-background px-6 py-24 sm:px-10 sm:py-28"
    >
      <p
        data-line
        className="font-mono text-[11px] tracking-[0.24em] uppercase text-muted"
      >
        {cinematic.outro.label}
      </p>

      <div>
        <h2
          data-line
          className="font-sans text-[clamp(2.5rem,8vw,8rem)] leading-[0.98] font-light tracking-[-0.04em] text-foreground"
        >
          {cinematic.outro.title}
        </h2>
        <a
          data-line
          href={`mailto:${profile.email}`}
          className="mt-10 inline-block py-2 font-mono text-base tracking-[0.06em] break-all text-lit underline decoration-hairline underline-offset-8 transition-colors duration-150 hover:decoration-lit sm:text-lg"
        >
          {profile.email}
        </a>
      </div>

      <ul
        data-line
        className="flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-hairline pt-8 font-mono text-[11px] tracking-[0.2em] uppercase text-muted"
      >
        <li>{profile.name}</li>
        <li>{profile.location}</li>
        {profile.links.map((link) => (
          <li key={link.href}>
            <a
              href={link.href}
              target={link.href.startsWith("http") ? "_blank" : undefined}
              rel={link.href.startsWith("http") ? "noreferrer noopener" : undefined}
              className="-my-2 inline-block py-3 transition-colors duration-150 hover:text-foreground"
            >
              {link.label}
            </a>
          </li>
        ))}
        <li className="sm:ml-auto">© {new Date().getFullYear()}</li>
      </ul>
    </footer>
  );
}
