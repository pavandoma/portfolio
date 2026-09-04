import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { certifications, education, profile } from "@/content/profile";

export function About() {
  return (
    <section
      id="about"
      className="mx-auto w-full max-w-6xl px-6 py-20 sm:px-10 sm:py-24"
    >
      <SectionHeading title="About" meta={profile.location} />

      <div className="mt-10 grid grid-cols-1 gap-12 lg:grid-cols-[1.35fr_1fr] lg:gap-20">
        <Reveal>
          <div className="space-y-6">
            {profile.about.map((paragraph, index) => (
              <p
                key={paragraph}
                className={
                  index === 0
                    ? "font-serif text-2xl leading-[1.45] text-pretty sm:text-[1.75rem]"
                    : "leading-relaxed text-pretty text-muted-foreground"
                }
              >
                {paragraph}
              </p>
            ))}
          </div>
        </Reveal>

        <Reveal delay={0.06}>
          <div className="space-y-10">
            <div>
              <h3 className="eyebrow text-muted-foreground">Education</h3>
              <ul className="mt-5 space-y-6">
                {education.map((entry) => (
                  <li key={entry.institution}>
                    <p className="font-serif text-lg leading-snug text-balance">
                      {entry.degree}
                    </p>
                    <p className="mt-1.5 text-sm text-muted-foreground">
                      {entry.institution}
                    </p>
                    <p className="eyebrow mt-1.5 text-muted-foreground">
                      {entry.location} · {entry.period}
                    </p>
                  </li>
                ))}
              </ul>
            </div>

            <div className="border-t border-border pt-10">
              <h3 className="eyebrow text-muted-foreground">Certifications</h3>
              <ul className="mt-5 space-y-6">
                {certifications.map((cert) => (
                  <li key={cert.title}>
                    <p className="font-serif text-lg leading-snug text-balance">
                      {cert.title}
                    </p>
                    <p className="mt-1.5 text-sm text-muted-foreground">
                      {cert.detail}
                    </p>
                    <p className="eyebrow mt-1.5 text-muted-foreground">
                      {cert.date}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
