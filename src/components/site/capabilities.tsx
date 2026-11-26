import type { ReactNode } from "react";
import { Reveal } from "./reveal";
import { SectionHead } from "./section-head";

type Capability = { title: string; body: string; icon: ReactNode };

const svg = (children: ReactNode) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.75}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="h-6 w-6"
    aria-hidden="true"
  >
    {children}
  </svg>
);

const capabilities: Capability[] = [
  {
    title: "RAG Systems",
    body: "LLM apps grounded in your own data.",
    icon: svg(
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
        <path d="M8 11h6M11 8v6" />
      </>,
    ),
  },
  {
    title: "LLM Evaluation",
    body: "Proof a model is ready before it ships.",
    icon: svg(
      <>
        <path d="M3 3v18h18" />
        <path d="m7 14 4-4 3 3 5-6" />
      </>,
    ),
  },
  {
    title: "Data Pipelines",
    body: "Clean schemas and ETL people can trust.",
    icon: svg(
      <>
        <ellipse cx="12" cy="5" rx="8" ry="3" />
        <path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
        <path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6" />
      </>,
    ),
  },
  {
    title: "MLOps & Cloud",
    body: "Containerized models on AWS, monitored.",
    icon: svg(
      <>
        <path d="M21 8 12 3 3 8l9 5 9-5Z" />
        <path d="m3 8v8l9 5 9-5V8" />
        <path d="M12 13v8" />
      </>,
    ),
  },
];

/**
 * Staggered four-up capability grid, styled like the rest of the page.
 *
 * Even cards sit lower on wide screens. Hovering the grid dims every card
 * except the one under the pointer, whose corner brackets grow out to frame
 * it and whose icon disc fills green.
 */
export function Capabilities() {
  return (
    <section id="capabilities" className="px-6 py-24 md:py-32">
      <div className="mx-auto max-w-7xl">
        <SectionHead title="Capabilities" sub="What I bring to an AI team" />

        <div className="group/list grid gap-x-8 gap-y-16 sm:grid-cols-2 lg:grid-cols-4">
          {capabilities.map((cap, i) => (
            <Reveal
              key={cap.title}
              delay={i * 120}
              className={i % 2 === 1 ? "lg:mt-24" : ""}
            >
              <article className="group/card relative transition-opacity duration-500 ease-out group-hover/list:opacity-30 hover:!opacity-100">
                {/* Corner brackets: small marks that grow to frame the card. */}
                <span className="pointer-events-none absolute -left-4 -top-4 h-3 w-3 border-l border-t border-emerald-400/40 transition-[width,height,border-color] duration-500 motion-reduce:transition-none group-hover/card:h-[calc(100%+2rem)] group-hover/card:w-[calc(100%+2rem)] group-hover/card:border-emerald-400/30" />
                <span className="pointer-events-none absolute -bottom-4 -right-4 h-3 w-3 border-b border-r border-emerald-400/40 transition-[width,height,border-color] duration-500 motion-reduce:transition-none group-hover/card:h-[calc(100%+2rem)] group-hover/card:w-[calc(100%+2rem)] group-hover/card:border-emerald-400/30" />

                <div className="rounded-2xl border border-white/5 bg-gray-900/70 p-7 transition-colors duration-500 group-hover/card:border-emerald-400/30">
                  <div className="mb-6 flex h-12 w-12 items-center justify-center rounded-full bg-emerald-400/10 text-emerald-400 transition-colors duration-500 group-hover/card:bg-emerald-400 group-hover/card:text-black">
                    {cap.icon}
                  </div>
                  <h3 className="mb-2 text-xl text-white">{cap.title}</h3>
                  <p className="text-sm leading-relaxed text-gray-400">{cap.body}</p>
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
