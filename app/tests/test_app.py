import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app as app_module


def client():
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_health_returns_ok():
    r = client().get("/health")
    assert r.status_code == 200
    assert r.get_json() == {"status": "ok"}


def test_home_renders_html_with_version():
    r = client().get("/")
    assert r.status_code == 200
    assert "text/html" in r.content_type
    body = r.get_data(as_text=True)
    assert "v1" in body
    assert "#2563eb" in body  # v1 = 파랑


def test_api_info_fields():
    r = client().get("/api/info")
    data = r.get_json()
    assert data["version"] == "v1"
    assert data["slot"] == "production"  # 로컬: WEBSITE_SLOT_NAME 미설정 기본값
    for key in ("color", "instance", "message", "started_at", "python"):
        assert key in data


def test_clamp_caps_value():
    assert app_module._clamp("999", 10) == 10
    assert app_module._clamp("3", 10) == 3
    assert app_module._clamp("abc", 10) == 0
    assert app_module._clamp(None, 10) == 0


def test_slow_returns_slept_seconds():
    r = client().get("/slow?sec=0")
    assert r.status_code == 200
    assert r.get_json()["slept"] == 0


def test_load_returns_burned_seconds():
    r = client().get("/load?sec=0")
    assert r.status_code == 200
    assert r.get_json()["burned_sec"] == 0


def test_cache_degrades_without_redis():
    r = client().get("/cache")
    assert r.status_code == 200
    assert r.get_json()["cache"] == "unavailable"
