/**
 * Home-page content that goes beyond `profile.ts`: the short display name,
 * resolved contact links, the extra Credit Union project, and everything the
 * agent (MCP) endpoint serves.
 */
import {
  certifications,
  education,
  experience,
  profile,
  projects as baseProjects,
  skills,
  type Project,
} from "./profile";
import { SITE_URL } from "@/lib/site";

export { education, experience };

export const displayName = "Pavan Srinivas";
export const email = profile.email;
const link = (label: string) => profile.links.find((l) => l.label === label)?.href ?? "";
export const github = link("GitHub");
export const linkedin = link("LinkedIn");

/** The blog lives on this site, in the home page's Blogs section. */
export const blogUrl = `${SITE_URL}/#blogs`;

/**
 * Agent endpoint: a small MCP server (Streamable HTTP) at public/api/mcp.php,
 * served at the shorter /mcp by a rewrite in public/.htaccess.
 */
export const mcpUrl = `${SITE_URL}/mcp`;

const creditUnion: Project = {
  slug: "credit-union-assistant",
  title: "Credit Union Assistant",
  kicker: "Grounded Answers",
  summary:
    "A deterministic multi-agent system that answers member questions from five dated snapshots of a real credit-union website, with no stale values.",
  tech: ["Python", "Multi-agent", "Retrieval", "Unit tests"],
  meter: { kind: "ratio", label: "Score on 40-question set", display: "0.97", fill: 0.97 },
  highlights: [
    "Six agents plus an answer agent, standard-library Python.",
    "37 contradictions resolved by source authority and effective date.",
    "p95 answers under 0.1 s; 25 unit tests pass.",
  ],
  repo: "https://github.com/pavandoma/credit-union-assistant",
};

/** Every project card links to GitHub: its own repo when there is one. */
export const projects: (Project & { href: string })[] = [...baseProjects, creditUnion].map(
  (p) => ({ ...p, href: p.repo ?? github }),
);

/** Everything the agent endpoint serves, generated at build time. */
export function agentProfile() {
  return {
    name: profile.name,
    title: profile.title,
    summary: profile.about[0],
    focusAreas: profile.focusAreas,
    contact: { email, linkedin, github, portfolio: SITE_URL, blog: blogUrl },
    education: education.map(({ degree, institution, period }) => ({
      degree,
      institution,
      completed: period,
    })),
    experience: experience.map(({ company, role, period, bullets }) => ({
      company,
      role,
      period,
      highlights: bullets,
    })),
    projects: projects.map(({ title, summary, tech, highlights, meter, href }) => ({
      title,
      summary,
      headline: `${meter.label}: ${meter.display}`,
      highlights,
      tech,
      link: href,
    })),
    skills: skills.map(({ category, items }) => ({ category, items })),
    certifications: certifications.map(({ title, date }) => ({ title, date })),
  };
}
