import { DrawnRule, Reveal } from "@/components/reveal";

export function SectionHeading({
  title,
  meta,
}: {
  title: string;
  /** Small right-aligned counter, e.g. "03 case studies". */
  meta?: string;
}) {
  return (
    <>
      <Reveal>
        <div className="flex flex-wrap items-baseline justify-between gap-4">
          <h2 className="font-serif text-3xl tracking-[-0.015em] sm:text-4xl">
            {title}
          </h2>
          {meta ? (
            <span className="eyebrow text-muted-foreground">{meta}</span>
          ) : null}
        </div>
      </Reveal>
      <DrawnRule className="mt-6" />
    </>
  );
}
