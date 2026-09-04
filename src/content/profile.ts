/**
 * Single source of truth for all portfolio content.
 * Edit this file to update the site — no component changes needed.
 */

export type Link = {
  label: string;
  href: string;
};

/**
 * A single headline number per project, drawn as a segmented meter.
 *
 * The bar is always a redundant encoding of the figure in `display` — never
 * decoration standing in for data. A project with no ratio to report uses
 * `kind: "count"`, which draws discrete filled segments instead of a track,
 * so a plain count is never mistaken for "100%".
 */
export type Meter =
  | { kind: "ratio"; label: string; display: string; /** 0–1. */ fill: number }
  | { kind: "count"; label: string; display: string; segments: number };

export type Project = {
  slug: string;
  title: string;
  /** Short kicker shown above the title. */
  kicker: string;
  /** One-line pitch. */
  summary: string;
  tech: string[];
  highlights: string[];
  meter: Meter;
  repo?: string;
  live?: string;
};

export type Experience = {
  company: string;
  role: string;
  period: string;
  location: string;
  bullets: string[];
};

export type Education = {
  institution: string;
  degree: string;
  period: string;
  location: string;
};

export type Certification = {
  title: string;
  detail: string;
  date: string;
};

export type SkillGroup = {
  category: string;
  items: string[];
};

/** Headline numbers surfaced in the hero. Keep to three. */
export type Stat = {
  value: string;
  label: string;
};

export const profile = {
  name: "Pavan Srinivas Doma",
  title: "AI / ML Engineer",
  /** Hero display headline. Kept short — it is set in serif at ~60px. */
  headline: "Building intelligence that earns trust.",
  availability: "Available for select collaborations — 2026",
  focusAreas: ["RAG systems", "MLOps", "Evaluation"],
  tagline:
    "I build retrieval-augmented LLM systems and the data pipelines that keep them reliable in production.",
  location: "Buffalo, NY",
  email: "pavand.srini@gmail.com",
  // Phone is deliberately omitted from the public site to limit scraping/spam.
  // Add it here and render it in the contact section if you want it public.
  resumeUrl: "/resume.pdf",
  links: [
    { label: "Email", href: "mailto:pavand.srini@gmail.com" },
    { label: "LinkedIn", href: "https://www.linkedin.com/in/pavansrinivasdoma" },
    // TODO: add your GitHub profile — the single biggest gap for an ML portfolio.
    // { label: "GitHub", href: "https://github.com/<username>" },
  ] satisfies Link[],
  about: [
    "I'm an AI/ML engineer focused on making language models dependable enough to ship. Most of my work sits at the seam between retrieval, evaluation, and infrastructure — the parts that decide whether a demo survives contact with real users.",
    "I recently finished a Master's in Engineering Science at the University at Buffalo, after a B.Tech in Artificial Intelligence at SRM. Alongside my degree I led data operations at UB, where I owned the schemas, ETL pipelines, and reporting that the operations team ran on day to day.",
  ],
};

/**
 * The hero's "system map" tiles. Each names a real stage of the pipelines
 * described below, so the grid is labelled rather than purely ornamental.
 * `tone` maps to a --swatch-* token; colour carries no meaning on its own.
 */
export const systemMap = {
  caption: "Signals → context → decisions",
  tiles: [
    { label: "Ingest", tone: 1 },
    { label: "Validate", tone: 2 },
    { label: "Embed", tone: 3 },
    { label: "Retrieve", tone: 4 },
    { label: "Rank", tone: 5 },
    { label: "Generate", tone: 6 },
    { label: "Evaluate", tone: 7 },
    { label: "Monitor", tone: 8 },
  ],
};

export const stats: Stat[] = [
  { value: "97.5%", label: "RAG semantic relevance" },
  { value: "40%", label: "Query runtime reduction" },
  { value: "77", label: "NLP intent classes served" },
];

export const skills: SkillGroup[] = [
  {
    category: "LLMs & Generative AI",
    items: [
      "RAG Systems",
      "LangGraph",
      "Prompt Engineering",
      "Fine-tuning",
      "LLM Evaluation",
      "Hugging Face",
      "Vector Databases",
    ],
  },
  {
    category: "ML & Data",
    items: [
      "PyTorch",
      "TensorFlow",
      "Keras",
      "Scikit-Learn",
      "Pandas",
      "NumPy",
      "Matplotlib",
    ],
  },
  {
    category: "Languages & Tools",
    items: ["Python", "SQL", "FastAPI", "Git", "MLflow"],
  },
  {
    category: "Cloud & Infrastructure",
    items: [
      "AWS EC2",
      "AWS ECS",
      "AWS Lambda",
      "Docker",
      "Containerization",
      "Distributed Systems",
    ],
  },
  {
    category: "Domains",
    items: [
      "Machine Learning",
      "Natural Language Processing",
      "Data Analytics",
    ],
  },
];

export const projects: Project[] = [
  {
    slug: "rag-conversational-ai",
    title: "Retrieval-Augmented Conversational AI",
    kicker: "LLM Systems",
    summary:
      "A production-scale RAG system with validated semantic relevance and containerized deployment on AWS ECS.",
    tech: ["RAG", "Vector DB", "AWS ECS", "Docker", "Python"],
    meter: {
      kind: "ratio",
      label: "Semantic relevance",
      display: "97.5%",
      fill: 0.975,
    },
    highlights: [
      "Validated semantic relevance at 97.5% accuracy alongside ML engineers.",
      "Containerized deployment on AWS ECS with monitoring infrastructure.",
      "Context engineering, memory management, and structured output validation for reliable, context-aware responses.",
    ],
  },
  {
    slug: "consumer-complaint-classification",
    title: "Consumer Complaint Classification",
    kicker: "Scalable NLP",
    summary:
      "An intent classifier for banking customer queries that routes most traffic automatically without sacrificing accuracy.",
    tech: ["NLP", "Text Classification", "Python", "Scikit-Learn"],
    meter: {
      kind: "ratio",
      label: "Intent accuracy",
      display: "89.5%",
      fill: 0.895,
    },
    highlights: [
      "89.5% accuracy across 77 distinct intent classes.",
      "Confidence-threshold pipeline lets 49.6% of predictions skip manual review.",
      "Maintains 99.8% accuracy on auto-approved cases.",
    ],
  },
  {
    slug: "credit-scoring-segmentation",
    title: "Credit Scoring & Customer Segmentation",
    kicker: "Data-Driven Systems",
    summary:
      "A credit risk scoring system built around a deliberate feature engineering strategy and tracked experimentation.",
    tech: ["MLflow", "Feature Engineering", "Scikit-Learn", "Pandas"],
    meter: {
      kind: "count",
      label: "Model approaches compared",
      display: "5",
      segments: 5,
    },
    highlights: [
      "Defined feature engineering strategy through cross-functional collaboration.",
      "Compared five model approaches with MLflow experiment tracking.",
      "Validated business logic against data quality trade-offs with senior engineers.",
    ],
  },
];

export const experience: Experience[] = [
  {
    company: "University at Buffalo",
    role: "Data Engineer — Operations Lead",
    period: "Sep 2024 – Dec 2025",
    location: "Buffalo, NY",
    bullets: [
      "Designed and maintained a normalized database schema (people, inventory, transactions) with validation rules and data quality checks that ensured 100% transactional integrity.",
      "Reduced query runtime by 40% by building real-time KPI dashboards with advanced SQL — window functions, CTEs, aggregations — and optimizing the underlying queries.",
      "Engineered a production resource allocation pipeline using SQL window functions and time-series decomposition, validating business logic directly with stakeholders.",
      "Improved asset utilization efficiency by 25% through ETL query refactoring and schema redesign.",
      "Standardized and documented ETL pipelines for stock tracking, adding data quality gates and error-handling protocols that cut ingestion errors by 30% and shortened refresh cycles.",
    ],
  },
];

export const education: Education[] = [
  {
    institution: "University at Buffalo, SUNY",
    degree: "M.S. in Engineering Science",
    period: "Jan 2026",
    location: "Buffalo, NY",
  },
  {
    institution: "SRM Institute of Science and Technology",
    degree: "B.Tech in Artificial Intelligence",
    period: "May 2024",
    location: "Chennai, India",
  },
];

export const certifications: Certification[] = [
  {
    title: "Claude with Amazon Bedrock",
    detail: "Generative AI & LLM application development",
    date: "Jul 2026",
  },
  {
    title: "AWS Cloud Practitioner",
    detail: "Cloud platform deployment & AI services",
    date: "Jan 2026",
  },
];

export const sections = [
  { id: "work", label: "Work" },
  { id: "experience", label: "Experience" },
  { id: "skills", label: "Skills" },
  { id: "about", label: "About" },
] as const;
