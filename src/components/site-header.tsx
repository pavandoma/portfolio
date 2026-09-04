import Link from "next/link";
import { profile, sections } from "@/content/profile";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/85 backdrop-blur-md">
      <nav
        aria-label="Primary"
        className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-6 px-6 sm:px-10"
      >
        <Link
          href="/"
          className="py-3 font-serif text-base tracking-tight transition-colors duration-200 hover:text-accent"
        >
          {profile.name}
        </Link>

        <ul className="hidden items-center gap-8 md:flex">
          {sections.map((section) => (
            <li key={section.id}>
              <a
                href={`#${section.id}`}
                className="eyebrow inline-block py-3 text-muted-foreground transition-colors duration-200 hover:text-foreground"
              >
                {section.label}
              </a>
            </li>
          ))}
        </ul>

        <span className="eyebrow text-muted-foreground">{profile.title}</span>
      </nav>
    </header>
  );
}
