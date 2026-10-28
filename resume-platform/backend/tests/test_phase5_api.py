"""Phase 5: REST API integration (the full user workflow) plus security behaviour of the HTTP layer."""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.config import reset_settings_cache
from app.db import reset_engine
from tests.conftest import job_text


@pytest.fixture
def client():
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def seeded(client, synthetic_pdf):
    r = client.post("/api/profile/import", files={"file": ("cv.pdf", synthetic_pdf, "application/pdf")})
    assert r.status_code == 200, r.text
    return client, r.json()


def test_full_workflow(seeded):
    client, prof = seeded
    data = prof["profile"]
    assert data["personal"]["name"] == "Jordan Avery Lee"
    assert prof["revision"]["number"] == 1
    ach = data["roles"][0]["achievements"][0]

    # Step 2: verify / correct claims; every change is a new revision with an audit event.
    r = client.patch(f"/api/profile/items/{ach['id']}", json={"patch": {"verification": "verified"}})
    assert r.json()["revision"]["number"] == 2
    corrected = "Built weekly loan performance dashboards in Tableau using SQL views, saving 6 hours of manual reporting each week."
    r = client.patch(f"/api/profile/items/{ach['id']}", json={"patch": {"text": corrected}})
    after = r.json()["profile"]["roles"][0]["achievements"][0]
    assert after["text"] == corrected and after["original_text"] == ach["original_text"]
    assert after["verification"] == "user_corrected"
    assert client.patch(f"/api/profile/items/{ach['id']}", json={"patch": {"organization": "X"}}).status_code == 400
    revs = client.get("/api/profile/revisions").json()
    assert len(revs) == 3
    first = client.get(f"/api/profile/revisions/{revs[-1]['id']}").json()
    assert first["profile"]["roles"][0]["achievements"][0]["text"] == ach["original_text"]  # history recoverable
    assert any(e["action"] == "updated" for e in client.get("/api/audit").json())

    # Wording variant: fabricated wording is stored but cannot be approved.
    bad = client.post(f"/api/profile/achievements/{ach['id']}/variants",
                      json={"text": "Led a team of 9 analysts building Power BI dashboards for 400 users."}).json()["variant"]
    assert bad["fact_check"]["passed"] is False and bad["approved"] is False
    r = client.post(f"/api/profile/achievements/{ach['id']}/variants/{bad['id']}/approval", json={"approved": True})
    assert r.status_code == 400

    # Step 3-4: job intake, duplicate detection, deterministic match.
    j = client.post("/api/jobs", json={"text": job_text("data_analyst"), "url": "https://jobs.example.com/da?utm_source=x"}).json()
    dup = client.post("/api/jobs", json={"text": job_text("data_analyst"), "url": "https://jobs.example.com/da"}).json()
    assert dup["duplicate"] is True and dup["id"] == j["id"]
    m1 = client.post(f"/api/jobs/{j['id']}/match").json()["report"]
    m2 = client.post(f"/api/jobs/{j['id']}/match").json()["report"]
    assert m1["job_fit"]["total"] == m2["job_fit"]["total"] and m1["input_hash"] == m2["input_hash"]

    # Step 5-7: generate, validate, revise.
    v = client.post("/api/resumes", json={"job_id": j["id"]}).json()
    kinds = {f["kind"] for f in v["files"]}
    assert {"pdf", "docx", "json", "match_report", "missing_skills", "change_log", "evidence_report",
            "evaluation_report"} <= kinds
    assert v["summary_scores"]["evidence_integrity"] == 100.0
    assert v["content"]["header"]["target_title"] == "Data Analyst"
    assert any(e["adapter"] == "external-matcher" and e["status"] == "unavailable" for e in v["validation"]["external"])
    pdf = client.get(next(f["url"] for f in v["files"] if f["kind"] == "pdf"))
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"/api/resumes/{v['id']}/preview.png").headers["content-type"] == "image/png"
    cmp = client.get(f"/api/resumes/{v['id']}/comparison").json()
    assert cmp["bullets"] and cmp["original_text"]

    # Step 8: editing creates a new version; an unsupported edit blocks approval.
    bullet = v["content"]["experience"][0]["bullets"][0]
    bad_v = client.post(f"/api/resumes/{v['id']}/edits", json={"ops": [
        {"op": "set_bullet_text", "bullet_id": bullet["id"], "text": "Managed a $3M budget for Google with Kubernetes."}]}).json()
    assert bad_v["version_no"] == 2 and bad_v["summary_scores"]["evidence_integrity"] < 100
    assert client.post(f"/api/resumes/{bad_v['id']}/approve").status_code == 400
    approved = client.post(f"/api/resumes/{v['id']}/approve").json()
    assert approved["status"] == "approved"
    assert not any(c["requires_approval"] for c in approved["change_log"])

    # Step 9-10: export and record the application with the exact version sent.
    z = client.get(f"/api/resumes/{v['id']}/export.zip")
    names = zipfile.ZipFile(io.BytesIO(z.content)).namelist()
    assert any(n.endswith(".pdf") for n in names) and any(n.endswith(".docx") for n in names)
    app_ = client.put(f"/api/applications/{j['id']}", json={"status": "applied", "resume_version_id": v["id"]}).json()
    assert app_["status"] == "applied" and app_["applied_at"]
    row = client.get("/api/applications").json()[0]
    assert row["submitted_version_id"] == v["id"]
    # The exact submitted version is still retrievable after newer versions exist.
    assert client.get(f"/api/resumes/{v['id']}").json()["status"] == "approved"


def test_variant_resume_and_status(seeded):
    client, _ = seeded
    v = client.post("/api/resumes", json={"variant": "data-analyst"}).json()
    assert v["variant"] == "data-analyst" and v["content"]["header"]["target_title"] == "Data Analyst"
    status = client.get("/api/system/status").json()
    assert status["llm"]["provider"] == "none" and status["counts"]["resume_versions"] == 1
    assert len(client.get("/api/variants").json()) == 12


def test_malformed_uploads_rejected(client):
    for name, content in (("cv.pdf", b"%PDF-1.4 broken"), ("cv.exe", b"MZ"), ("cv.docx", b"PK\x03\x04junk"),
                          ("cv.txt", b"\x00\x01binary")):
        r = client.post("/api/profile/import", files={"file": (name, content, "application/octet-stream")})
        assert r.status_code == 400, (name, r.text)
    assert client.get("/api/profile").status_code == 404


def test_scanned_pdf_without_text_is_explained(client):
    import pymupdf

    doc = pymupdf.open()
    doc.new_page()
    r = client.post("/api/profile/import", files={"file": ("scan.pdf", doc.tobytes(), "application/pdf")})
    assert r.status_code == 400 and "No text" in r.json()["detail"]


def test_job_validation_and_ssrf(seeded):
    client, _ = seeded
    assert client.post("/api/jobs", json={}).status_code == 422
    assert client.post("/api/jobs", json={"text": "too short"}).status_code == 400
    r = client.post("/api/jobs", json={"url": "http://127.0.0.1:8000/api/health"})
    assert r.status_code in (400, 422) and "private" in r.json()["detail"].lower()


def test_job_with_injection_reports_it(seeded):
    client, _ = seeded
    j = client.post("/api/jobs", json={"text": job_text("injection_job")}).json()
    assert len(j["analysis"]["injection_warnings"]) == 2
    report = client.post(f"/api/jobs/{j['id']}/match").json()["report"]
    assert report["job_fit"]["total"] < 100


def test_api_token(monkeypatch, synthetic_pdf):
    monkeypatch.setenv("RIP_API_TOKEN", "s3cret-token-value")
    reset_settings_cache()
    reset_engine()
    from app.main import create_app

    with TestClient(create_app()) as c:
        assert c.get("/api/health").status_code == 200
        assert c.get("/api/system/status").status_code == 401
        assert c.get("/api/system/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
        assert c.get("/api/system/status", headers={"Authorization": "Bearer s3cret-token-value"}).status_code == 200


def test_delete_and_purge(seeded):
    client, _ = seeded
    j = client.post("/api/jobs", json={"text": job_text("ml_engineer")}).json()
    v = client.post("/api/resumes", json={"job_id": j["id"]}).json()
    assert client.delete(f"/api/jobs/{j['id']}").json()["deleted"]
    assert client.get(f"/api/resumes/{v['id']}").status_code == 404
    assert client.post("/api/system/purge", json={"confirm": "yes"}).status_code == 400
    assert client.post("/api/system/purge", json={"confirm": "DELETE ALL MY DATA"}).json()["deleted"]
    assert client.get("/api/profile").status_code == 404


def test_agent_import(seeded):
    client, _ = seeded
    body = {"postings": [{"title": "Data Analyst", "company": "Maplecrest Health Partners", "url": "https://x.example/1",
                          "description": job_text("data_analyst")},
                         {"title": "Data Analyst", "company": "Maplecrest Health Partners", "url": "https://x.example/1",
                          "description": job_text("data_analyst")}]}
    out = client.post("/api/agent/jobs/import", json=body).json()["imported"]
    assert out[0]["duplicate"] is False and out[1]["duplicate"] is True
    summary = client.get("/api/agent/summary").json()
    assert summary["profile"]["name"] == "Jordan Avery Lee" and len(summary["pipeline"]) == 1
