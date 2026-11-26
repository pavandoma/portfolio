import type { Metadata } from "next";
import Link from "next/link";
import { Badges } from "@/components/site/badges";
import { Capabilities } from "@/components/site/capabilities";
import { AgentConnect } from "@/components/site/agent-connect";
import { ContactForm } from "@/components/site/contact-form";
import { EyeCard } from "@/components/site/eye-card";
import { Reveal } from "@/components/site/reveal";
import { SectionHead } from "@/components/site/section-head";
import { githubIcon, SiteShell } from "@/components/site/shell";
import { formatDate, posts, readingMinutes } from "@/content/blog";
import { profile, skills, stats } from "@/content/profile";
import {
  displayName,
  experience,
  github,
  email,
  linkedin,
  mcpUrl,
  projects,
} from "@/content/site";

// Title, description and social cards come from the root layout.
export const metadata: Metadata = {
  alternates: { canonical: "/" },
};

/** Button hover motion: a small lift, and any arrow inside slides along. */
const lift =
  "transition-[translate,scale,background-color,border-color,color,box-shadow] duration-300 ease-out motion-safe:hover:-translate-y-0.5 active:translate-y-0 active:scale-[0.97] motion-reduce:translate-none";
const btnPrimary = `group/btn inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-medium text-black hover:bg-emerald-400 hover:shadow-lg hover:shadow-emerald-500/25 ${lift}`;
const btnIcon = `flex h-11 w-11 items-center justify-center rounded-full border border-white/10 text-gray-300 hover:border-emerald-400/60 hover:bg-emerald-400/10 hover:text-emerald-300 [&>svg]:transition-transform [&>svg]:duration-300 motion-safe:hover:[&>svg]:scale-110 ${lift}`;
const arrow = (
  <svg
    viewBox="0 0 24 24"
    className="h-4 w-4 transition-transform duration-300 motion-safe:group-hover/btn:translate-x-1 motion-reduce:translate-none"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    <path d="M5 12h14M13 6l6 6-6 6" />
  </svg>
);

const chip =
  "rounded-full border border-emerald-400/20 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300";

export default function HomePage() {
  const firstName = displayName.split(" ")[0];

  return (
    <SiteShell>
      <main className="relative">
        {/* ── Hero ─────────────────────────────────────────── */}
        <section
          id="home"
          className="relative flex min-h-svh items-center px-6 pb-20 pt-28"
        >
          <div className="relative mx-auto grid w-full max-w-7xl items-center gap-16 lg:grid-cols-[1.25fr_1fr]">
            <Reveal>
              <p className="mb-4 text-emerald-400">Hello, I&apos;m</p>
              <h1 className="text-5xl leading-[1.05] tracking-[-0.025em] text-white md:text-7xl">{displayName}</h1>
              <p className="mt-5 text-2xl leading-snug text-gray-200 md:text-3xl">
                I&apos;m an{" "}
                <span className="text-emerald-400">
                  {profile.title}
                </span>{" "}
                building{" "}
                LLM systems that earn trust
              </p>
              <AgentConnect url={mcpUrl} />

              <div className="mt-10 flex flex-wrap items-center gap-4">
                <a href="#projects" className={btnPrimary}>
                  View my work
                  {arrow}
                </a>
                <a href={github} target="_blank" rel="noreferrer" aria-label="GitHub" className={btnIcon}>
                  {githubIcon()}
                </a>
                {linkedin && (
                  <a
                    href={linkedin}
                    target="_blank"
                    rel="noreferrer"
                    aria-label="LinkedIn"
                    className={btnIcon}
                  >
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor" aria-hidden="true">
                      <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.5c0-1.3-.02-3-1.83-3-1.84 0-2.12 1.43-2.12 2.9V21H9z" />
                    </svg>
                  </a>
                )}
                <a
                  href={`mailto:${email}`}
                  aria-label="Email"
                  className={btnIcon}
                >
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                    <rect x="3" y="5" width="18" height="14" rx="2" />
                    <path d="m3 7 9 6 9-6" />
                  </svg>
                </a>
              </div>
            </Reveal>

            <Reveal delay={200}>
              <EyeCard />
            </Reveal>
          </div>
        </section>

        <Badges />

        {/* ── About ────────────────────────────────────────── */}
        <section id="about" className="scroll-mt-20 px-4 py-10 md:px-6 md:py-14">
          <div className="mx-auto max-w-7xl rounded-[2rem] border border-white/10 bg-gray-950/80 px-6 py-16 md:px-12 md:py-20">
            <SectionHead title="About Me" sub="Making language models dependable enough to ship" />
            <div className="grid gap-12 lg:grid-cols-2">
              <Reveal>
                {profile.about.slice(0, 1).map((p) => (
                  <p key={p.slice(0, 20)} className="mb-5 leading-relaxed text-gray-300">
                    {p}
                  </p>
                ))}
                <div className="mt-8 flex flex-wrap gap-3">
                  {profile.focusAreas.map((f) => (
                    <span key={f} className={chip}>
                      {f}
                    </span>
                  ))}
                </div>
              </Reveal>
              <div className="grid gap-5 sm:grid-cols-3 lg:grid-cols-1 xl:grid-cols-3">
                {stats.map((s, i) => (
                  <Reveal key={s.label} delay={i * 100}>
                    <div className="h-full rounded-xl border border-white/5 bg-black/40 p-6 transition-colors hover:border-emerald-400/30">
                      <p className="text-4xl font-medium text-emerald-400">
                        {s.value}
                      </p>
                      <p className="mt-3 text-sm text-gray-400">{s.label}</p>
                    </div>
                  </Reveal>
                ))}
              </div>
            </div>
          </div>
        </section>

        {/* ── Capabilities (staggered cards) ───────────────── */}
        <Capabilities />

        {/* ── Skills ───────────────────────────────────────── */}
        <section id="skills" className="scroll-mt-20 px-4 py-10 md:px-6 md:py-14">
          <div className="mx-auto max-w-7xl rounded-[2rem] border border-white/10 bg-gray-950/80 px-6 py-16 md:px-12 md:py-20">
            <SectionHead
              title="Skills & Technologies"
              sub="The tools I use to take models from notebook to production"
            />
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {skills.map((g, i) => (
                <Reveal key={g.category} delay={(i % 3) * 100}>
                  <div className="h-full rounded-xl border border-white/5 bg-black/40 p-6">
                    <h3 className="mb-5 text-lg text-white">{g.category}</h3>
                    <div className="flex flex-wrap gap-2">
                      {g.items.map((item) => (
                        <span
                          key={item}
                          className="rounded-md border border-white/10 bg-white/5 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-emerald-400/40 hover:text-emerald-300"
                        >
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ── Projects ─────────────────────────────────────── */}
        <section id="projects" className="px-6 py-24 md:py-32">
          <div className="mx-auto max-w-7xl">
            <SectionHead
              title="Featured Projects"
              sub="Systems I've built, with the number that mattered most for each"
            />
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
              {projects.map((p, i) => (
                <Reveal key={p.slug} delay={i * 120}>
                  <article className="group relative flex h-full flex-col rounded-2xl border border-white/5 bg-gray-900/70 p-7 transition-[translate,border-color] duration-300 motion-safe:hover:-translate-y-1 hover:border-emerald-400/30 motion-reduce:translate-none">
                    <div className="flex items-start justify-between gap-4">
                      <p className="pt-2 font-mono text-xs uppercase tracking-[0.2em] text-emerald-400">
                        {p.kicker}
                      </p>
                      <a
                        href={p.href}
                        target="_blank"
                        rel="noreferrer"
                        aria-label={`${p.title} on GitHub`}
                        className="flex h-11 w-11 shrink-0 items-center md:h-9 md:w-9 justify-center rounded-full border border-white/10 text-gray-400 transition-[background-color,border-color,color,scale] duration-300 active:scale-90 hover:border-emerald-400 hover:bg-emerald-400 hover:text-black group-hover:border-emerald-400/40 group-hover:text-emerald-300 [&>svg]:transition-transform [&>svg]:duration-300 motion-safe:hover:[&>svg]:rotate-45"
                      >
                        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                          <path d="M7 17 17 7M8 7h9v9" />
                        </svg>
                      </a>
                    </div>
                    <h3 className="mt-3 text-xl tracking-[-0.01em] text-white">{p.title}</h3>
                    <p className="mt-3 text-sm leading-relaxed text-gray-400">{p.summary}</p>

                    <div className="mt-6 rounded-lg bg-black/50 p-4">
                      <div className="flex items-baseline justify-between">
                        <span className="text-xs text-gray-400">{p.meter.label}</span>
                        <span className="text-2xl font-medium text-emerald-400">
                          {p.meter.display}
                        </span>
                      </div>
                      {p.meter.kind === "ratio" ? (
                        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/10">
                          <div
                            className="h-full rounded-full bg-emerald-400"
                            style={{ width: `${p.meter.fill * 100}%` }}
                          />
                        </div>
                      ) : (
                        <div className="mt-3 flex gap-1.5">
                          {Array.from({ length: p.meter.segments }, (_, k) => (
                            <span key={k} className="h-1.5 flex-1 rounded-full bg-emerald-400" />
                          ))}
                        </div>
                      )}
                    </div>

                    <div className="flex-1" />

                    <div className="mt-6 flex flex-wrap gap-2">
                      {p.tech.map((t) => (
                        <span key={t} className="rounded bg-white/5 px-2 py-1 text-xs text-gray-300">
                          {t}
                        </span>
                      ))}
                    </div>
                  </article>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ── Blogs ────────────────────────────────────────── */}
        <section id="blogs" className="px-6 py-24 md:py-32">
          <div className="mx-auto max-w-7xl">
            <SectionHead title="Blogs" sub="The stories behind the projects, and what each one taught me" />
            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
              {posts.map((post, i) => (
                <Reveal key={post.slug} delay={i * 120}>
                  <Link
                    href={`/blog/${post.slug}/`}
                    className="group/btn flex h-full flex-col rounded-2xl border border-white/5 bg-gray-900/70 p-7 transition-[translate,border-color,scale] duration-300 motion-safe:hover:-translate-y-1 hover:border-emerald-400/30 active:scale-[0.99] motion-reduce:translate-none"
                  >
                    <p className="font-mono text-xs text-gray-400">
                      {formatDate(post.date)} · {readingMinutes(post)} min read
                    </p>
                    <h3 className="mt-4 text-xl leading-snug tracking-[-0.01em] text-white transition-colors group-hover/btn:text-emerald-300">
                      {post.title}
                    </h3>
                    <p className="mt-3 text-sm leading-relaxed text-gray-400">{post.excerpt}</p>
                    <div className="flex-1" />
                    <div className="mt-6 flex items-baseline gap-3 border-t border-white/5 pt-5">
                      <span className="text-2xl font-medium text-emerald-400">{post.figure.value}</span>
                      <span className="text-xs text-gray-400">{post.figure.label}</span>
                    </div>
                    <span className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-emerald-300">
                      Read the story
                      {arrow}
                    </span>
                  </Link>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* ── Experience ───────────────────────────────────── */}
        <section id="experience" className="scroll-mt-20 px-4 py-10 md:px-6 md:py-14">
          <div className="mx-auto max-w-5xl rounded-[2rem] border border-white/10 bg-gray-950/80 px-6 py-16 md:px-12 md:py-20">
            <SectionHead title="Experience" sub="Where the pipelines met real operations" />
            {experience.map((job) => (
              <Reveal key={job.company}>
                <div className="relative border-l border-emerald-400/30 pl-8">
                  <span className="absolute -left-[5px] top-2 h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <h3 className="text-xl text-white">{job.role}</h3>
                    <span className="font-mono text-xs text-gray-400">{job.period}</span>
                  </div>
                  <p className="mt-1 text-emerald-400">{job.company}</p>
                  <ul className="mt-5 space-y-3">
                    {job.bullets.slice(0, 3).map((b) => (
                      <li key={b} className="flex gap-3 text-gray-300">
                        <span className="mt-2.5 h-1 w-1 shrink-0 rounded-full bg-gray-500" />
                        {b}
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            ))}
          </div>
        </section>

        {/* ── Contact ──────────────────────────────────────── */}
        <section id="contact" className="scroll-mt-20 px-4 py-10 md:px-6 md:py-14">
          <div className="mx-auto max-w-7xl rounded-[2rem] border border-white/10 bg-gray-950/80 px-6 py-16 md:px-12 md:py-20">
            <SectionHead
              title="Get In Touch"
              sub="Let's talk."
            />
            <div className="grid gap-12 lg:grid-cols-2">
              <Reveal>
                <ContactForm email={email} />
              </Reveal>
              <Reveal delay={150}>
                <h3 className="text-2xl text-white">Let&apos;s connect</h3>
                <p className="mt-4 leading-relaxed text-gray-400">{profile.availability.replace(/\s+—\s+\d{4}$/, "")}.</p>
                <div className="mt-8 space-y-4">
                  <a
                    href={`mailto:${email}`}
                    className={`flex items-center gap-4 rounded-xl border border-white/5 bg-gray-900/60 p-5 hover:border-emerald-400/30 ${lift}`}
                  >
                    <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-400">
                      <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden="true">
                        <rect x="3" y="5" width="18" height="14" rx="2" />
                        <path d="m3 7 9 6 9-6" />
                      </svg>
                    </span>
                    <span>
                      <span className="block text-sm text-gray-400">Email</span>
                      <span className="text-gray-200">{email}</span>
                    </span>
                  </a>
                  {linkedin && (
                    <a
                      href={linkedin}
                      target="_blank"
                      rel="noreferrer"
                      className={`flex items-center gap-4 rounded-xl border border-white/5 bg-gray-900/60 p-5 hover:border-emerald-400/30 ${lift}`}
                    >
                      <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-400/10 text-emerald-400">
                        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="currentColor" aria-hidden="true">
                          <path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM3 9h4v12H3zM9 9h3.8v1.7h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V21h-4v-5.5c0-1.3-.02-3-1.83-3-1.84 0-2.12 1.43-2.12 2.9V21H9z" />
                        </svg>
                      </span>
                      <span>
                        <span className="block text-sm text-gray-400">LinkedIn</span>
                        <span className="text-gray-200">{displayName}</span>
                      </span>
                    </a>
                  )}
                </div>
              </Reveal>
            </div>
          </div>
        </section>
      </main>

      <footer className="relative border-t border-white/5 px-6 py-10 text-center text-sm text-gray-400">
        © {new Date().getFullYear()} {displayName}. Built by {firstName} with Next.js and Tailwind CSS.
      </footer>
    </SiteShell>
  );
}
