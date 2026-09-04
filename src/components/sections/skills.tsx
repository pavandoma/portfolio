import { Reveal } from "@/components/reveal";
import { SectionHeading } from "@/components/section-heading";
import { skills } from "@/content/profile";

export function Skills() {
  return (
    <section
      id="skills"
      className="mx-auto w-full max-w-6xl px-6 py-20 sm:px-10 sm:py-24"
    >
      <SectionHeading title="Toolkit" meta="What I reach for" />

      <ul className="mt-4">
        {skills.map((group, index) => (
          <Reveal
            as="li"
            key={group.category}
            delay={index * 0.06}
            className="grid grid-cols-1 gap-3 border-b border-border py-7 md:grid-cols-[13rem_1fr] md:gap-10"
          >
            <h3 className="eyebrow text-muted-foreground">{group.category}</h3>
            <ul className="flex flex-wrap gap-x-5 gap-y-2.5">
              {group.items.map((item) => (
                <li key={item} className="whitespace-nowrap">
                  {item}
                </li>
              ))}
            </ul>
          </Reveal>
        ))}
      </ul>
    </section>
  );
}
