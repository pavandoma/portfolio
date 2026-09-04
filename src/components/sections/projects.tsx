import { Meter } from "@/components/meter";
import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { Tilt, TiltLayer } from "@/components/tilt";
import { projects } from "@/content/profile";

export function Projects() {
  return (
    <section
      id="work"
      className="mx-auto w-full max-w-6xl px-6 py-20 sm:px-10 sm:py-24"
    >
      <SectionHeading
        title="Selected work"
        meta={`${String(projects.length).padStart(2, "0")} case studies`}
      />

      <ul className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-3">
        {projects.map((project, index) => (
          <Reveal as="li" key={project.slug} delay={index * 0.06}>
            <Tilt className="group flex h-full flex-col rounded-lg border border-border bg-card p-6 transition-[border-color,box-shadow] duration-200 hover:border-rule hover:shadow-[0_18px_40px_-24px_rgba(0,0,0,0.35)]">
              <div className="flex items-start justify-between gap-4">
                <span className="eyebrow tabular-nums text-muted-foreground">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <svg
                  viewBox="0 0 16 16"
                  aria-hidden="true"
                  className="size-3.5 text-muted-foreground transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M4 12 12 4M6 4h6v6" />
                </svg>
              </div>

              {/* Title and summary ride closest to the viewer so the card reads
                  as stacked planes rather than one rotating rectangle. */}
              <TiltLayer z={28}>
                <h3 className="mt-5 font-serif text-2xl leading-snug tracking-[-0.01em] text-balance">
                  {project.title}
                </h3>
                <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                  {project.summary}
                </p>
              </TiltLayer>

              <TiltLayer z={14}>
                <ul className="mt-5 space-y-2.5">
                  {project.highlights.map((highlight) => (
                    <li
                      key={highlight}
                      className="flex gap-2.5 text-sm leading-relaxed text-muted-foreground"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-2 size-1 shrink-0 rounded-full bg-rule"
                      />
                      <span>{highlight}</span>
                    </li>
                  ))}
                </ul>
              </TiltLayer>

              <div className="mt-auto pt-8">
                <Meter meter={project.meter} delay={index * 0.06} />

                <ul className="mt-5 flex flex-wrap gap-x-3 gap-y-1.5 border-t border-border pt-4">
                  {project.tech.map((tech) => (
                    <li
                      key={tech}
                      className="eyebrow whitespace-nowrap text-muted-foreground"
                    >
                      {tech}
                    </li>
                  ))}
                </ul>
              </div>
            </Tilt>
          </Reveal>
        ))}
      </ul>
    </section>
  );
}
