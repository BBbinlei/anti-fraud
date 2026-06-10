from pathlib import Path

from fastapi.testclient import TestClient

from config import FRONTEND_ASSETS_DIR, FRONTEND_DIR
from main import app


def _read_frontend_file(filename: str) -> str:
    return (FRONTEND_DIR / filename).read_text(encoding="utf-8")


def test_frontend_pages_are_served_by_fastapi():
    with TestClient(app) as client:
        index = client.get("/")
        theater = client.get("/theater.html")
        review = client.get("/review.html")
        report = client.get("/report.html")
        profile = client.get("/profile.html")
        api_js = client.get("/assets/api.js")

    assert index.status_code == 200
    assert theater.status_code == 200
    assert review.status_code == 200
    assert report.status_code == 200
    assert profile.status_code == 200
    assert api_js.status_code == 200
    assert "金融反诈剧场" in index.text
    assert "getTheaterTemplates" in index.text
    assert "/theater.html?scam_id=" in index.text
    assert "sendTheaterMessage" in theater.text
    assert "getReviewReport" in review.text
    assert "reviewCardTitle" in review.text
    assert "reviewCardContent" in review.text
    assert "completeScenario" in review.text
    assert "submitReport" in report.text
    assert "getUserProgress" in profile.text


def test_frontend_requests_go_through_shared_api_client():
    api_js = (FRONTEND_ASSETS_DIR / "api.js").read_text(encoding="utf-8")
    index_html = _read_frontend_file("index.html")
    theater_html = _read_frontend_file("theater.html")
    review_html = _read_frontend_file("review.html")
    report_html = _read_frontend_file("report.html")
    profile_html = _read_frontend_file("profile.html")

    assert "fetch(" in api_js
    assert "apiPost(" in api_js
    assert "apiGet(" in api_js
    assert "getTheaterTemplates(" in api_js
    assert "sendTheaterMessage(" in api_js
    assert "getReviewReport(" in api_js
    assert "fetch(" not in index_html
    assert "fetch(" not in theater_html
    assert "fetch(" not in review_html
    assert "fetch(" not in report_html
    assert "fetch(" not in profile_html
    assert "getTheaterTemplates(" in index_html
    assert "template.scam_name" in index_html
    assert "template.target" in index_html
    assert "template.red_flags" in index_html
    assert "template.prevention" in index_html
    assert "sendTheaterMessage(" in theater_html
    assert "template.scam_name" in theater_html
    assert "template.target" in theater_html
    assert "lastUserMessage" in theater_html
    assert "content: lastUserMessage" in theater_html
    assert "getReviewReport(" in review_html
    assert "report.review_title" in review_html
    assert "report.review_content" in review_html
    assert "completeScenario(" in review_html
    assert "session_id: sessionId" in review_html
    assert "submitReport(" in report_html
    assert "applyPrefill()" in report_html
    assert 'params.get("session_id")' in report_html
    assert 'params.get("risk_level")' in report_html
    assert 'params.get("content")' in report_html
    assert "getUserProgress(" in profile_html
    assert "completeScenario(" in profile_html


def test_frontend_has_no_ai_key_or_direct_ai_endpoint_references():
    frontend_files = [
        path
        for path in Path(FRONTEND_DIR).rglob("*")
        if path.is_file() and path.suffix in {".html", ".js", ".css"}
    ]

    assert frontend_files
    for path in frontend_files:
        content = path.read_text(encoding="utf-8")
        lowered = content.lower()
        assert "deepseek" not in lowered
        assert "api_key" not in lowered
        assert "anthropic" not in lowered
        assert "sk-" not in lowered


def test_frontend_contains_expected_static_assets():
    assert (FRONTEND_DIR / "index.html").exists()
    assert (FRONTEND_DIR / "theater.html").exists()
    assert (FRONTEND_DIR / "review.html").exists()
    assert (FRONTEND_DIR / "report.html").exists()
    assert (FRONTEND_DIR / "profile.html").exists()
    assert (FRONTEND_ASSETS_DIR / "api.js").exists()
    assert (FRONTEND_ASSETS_DIR / "style.css").exists()
