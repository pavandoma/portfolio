import { certifications } from "@/content/profile";
import { education } from "@/content/prototype";

type Badge = { title: string; issuer: string; mark: string };

const credentials: Badge[] = [
  ...certifications.map((c) => ({
    title: c.title,
    issuer: c.date,
    mark: c.title.includes("AWS") ? "AWS" : "AI",
  })),
  ...education.map((e) => ({
    title: e.degree,
    issuer: e.institution.split(",")[0],
    mark: e.degree.startsWith("Master") ? "MS" : "BS",
  })),
];

const tools = [
  "Python",
  "PyTorch",
  "RAG Systems",
  "LangGraph",
  "Hugging Face",
  "MLflow",
  "Docker",
  "AWS ECS",
  "FastAPI",
  "SQL",
];

/**
 * One row of items scrolling forever. The list is rendered twice and the
 * track slides by exactly half its width, so the loop has no visible seam.
 * Hovering pauses it; under reduced motion it stops and wraps instead.
 */
function Marquee({
  children,
  reverse = false,
  seconds,
}: {
  children: React.ReactNode;
  reverse?: boolean;
  seconds: number;
}) {
  return (
    <div className="group overflow-hidden motion-reduce:overflow-visible">
      <div
        className="flex w-max animate-[badge-scroll_var(--dur)_linear_infinite] group-hover:[animation-play-state:paused] motion-reduce:w-full motion-reduce:animate-none motion-reduce:flex-wrap motion-reduce:justify-center"
        style={
          {
            "--dur": `${seconds}s`,
            animationDirection: reverse ? "reverse" : "normal",
          } as React.CSSProperties
        }
      >
        <div className="flex shrink-0 gap-4 pr-4 motion-reduce:flex-wrap motion-reduce:justify-center">
          {children}
        </div>
        <div className="flex shrink-0 gap-4 pr-4 motion-reduce:hidden" aria-hidden="true">
          {children}
        </div>
      </div>
    </div>
  );
}

export function Badges() {
  return (
    <section id="badges" aria-label="Badges" className="relative border-y border-white/5 bg-black/60 py-14">
      <p className="mb-8 text-center font-mono text-xs uppercase tracking-[0.3em] text-gray-400">
        Badges &amp; credentials
      </p>

      <div className="space-y-4">
        <Marquee seconds={30}>
          {credentials.map((b) => (
            <div
              key={b.title}
              className="flex items-center gap-4 rounded-full border border-white/10 bg-gray-900 py-2 pl-2 pr-6 transition-colors hover:border-emerald-400/40"
            >
              <span className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-emerald-400 font-mono text-xs font-semibold text-emerald-400">
                {b.mark}
              </span>
              <span className="whitespace-nowrap">
                <span className="block text-sm text-white">{b.title}</span>
                <span className="block text-xs text-gray-400">{b.issuer}</span>
              </span>
            </div>
          ))}
        </Marquee>

        <Marquee seconds={40} reverse>
          {tools.map((t) => (
            <span
              key={t}
              className="flex items-center gap-2 whitespace-nowrap rounded-full border border-emerald-400/20 bg-emerald-400/10 px-4 py-2 text-sm text-emerald-300"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {t}
            </span>
          ))}
        </Marquee>
      </div>
    </section>
  );
}
