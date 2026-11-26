/**
 * Sample blog posts for the home page: short stories behind the
 * projects. Every figure here is one already confirmed for the portfolio;
 * nothing else is claimed. Edit or replace freely.
 */

export type Post = {
  slug: string;
  title: string;
  /** One-line hook shown on the card. */
  excerpt: string;
  date: string;
  /** Project the story is about. */
  project: string;
  /** The single number the story turns on, shown as a callout. */
  figure: { value: string; label: string };
  tags: string[];
  repo: string;
  /** Paragraphs. A paragraph starting with "## " is a subheading. */
  body: string[];
};

const github = "https://github.com/pavandoma";

export const posts: Post[] = [
  {
    slug: "no-model-writes-a-fact",
    title: "Why no language model writes a fact in my credit-union assistant",
    excerpt:
      "When five versions of the same website disagree, the answer has to come from the right one. Here is how I made that deterministic.",
    date: "2026-11-12",
    project: "Credit Union Assistant",
    figure: { value: "0.97", label: "on the 40-question public set" },
    tags: ["Multi-agent", "Grounding", "Python"],
    repo: "https://github.com/pavandoma/credit-union-assistant",
    body: [
      "Members ask a credit union simple questions: what a rate is, what a fee costs, when a branch opens. The hard part is not finding an answer. It is finding the current one. I worked from five dated snapshots of a real credit-union website, and they did not always agree with each other.",
      "## Facts come from sources, not from a model",
      "I made one rule early: no language model writes a fact. The system is deterministic and uses only Python's standard library. Six agents each handle one part of the work, and an answer agent assembles the reply from what they return.",
      "## Settling disagreements on purpose",
      "Across the snapshots I found 37 contradictions. Each one is resolved by two rules applied in order: which source has more authority, then which has the later effective date. Because the rules are explicit, every answer can be traced back to the page and date it came from, and the system returned 0 stale values.",
      "## Fast enough to feel instant",
      "Without a model in the loop, answers are quick: the 95th-percentile answer time is under 0.1 seconds. The system scores 0.97 on the 40-question public set, and 25 unit tests keep the behaviour pinned down as it changes.",
    ],
  },
  {
    slug: "half-the-queue-skips-review",
    title: "Letting half the queue skip review without losing accuracy",
    excerpt:
      "A 77-intent classifier does not have to be perfect everywhere. It has to know when it is sure.",
    date: "2026-10-28",
    project: "Consumer Complaint Classification",
    figure: { value: "49.6%", label: "of queries cleared automatically" },
    tags: ["NLP", "Classification", "Scikit-Learn"],
    repo: github,
    body: [
      "Banking customers write in about 77 different kinds of problem. Routing each message to the right team by hand is slow, but routing it wrongly is worse. I trained an intent classifier on 13,083 customer queries to take some of that load.",
      "## Beat the baseline first",
      "Before anything clever, the model had to beat a plain TF-IDF baseline, which reached 85.7% accuracy. The classifier reached 89.5% across all 77 intents. Good, but not good enough to trust on every message.",
      "## Then decide when to trust it",
      "The more useful step was a confidence threshold. When the model is confident, the query goes straight through; when it is not, a person reviews it. Set that way, 49.6% of queries clear automatically, and those auto-cleared queries are 99.8% accurate.",
      "The lesson I keep coming back to: a model that knows its limits can be more useful than a slightly more accurate one that doesn't.",
    ],
  },
  {
    slug: "measuring-a-rag-system",
    title: "What it took to trust a RAG system's answers",
    excerpt:
      "A retrieval-augmented assistant is only as good as the context it is given. Measuring that was the real project.",
    date: "2026-10-09",
    project: "Retrieval-Augmented Conversational AI",
    figure: { value: "97.5%", label: "semantic relevance, validated" },
    tags: ["RAG", "Evaluation", "AWS ECS"],
    repo: github,
    body: [
      "A demo of a retrieval-augmented assistant is easy to make impressive. Keeping it reliable once real questions arrive is the part that takes the work. Most of what I did on this project sat between retrieval, evaluation and deployment.",
      "## Context is the product",
      "The quality of an answer depends on what the model is shown. I spent most of my effort on context engineering, memory management and validating structured outputs, so responses stayed grounded and aware of the conversation so far.",
      "## Measure it with the people who will rely on it",
      "Working alongside ML engineers, we validated semantic relevance at 97.5%. Having that number agreed with the people who would depend on the system mattered as much as the number itself.",
      "## Ship it where it can be watched",
      "The system runs in containers on AWS ECS with monitoring in place, so a drop in quality shows up as a signal rather than a complaint.",
    ],
  },
];

export const postBySlug = (slug: string) => posts.find((p) => p.slug === slug);

/** Rough reading time at 220 words a minute, never under one minute. */
export const readingMinutes = (p: Post) =>
  Math.max(1, Math.round(p.body.join(" ").split(/\s+/).length / 220));

export const formatDate = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
