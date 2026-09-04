import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { experience, stats } from "@/content/profile";

export function Experience() {
  return (
    <section
      id="experience"
      className="mx-auto w-full max-w-6xl px-6 py-20 sm:px-10 sm:py-24"
    >
      <SectionHeading title="Experience" meta="In practice" />

      <ul className="mt-10 space-y-14">
        {experience.map((role, index) => (
          <Reveal as="li" key={role.company} delay={index * 0.06}>
            <div className="grid grid-cols-1 gap-6 md:grid-cols-[13rem_1fr] md:gap-10">
              <div>
                <p className="eyebrow text-muted-foreground">{role.period}</p>
                <p className="eyebrow mt-1.5 text-muted-foreground">
                  {role.location}
                </p>
              </div>

              <div>
                <h3 className="font-serif text-2xl leading-snug tracking-[-0.01em] text-balance">
                  {role.role}
                </h3>
                <p className="mt-1.5 text-accent">{role.company}</p>

                <ul className="mt-6 space-y-3.5">
                  {role.bullets.map((bullet) => (
                    <li
                      key={bullet}
                      className="flex gap-3 leading-relaxed text-muted-foreground"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-2.5 size-1 shrink-0 rounded-full bg-rule"
                      />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </Reveal>
        ))}
      </ul>

      <dl className="mt-16 grid grid-cols-1 border-t border-rule sm:grid-cols-3">
        {stats.map((stat, index) => (
          <Reveal
            key={stat.label}
            delay={index * 0.06}
            className="border-b border-border py-7 sm:border-b-0 sm:pr-8"
          >
            <dd className="font-serif text-4xl leading-none tabular-nums">
              {stat.value}
            </dd>
            <dt className="eyebrow mt-3 text-muted-foreground">{stat.label}</dt>
          </Reveal>
        ))}
      </dl>
    </section>
  );
}
