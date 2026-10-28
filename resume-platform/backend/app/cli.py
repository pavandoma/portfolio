"""Command-line interface.

    python -m app.cli import-resume ../data/inputs/master_resume.pdf
    python -m app.cli apply-suggestions ../examples/suggestion-packs/pavan-doma.yaml
    python -m app.cli analyze-job --file posting.txt
    python -m app.cli generate --job <job_id> --out ./out
    python -m app.cli samples --out ../data/samples
    python -m app.cli serve
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml

from app.config import get_settings
from app.core.security import validate_upload
from app.db import init_db, session_scope
from app.services.storage import resolve_stored


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_import(args) -> None:
    from app.services import profiles

    path = Path(args.path)
    with session_scope() as s:
        upload = validate_upload(path.name, path.read_bytes(), get_settings())
        _p, rev, data, doc = profiles.import_resume(s, get_settings(), upload)
        _print({"revision": rev.revision_no, "name": data.personal.name, "roles": len(data.roles),
                "projects": len(data.projects), "skills": len(data.skills),
                "open_issues": sum(1 for i in data.issues if i.status == "open"),
                "completeness": profiles.completeness(data)})


def cmd_suggestions(args) -> None:
    from app.services import profiles

    pack = yaml.safe_load(Path(args.path).read_text(encoding="utf-8"))
    with session_scope() as s:
        rev, _data, results = profiles.apply_suggestion_pack(s, pack)
        _print({"revision": rev.revision_no, "passed": sum(1 for r in results if r.get("passed")),
                "failed": [r for r in results if r.get("passed") is False],
                "unmatched": [r["match"] for r in results if r.get("status") == "no_matching_achievement"]})


def cmd_analyze(args) -> None:
    from app.ingest.url_fetch import fetch_job
    from app.services import jobs

    text, title, company = "", args.title, args.company
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif args.url:
        f = fetch_job(args.url, get_settings())
        text, title, company = f.text, title or f.title, company or f.company
    with session_scope() as s:
        job, dup = jobs.create_job(s, text, url=args.url, title=title, company=company)
        _rec, report = jobs.run_match(s, job.id)
        _print({"job_id": job.id, "duplicate": dup, "title": job.title, "company": job.company,
                "job_fit": report.job_fit.total, "missing_mandatory": report.missing_mandatory,
                "gates": [(g.gate, g.status) for g in report.gates]})


def _copy_files(version, out: Path) -> list[str]:
    out.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in version.files:
        dest = out / f.filename
        shutil.copyfile(resolve_stored(get_settings(), f.path), dest)
        copied.append(str(dest))
    return copied


def cmd_generate(args) -> None:
    from app.services import resumes

    with session_scope() as s:
        v = resumes.generate(s, get_settings(), job_id=args.job, variant=args.variant)
        files = _copy_files(v, Path(args.out)) if args.out else [f.path for f in v.files]
        sc = v.scores
        _print({"resume_version_id": v.id, "job_fit": sc["job_fit"]["total"],
                "resume_alignment": sc["resume_alignment"]["total"], "ats_parsing": sc["ats_parsing"],
                "evidence_integrity": sc["evidence_integrity"], "qa": sc["qa"], "files": files})


def cmd_samples(args) -> None:
    """Analyse the four synthetic test postings and generate a resume for each (sample outputs)."""
    from app.services import jobs, resumes

    fixtures = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "jobs"
    out = Path(args.out)
    summary = []
    for name in ("ai_engineer", "ml_engineer", "data_engineer", "data_analyst"):
        with session_scope() as s:
            job, _dup = jobs.create_job(s, (fixtures / f"{name}.txt").read_text(encoding="utf-8"))
            v = resumes.generate(s, get_settings(), job_id=job.id)
            _copy_files(v, out / name)
            sc = v.scores
            summary.append({"posting": name, "title": job.title, "job_fit": sc["job_fit"]["total"],
                            "resume_alignment": sc["resume_alignment"]["total"], "ats_parsing": sc["ats_parsing"],
                            "evidence_integrity": sc["evidence_integrity"], "qa": sc["qa"],
                            "critical_issues": sc["critical_issues"], "cycles": len(sc["iterations"])})
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    _print(summary)


def cmd_serve(args) -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=False)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="resume-platform")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init-db").set_defaults(fn=lambda a: (init_db(), print("ok")))
    x = sub.add_parser("import-resume")
    x.add_argument("path")
    x.set_defaults(fn=cmd_import)
    x = sub.add_parser("apply-suggestions")
    x.add_argument("path")
    x.set_defaults(fn=cmd_suggestions)
    x = sub.add_parser("analyze-job")
    g = x.add_mutually_exclusive_group(required=True)
    g.add_argument("--file")
    g.add_argument("--url")
    x.add_argument("--title")
    x.add_argument("--company")
    x.set_defaults(fn=cmd_analyze)
    x = sub.add_parser("generate")
    g = x.add_mutually_exclusive_group(required=True)
    g.add_argument("--job")
    g.add_argument("--variant")
    x.add_argument("--out")
    x.set_defaults(fn=cmd_generate)
    x = sub.add_parser("samples")
    x.add_argument("--out", required=True)
    x.set_defaults(fn=cmd_samples)
    x = sub.add_parser("serve")
    x.add_argument("--host", default="127.0.0.1")
    x.add_argument("--port", type=int, default=8000)
    x.set_defaults(fn=cmd_serve)
    sub.add_parser("mcp").set_defaults(fn=lambda a: __import__("app.mcp_server", fromlist=["main"]).main())
    args = p.parse_args(argv)
    get_settings().ensure_dirs()
    init_db()
    args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
