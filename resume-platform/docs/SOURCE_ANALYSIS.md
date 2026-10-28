# What the source documents require, and how the platform does it

Three documents were provided with the build brief:

- **A.** *The Recruiter Psychology Playbook* (ApplyRyt), six pages on how a recruiter skims a resume.
- **B.** A one-page resume template with a bullet formula.
- **C.** The candidate's master resume (kept out of this repository; only masked examples are committed).

Where the documents and the brief's priority order conflict, the order wins:
**truthful qualifications > job fit > readability > ATS parsing > cosmetic score.**

## A. Recruiter psychology

| Principle in the playbook | Implementation | Where |
|---|---|---|
| Recruiters read top left first and scan for the role they are hiring for | The posting's exact title goes on its own line under the name. Only work-arrangement suffixes such as "(Remote)" are trimmed; abbreviations are never substituted. | `tailor.py: clean_target_title`, PDF/DOCX header |
| The title line holds only the title | No skills or taglines on that line | renderers |
| "Only use a title you can back up" | Job Fit, gates and missing requirements are shown before you generate. The editor lets you change the title (`set_target_title`). | match report, resume editor |
| Summary formula: title + years + domain, top three skills, one number, what you bring | Three sentences: identity (title, degree, honest years phrasing such as "over a year"), "Skilled in X, Y and Z" using the posting's top evidenced skills, and one result with a number from your profile. The optional fourth part ("what you bring to this team") is left out: without real knowledge of the team it becomes generic filler, which the playbook itself says to cut. | `tailor.py: build_summary` |
| At least one number; numbers are proof | The result sentence uses a real metric from your profile (a short `summary`-tagged variant when one exists). QA flags a summary without a number. Numbers are never estimated. | `build_summary`, `qa.py` |
| Cut empty words ("passionate", "team player") | Filler and AI-sounding vocabulary are flagged by QA and removed by rule-based cleanup | `style.py`, `rewrite.py: rule_cleanup` |
| Skills in the posting's order of importance, in its words, unrelated ones removed | Skills are ranked by the posting's importance and grouped into at most five lines. The posting's spelling is used only when it names exactly the same skill (its "scikit-learn" for your "Scikit-Learn"); a broader or bundled term ("ETL/ELT" when only ETL is evidenced) is never borrowed. Unrelated skills are omitted with a recorded reason. | `tailor.py: build_skills` |
| Lead each role with the bullets that match | Bullets are ordered by relevance to the posting inside each role and project; chronology between roles is unchanged | `tailor.py: tailor` |
| Action verb first, result last, numbers | QA checks weak openers, missing outcomes, tense and length; wording variants put the method and the result in that order | `qa.py`, suggestion packs |
| Mirror the posting's language | Only through truthful synonyms and approved variants that pass the fact check | `rewrite.py: fact_check` |
| Structure: name + title, summary, skills, experience, education + certifications | Default order. Projects come after experience unless they are clearly more relevant to the posting than the professional experience (common for early-career candidates moving into a new field), in which case they come first. | `tailor.py` section order |
| The 60-second checklist | Automated: title match, summary length and number, skills wording and order, first bullets matching, results in bullets, irrelevant content removed, gates for "I genuinely fit" | QA codes `title_mismatch`, `summary_length`, `summary_without_number`, `missing_outcome`, ... |

## B. Template and bullet formula

| Template element | Implementation |
|---|---|
| Name, phone, email, LinkedIn; exact job title; 3–4 sentence summary | Header and summary as above |
| Skills as "Category: skill, skill, ..." lines, "only skills mentioned in the job and highly relevant skills" | Category lines in posting order. When fewer than about a dozen skills relate to the posting, up to five *evidenced* neighbouring skills (for an analyst posting: data modeling, data quality, ETL) are added after the related ones, never unrelated ones. |
| Experience: "Job Title, Company" with duration and location | Title, organisation, location and dates exactly as in the profile; locations and dates right-aligned |
| Bullet = action verb + what + how (skill) + measurable improvement, 15–25 words | QA aims for 15–25 words (warning above 35, note below 8). Wording variants follow the order verb → work → method → result. A bullet without a number is never given one: QA notes it and suggests adding the real figure to the profile. |
| Projects, education (with CGPA when present), certifications | Rendered in that style; academic projects are labelled by context and may not claim production use |

## C. The master resume

What the importer found, and what the platform does with it:

- **Format.** A Word-made, single-column resume in a Times-style serif with a centred name, bold section
  headings with rules, and right-aligned locations and dates. Generated PDFs mirror this look (Liberation
  Serif is metric-compatible with Times) so the output reads as the candidate's own document, not a
  generator's template. The DOCX output uses the same structure.
- **Content.** One professional role, three academic projects, two degrees, two certifications and about
  fifty listed skills. All are parsed into the evidence profile with their original text preserved.
- **Review issues raised (36 open after import, 3 critical):**
  - *critical*: an academic project described as "production-scale" and "enterprise". An academic
    project may not imply production use unless it served real users, so the tailored wording drops these
    words until the candidate confirms otherwise;
  - *warnings*: every percentage and count is unverified until the candidate confirms how it was
    measured (unverified numbers still count, at 75% credit);
  - *notes*: listed skills that no bullet demonstrates (they may stay listed, but only bullet evidence
    counts as "direct"), no city in the header, no GitHub or portfolio link, and unknown work
    authorisation (needed for sponsorship gates).
- **Wording.** Some original bullets are long or awkward ("Optimized ETL pipeline performance by real-time
  operational decision-making..."). The assistant-written suggestion pack
  (`examples/suggestion-packs/pavan-doma.yaml`) offers 16 clearer variants. Every one passes the fact
  check (no new numbers, tools, employers or claims), and every one stays pending until the candidate
  approves it.

## Making it read like a person wrote it

- No AI-tell vocabulary ("leveraged", "spearheaded", "seamless", "cutting-edge", "passionate") and no
  trailing "..., ensuring X" or "..., enabling Y" clauses; QA flags them and the cleanup removes them.
- Openers vary; the same keyword is not repeated more than five times.
- The summary states facts plainly instead of self-assessment ("results-driven", "proven track record").
- Honest experience phrasing ("over a year"), never rounded up.
- Layout follows the candidate's own document instead of a generic template, and pages are filled with real
  content: when space is left, the most relevant bullets and projects held in reserve go back in rather
  than padding.
