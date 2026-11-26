import { Reveal } from "./reveal";

/** Centered section title with a short green rule, shared by every section. */
export function SectionHead({ title, sub }: { title: string; sub: string }) {
  return (
    <Reveal className="mx-auto mb-16 max-w-2xl text-center">
      <h2 className="text-4xl leading-[1.1] tracking-[-0.02em] text-white md:text-5xl">{title}</h2>
      <div className="mx-auto mt-5 h-1 w-20 rounded-full bg-emerald-400" />
      <p className="mt-6 text-gray-400">{sub}</p>
    </Reveal>
  );
}
