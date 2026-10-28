// Subset of the backend schemas used by the UI.

export type Verification = "unverified" | "verified" | "needs_review" | "rejected" | "user_corrected";

export interface ClaimFlag { kind: string; span: string; message: string; severity: "info" | "warning" | "critical" }
export interface FactCheck { passed: boolean; problems: string[] }
export interface Variant { id: string; text: string; emphasis: string[]; origin: string; approved: boolean; fact_check: FactCheck | null }
export interface SourceRef { document_name: string | null; page: number | null; section: string | null; line: number | null; original_text: string }
export interface Metric { raw: string; unit: string }

export interface Achievement {
  id: string; text: string; original_text: string; source_ref: SourceRef; verification: Verification;
  technologies: string[]; competencies: string[]; metrics: Metric[]; flags: ClaimFlag[];
  evidence_strength: string; allowed_usage: "any" | "with_care" | "do_not_use"; evidence_ids: string[];
  variants: Variant[]; note: string | null;
}
export interface Role {
  id: string; title: string; organization: string; location: string | null; start: string | null; end: string | null;
  date_text: string; employment_type: string; verification: Verification; achievements: Achievement[];
}
export interface Project {
  id: string; name: string; subtitle: string | null; context: string; repo_url: string | null; url: string | null;
  technologies: string[]; verification: Verification; achievements: Achievement[];
}
export interface Education { id: string; institution: string; degree: string; level: string; location: string | null; date_text: string; status: string; verification: Verification }
export interface Certification { id: string; name: string; detail: string | null; date_text: string; verification: Verification }
export interface Skill { id: string; name: string; display: string; category: string | null; verification: Verification; evidence_achievement_ids: string[]; self_reported_only: boolean; derived_from_bullets: boolean }
export interface Evidence { id: string; kind: string; title: string; uri: string | null; description: string; technologies: string[]; linked_ids: string[] }
export interface Issue { id: string; kind: string; target_id: string | null; field: string | null; message: string; severity: "info" | "warning" | "critical"; status: "open" | "resolved" | "dismissed"; options: string[] }
export interface Personal { name: string; email: string | null; phone: string | null; location: string | null; links: { label: string; url: string }[] }
export interface CandidateProfile {
  personal: Personal; roles: Role[]; projects: Project[]; education: Education[]; certifications: Certification[];
  skills: Skill[]; evidence: Evidence[]; issues: Issue[];
  work_authorization: { status: string; note: string | null; has_security_clearance: boolean | null };
}
export interface Completeness { score: number; checks: Record<string, boolean>; achievements_total: number; achievements_reviewed: number; open_issues: number; critical_issues: number }
export interface ProfileResponse { revision: { id: string; number: number; reason: string; created_at: string }; profile: CandidateProfile; completeness: Completeness }

export interface Requirement { id: string; text: string; category: string; category_basis: string; kind: string; importance: number; skills: { canonical: string; as_written: string }[] }
export interface JobAnalysis {
  title: string; company: string | null; location: string | null; work_arrangement: string; seniority: string;
  employment_type: string | null; requirements: Requirement[]; min_years_experience: number | null; domains: string[];
  injection_warnings: string[]; skill_importance: { canonical: string; as_written: string; importance: number }[];
}
export interface Job { id: string; title: string; company: string | null; location: string | null; url: string | null; created_at: string; duplicate_of: string | null; analysis?: JobAnalysis; raw_text?: string; duplicate?: boolean; notes?: string[] }

export interface Dimension { key: string; label: string; weight: number; score: number; points: number; explanation: string; details: string[] }
export interface ScoreCard { name: string; total: number; dimensions: Dimension[]; notes: string[] }
export interface EvidenceLink { target_type: string; target_id: string; excerpt: string; reason: string; verification: string | null }
export interface RequirementMatch {
  requirement_id: string; requirement_text: string; category: string; kind: string; importance: number;
  level: "direct" | "partial" | "related" | "none" | "unknown"; level_label: string; score: number; explanation: string;
  matched_skills: string[]; missing_skills: string[]; related_skills: string[]; evidence: EvidenceLink[];
}
export interface Gate { gate: string; requirement_text: string; status: "met" | "not_met" | "unclear" | "needs_user_input"; explanation: string }
export interface MatchReport {
  job_title: string; company: string | null; job_fit: ScoreCard; requirement_matches: RequirementMatch[]; gates: Gate[];
  strengths: string[]; missing_mandatory: string[]; missing_preferred: string[]; recommendations: string[];
  scoring_version: string; input_hash: string; disclaimer: string;
}

export interface ResumeBullet { id: string; text: string; achievement_ids: string[]; origin: string; approved: boolean; relevance: number; flags: ClaimFlag[] }
export interface ExperienceEntry { role_id: string; title: string; organization: string; location: string | null; date_range: string; bullets: ResumeBullet[] }
export interface ProjectEntry { project_id: string; name: string; descriptor: string | null; date_range: string; bullets: ResumeBullet[] }
export interface TailoredResume {
  header: { name: string; target_title: string; contact: string[] };
  summary: { text: string; kind: string; source_ids: string[] }[];
  skills: { category: string; items: string[] }[];
  experience: ExperienceEntry[]; projects: ProjectEntry[];
  education: { degree: string; institution: string; date: string }[];
  certifications: { name: string; detail: string | null; date: string }[];
  omitted: { item_type: string; item_id: string; text: string; reason: string }[];
  layout: { page_target: number; body_font_size: number; margin_in: number; font_family: string };
  section_order: string[];
}
export interface ChangeLogEntry { kind: string; target: string; before: string | null; after: string | null; reason: string; evidence_ids: string[]; requires_approval: boolean }
export interface FieldCheck { field: string; expected: string; extracted: string | null; status: "pass" | "warn" | "fail" | "skipped"; detail: string }
export interface ATSReport { extractor: string; document_kind: string; score: number; page_count: number; fields: FieldCheck[]; checks: { name: string; status: string; detail: string }[] }
export interface ClaimTrace { location: string; text: string; source_ids: string[]; status: string; detail: string }
export interface Validation {
  ats: ATSReport[];
  integrity: { score: number; claims: ClaimTrace[]; unsupported: number; unverified: number; verified: number; fact_problems: string[]; employment_facts_preserved: boolean };
  qa: { score: number; issues: { category: string; code: string; severity: string; location: string; message: string; suggestion: string }[] };
  external: { adapter: string; category: string; status: string; detail: string; score: number | null }[];
}
export interface GeneratedFile { id: string; kind: string; filename: string; size_bytes: number; url: string }
export interface SummaryScores { job_fit: number | null; resume_alignment: number | null; ats_parsing: number | null; evidence_integrity: number | null; qa: number | null; critical_issues: number | null }
export interface ResumeVersion {
  id: string; job_id: string | null; variant: string | null; version_no: number; parent_id: string | null; status: string;
  created_at: string; approved_at: string | null; target_title: string; summary_scores: SummaryScores; files: GeneratedFile[];
  content?: TailoredResume; change_log?: ChangeLogEntry[]; validation?: Validation;
  scores?: { job_fit: ScoreCard; resume_alignment: ScoreCard; iterations: { iteration: number; scores: Record<string, number>; actions: string[] }[]; stop_reason: string };
}
export interface DiffToken { op: "equal" | "insert" | "delete"; text: string }
export interface Comparison {
  original_text: string; tailored_text: string; section_order: string[];
  bullets: { target: string; achievement_ids: string[]; before: string; after: string; tokens: DiffToken[]; origin: string; approved: boolean; position_before: number | null; position_after: number | null }[];
  omitted: { item_type: string; item_id: string; text: string; reason: string }[];
}
export interface ApplicationRow {
  job_id: string; title: string; company: string | null; location: string | null; url: string | null; analyzed_at: string;
  job_fit: number | null; resume_versions: number; latest_version_id: string | null; latest_alignment: number | null;
  latest_status: string | null; application_status: string; submitted_version_id: string | null; applied_at: string | null; notes: string;
}
export interface SystemStatus {
  version: string; database: string; pdftotext: boolean; firecrawl_configured: boolean; external_data_sharing: boolean;
  llm: { provider: string; model: string | null; available: boolean; detail: string };
  validators: { name: string; category: string; available: boolean; detail: string; sends_data_externally: boolean }[];
  profile: { exists: boolean; revision?: number; name?: string; completeness?: Completeness };
  counts: { jobs: number; resume_versions: number; applications: number };
}
export interface Preset { key: string; title: string; focus: string[] }
