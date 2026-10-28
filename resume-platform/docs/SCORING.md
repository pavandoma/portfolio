# How the scores work

Every number in this application is a transparent heuristic computed locally from your profile and the
posting. None of them is an employer's ATS score, and none predicts interview chances. Each report says
so, and each score shows the evidence behind it.

The platform keeps four scores apart on purpose:

| Score | Question it answers | Computed from |
|---|---|---|
| **Job Fit** | Are you a good match for this job? | the whole master profile |
| **Resume Alignment** | Does this generated resume show that match? | only what is on the generated resume |
| **ATS Parsing** | Can software read this file back correctly? | the rendered PDF and DOCX |
| **Evidence Integrity** | Is every claim on it backed by your profile? | the claim trace |

Eligibility gates (years, degree, work authorisation, clearance, required credentials) are reported
separately and are never folded into a score: a 90% fit with an unmet sponsorship gate is still shown as
unmet.

## Evidence levels

Each requirement in the posting is matched against your profile and gets one level:

| Level | Meaning | Credit |
|---|---|---|
| `direct` | the exact skill or qualification appears in a bullet, skill list, degree or certification | 1.0 |
| `partial` | a more specific skill satisfies a general ask (PyTorch for "deep learning"), or the evidence is weaker | 0.6 |
| `related` | a sibling, not a substitute (AWS for an Azure requirement) | 0.3 |
| `none` / `unknown` | no evidence, or the requirement cannot be judged (it becomes a question for you) | 0 |

Skills are resolved through a taxonomy (`backend/app/data/skills.yaml`) of canonical names, aliases,
parents ("specific satisfies generic") and sibling families. A TF-IDF similarity between the requirement
and your bullets is a secondary signal; it never turns `none` into `direct` on its own.

## Job Fit (default weights 30 / 25 / 15 / 15)

| Dimension | Weight | Measure |
|---|---:|---|
| Required skills and qualifications | 30 | importance-weighted evidence credit for mandatory requirements (preferred ones if the posting has none) |
| Relevant experience and projects | 25 | 75%: responsibilities and preferred items matched by your achievements (project-only evidence counts 80%); 25%: professional years against the posting's minimum |
| Technical keyword coverage | 15 | share of the posting's important skills you can truthfully claim (direct 1.0, partial 0.8, related 0.3) |
| Measurable impact | 15 | share of your six most relevant achievements that carry a number (verified 1.0, unverified 0.75) |

Job Fit = points earned ÷ 85 × 100. ATS parsing (10) and clarity (5) describe a document, not a person, so
they appear only in Resume Alignment. Weights can be changed per match (`POST /api/jobs/{id}/match`).

A skill's importance adds up over every requirement that names it, weighted by where the line sits
(mandatory 1.0, responsibilities 0.6, preferred 0.45, company context 0.15), with a boost when the job
title names it. Section headings and cue words ("must", "required", "nice to have", "bonus") decide which
list a line belongs to.

## Resume Alignment (30 / 25 / 15 / 15 / 10 / 5)

The same four dimensions, recomputed from the generated resume only (a skill you have but the resume
omits earns 30% of its keyword credit), plus:

| Dimension | Weight | Measure |
|---|---:|---|
| ATS parsing and formatting | 10 | the lowest ATS Parsing score across the extractors that ran |
| Clarity and conciseness | 5 | the QA score |

## ATS Parsing

Each rendered file is parsed back with PyMuPDF, python-docx and, when installed, poppler's `pdftotext`.
The parsed fields are compared with what was meant to be there:

| Field | Weight |
|---|---:|
| name, email, section headings, each role (title, organisation, dates) | 3 |
| phone, target title, education, skills, bullets | 2 |
| links, projects, certifications, summary | 1 |

Field score = weighted pass rate (a near miss counts half). For the PyMuPDF and python-docx reports, 25% of
the score comes from format checks: selectable text, single column, no tables or images in the text flow, no header/footer-only text,
consistent fonts and headings, no broken characters, reasonable whitespace, page count.

## Evidence Integrity

Every bullet, summary sentence and listed skill is traced to profile items. Score = supported claims ÷
all claims × 100. A claim is unsupported when its wording fails the fact check against its source (a new
number, technology, employer, year, or production / leadership / collaboration claim) or when it has no
source at all. A version with any unsupported claim cannot be approved.

## QA (clarity)

Starts at 100 and subtracts 15 per critical issue, 4 per warning and 1 per note. Checks include:

- employment facts changed from the profile, academic projects claiming production use (critical);
- wording that makes text sound machine-written ("leveraged", "spearheaded", "seamlessly", "cutting-edge",
  trailing "..., ensuring/enabling ..." clauses) and weak openers ("Responsible for", "Worked on");
- bullet length (aim 15–25 words; warning above 35, note below 8), tense (past for finished roles),
  repeated openers, a keyword used more than five times, inconsistent dates or punctuation;
- summary length, a summary without a number, a summary repeating a bullet word for word, a title that
  differs from the posting, unexplained abbreviations.

Mandatory requirements you do not meet are reported as gaps but are not deducted here: they belong to
Job Fit, and the resume must not hide or invent them.

## Revision loop

Up to three cycles (`RIP_MAX_REVISION_CYCLES`, never more than 3):

1. fit to the page, render PDF and DOCX, run ATS parsing, integrity and QA;
2. diagnose: unsupported claims, academic projects claiming production use, mandatory requirements that
   the profile supports but the resume does not show, critical style problems;
3. revise: switch to wording that passes, drop what cannot be fixed, restore supported evidence for a
   missing mandatory requirement.

It stops with `no_critical_issues`, `no_further_improvement` (nothing left to change) or `max_cycles`, and
keeps the best iteration: fewest critical issues, then highest integrity, then highest alignment. The loop
can only select and reword from the profile; it cannot add qualifications to raise a score.

## Determinism

No randomness and no model calls in any score. Each match report stores an `input_hash` (profile content,
analysed posting, weights, `SCORING_VERSION`), so re-running the same inputs gives the same numbers, and a
changed number always has a changed input behind it.

See [`examples/`](examples) for a full scoring report on a real profile.
