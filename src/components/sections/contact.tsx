import { MaskedLines, Reveal } from "@/components/reveal";
import { profile } from "@/content/profile";

const HEADLINE_LINES = ["If the problem matters,", "I'd love to hear about it."];

export function Contact() {
  return (
    <footer id="contact" className="bg-band text-band-foreground">
      <div className="mx-auto w-full max-w-6xl px-6 py-20 sm:px-10 sm:py-28">
        <Reveal>
          <p className="eyebrow text-band-muted">Let&rsquo;s make the useful thing</p>
        </Reveal>

        <h2 className="mt-6 font-serif text-[2rem] leading-[1.15] tracking-[-0.015em] sm:text-5xl">
          <MaskedLines lines={HEADLINE_LINES} />
        </h2>

        <Reveal delay={0.2}>
          <div className="mt-10 flex flex-wrap items-center gap-4">
            <a
              href={`mailto:${profile.email}`}
              className="group inline-flex items-center gap-2.5 rounded-full border border-band-border bg-band-foreground/10 px-6 py-3 text-sm font-medium transition-colors duration-200 hover:bg-band-foreground/20"
            >
              Start a conversation
              <svg
                viewBox="0 0 16 16"
                aria-hidden="true"
                className="size-3.5 transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M4 12 12 4M6 4h6v6" />
              </svg>
            </a>
            <a
              href={`mailto:${profile.email}`}
              className="inline-block py-3 text-sm break-all text-band-muted underline decoration-band-border underline-offset-4 transition-colors duration-200 hover:text-band-foreground"
            >
              {profile.email}
            </a>
          </div>
        </Reveal>

        <Reveal delay={0.26}>
          <ul className="mt-20 flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-band-border pt-8">
            <li className="eyebrow text-band-muted">
              {profile.name} / {profile.title}
            </li>
            {profile.links.map((link) => (
              <li key={link.href}>
                <a
                  href={link.href}
                  target={link.href.startsWith("http") ? "_blank" : undefined}
                  rel={
                    link.href.startsWith("http")
                      ? "noreferrer noopener"
                      : undefined
                  }
                  className="eyebrow -my-2 inline-block py-3 text-band-muted transition-colors duration-200 hover:text-band-foreground"
                >
                  {link.label}
                </a>
              </li>
            ))}
            <li className="eyebrow text-band-muted sm:ml-auto">
              © {new Date().getFullYear()}
            </li>
          </ul>
        </Reveal>
      </div>
    </footer>
  );
}
