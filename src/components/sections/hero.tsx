import { MaskedLines, Reveal } from "@/components/reveal";
import { SystemMap } from "@/components/system-map";
import { profile } from "@/content/profile";

/** Manual line breaks — the serif display is set tight and balanced by hand. */
const HEADLINE_LINES = ["Building", "intelligence", "that earns trust."];

export function Hero() {
  return (
    <section className="mx-auto w-full max-w-6xl px-6 pt-16 pb-20 sm:px-10 sm:pt-20 sm:pb-24">
      <Reveal onMount>
        <p className="eyebrow text-muted-foreground">{profile.availability}</p>
      </Reveal>

      <div className="mt-8 grid grid-cols-1 items-start gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-16">
        <div>
          <h1 className="font-serif text-[2.75rem] leading-[1.06] tracking-[-0.02em] sm:text-6xl">
            <MaskedLines lines={HEADLINE_LINES} onMount />
          </h1>

          <Reveal delay={0.24} onMount>
            <p className="mt-8 max-w-md leading-relaxed text-pretty text-muted-foreground">
              {profile.tagline}
            </p>
          </Reveal>

          <Reveal delay={0.3} onMount>
            <ul className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2">
              {profile.focusAreas.map((area) => (
                <li key={area} className="eyebrow text-accent">
                  {area}
                </li>
              ))}
            </ul>
          </Reveal>

          <Reveal delay={0.36} onMount>
            <div className="mt-10 flex flex-wrap items-center gap-3">
              <a
                href={`mailto:${profile.email}`}
                className="rounded-full bg-accent px-6 py-3 text-sm font-medium text-accent-foreground transition-opacity duration-200 hover:opacity-90"
              >
                Start a conversation
              </a>
              <a
                href={profile.resumeUrl}
                className="rounded-full border border-rule px-6 py-3 text-sm font-medium transition-colors duration-200 hover:border-foreground"
              >
                Résumé
              </a>
            </div>
          </Reveal>
        </div>

        <Reveal delay={0.12} onMount>
          <SystemMap />
        </Reveal>
      </div>
    </section>
  );
}
