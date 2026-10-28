"""Reusable resume variants (target categories). These describe what each kind of role usually
emphasises; they are targeting aids, never evidence that the candidate qualifies."""

from __future__ import annotations

from app.core.taxonomy import get_taxonomy
from app.jobs.jd_parser import PARSER_VERSION, _rank_skills
from app.schemas.job import JobAnalysis, Requirement, SkillMention

PRESETS: dict[str, dict] = {
    "ai-engineer": {
        "title": "AI Engineer",
        "must": ["Python", "Large Language Models", "RAG", "Machine Learning", "AWS"],
        "nice": ["Prompt Engineering", "LLM Evaluation", "Vector Databases", "Docker", "FastAPI", "NLP", "SQL"],
        "duties": ["Build LLM applications and retrieval pipelines", "Evaluate model output quality",
                   "Deploy services in containers on AWS"],
    },
    "ml-engineer": {
        "title": "Machine Learning Engineer",
        "must": ["Machine Learning", "Python", "Scikit-learn", "Feature Engineering", "Model Evaluation"],
        "nice": ["PyTorch", "MLflow", "MLOps", "SQL", "Docker", "AWS", "NLP"],
        "duties": ["Train and evaluate machine learning models", "Track experiments and compare model approaches",
                   "Build data pipelines for model features"],
    },
    "genai-llm-engineer": {
        "title": "Generative AI Engineer",
        "must": ["Large Language Models", "Generative AI", "RAG", "Prompt Engineering", "Python"],
        "nice": ["Fine-tuning", "LLM Evaluation", "LangGraph", "Hugging Face", "Vector Databases", "Amazon Bedrock",
                 "Structured Outputs", "Context Engineering"],
        "duties": ["Build retrieval-augmented LLM applications", "Design prompts, context and output validation",
                   "Evaluate LLM responses"],
    },
    "rag-engineer": {
        "title": "RAG Engineer",
        "must": ["RAG", "Vector Databases", "Python", "Large Language Models", "Information Retrieval"],
        "nice": ["Embeddings", "LLM Evaluation", "Context Engineering", "LangGraph", "AWS", "Docker", "Monitoring"],
        "duties": ["Build retrieval pipelines over documents", "Measure retrieval relevance and answer quality",
                   "Deploy and monitor RAG services"],
    },
    "data-engineer": {
        "title": "Data Engineer",
        "must": ["SQL", "Python", "ETL", "Data Pipelines", "Data Modeling"],
        "nice": ["Data Quality", "Window Functions", "Query Optimization", "AWS", "Docker", "Apache Airflow",
                 "Technical Documentation"],
        "duties": ["Build and maintain ETL pipelines", "Design database schemas", "Implement data quality checks",
                   "Optimize SQL queries"],
    },
    "ml-data-engineer": {
        "title": "ML Data Engineer",
        "must": ["Python", "SQL", "Data Pipelines", "ETL", "Machine Learning"],
        "nice": ["Feature Engineering", "MLflow", "Data Quality", "Data Modeling", "AWS", "Docker"],
        "duties": ["Build data pipelines that feed machine learning models", "Ensure data quality for training data",
                   "Track experiments"],
    },
    "data-analyst": {
        "title": "Data Analyst",
        "must": ["SQL", "Data Analysis", "Dashboards", "KPI Reporting"],
        "nice": ["Python", "Pandas", "Statistics", "Excel", "Tableau", "Power BI", "Data Visualization"],
        "duties": ["Build dashboards that track KPIs", "Write SQL to analyze operational data",
                   "Present findings to stakeholders"],
    },
    "business-analyst": {
        "title": "Business Analyst",
        "must": ["Requirements Gathering", "Stakeholder Management", "SQL", "Data Analysis"],
        "nice": ["KPI Reporting", "Process Improvement", "Technical Documentation", "Excel", "Dashboards"],
        "duties": ["Gather and document business requirements", "Analyze processes and data",
                   "Work with stakeholders to validate business logic"],
    },
    "bi-analyst": {
        "title": "Business Intelligence Analyst",
        "must": ["Business Intelligence", "SQL", "Dashboards", "KPI Reporting"],
        "nice": ["Data Modeling", "Power BI", "Tableau", "Data Visualization", "Excel", "Window Functions"],
        "duties": ["Build BI dashboards and reports", "Model data for reporting", "Define KPIs with stakeholders"],
    },
    "bi-developer": {
        "title": "Business Intelligence Developer",
        "must": ["SQL", "Data Modeling", "ETL", "Dashboards"],
        "nice": ["Power BI", "Query Optimization", "Data Warehousing", "Window Functions", "Data Quality"],
        "duties": ["Develop ETL and reporting data models", "Build dashboards", "Tune reporting queries"],
    },
    "tech-ops-analyst": {
        "title": "Technical Operations Analyst",
        "must": ["SQL", "Operations Analytics", "Process Improvement", "Technical Documentation"],
        "nice": ["Troubleshooting", "Data Quality", "Monitoring", "KPI Reporting", "Inventory Management"],
        "duties": ["Analyze operational data and processes", "Document procedures and runbooks",
                   "Monitor systems and resolve data issues"],
    },
    "marketing-analytics": {
        "title": "Marketing Analytics Analyst",
        "must": ["SQL", "Data Analysis", "Campaign Analytics", "Customer Segmentation"],
        "nice": ["Python", "Statistics", "A/B Testing", "Dashboards", "Data Visualization", "Google Analytics",
                 "Marketing Attribution"],
        "duties": ["Analyze campaign performance", "Segment customers", "Build dashboards for marketing teams"],
    },
}


def preset_job(key: str) -> JobAnalysis:
    """Build a pseudo job analysis for a variant so the normal tailoring pipeline can run."""
    preset = PRESETS[key]
    tax = get_taxonomy()
    reqs: list[Requirement] = []
    n = 0
    for cat, names in (("mandatory", preset["must"]), ("preferred", preset["nice"])):
        for i, name in enumerate(names):
            n += 1
            reqs.append(Requirement(
                id=f"V{n}", text=f"{name}", category=cat, category_basis="inferred", kind="skill",
                skills=[SkillMention(canonical=name, as_written=name, category=tax.category(name))],
                importance=round((1.0 if cat == "mandatory" else 0.5) * max(0.6, 1 - 0.04 * i), 3),
            ))
    for i, duty in enumerate(preset["duties"]):
        n += 1
        hits = tax.find(duty)
        reqs.append(Requirement(
            id=f"V{n}", text=duty, category="responsibility", category_basis="inferred", kind="responsibility",
            skills=[SkillMention(canonical=h.canonical, as_written=h.as_written, category=tax.category(h.canonical)) for h in hits],
            importance=round(0.6 * max(0.6, 1 - 0.04 * i), 3),
        ))
    title_skills = set(tax.find_canonical(preset["title"]))
    return JobAnalysis(title=preset["title"], title_basis="user", requirements=reqs,
                       skill_importance=_rank_skills(reqs, title_skills), extraction_method="preset",
                       parser_version=PARSER_VERSION)


def list_presets() -> list[dict]:
    return [{"key": k, "title": v["title"], "focus": v["must"]} for k, v in PRESETS.items()]
