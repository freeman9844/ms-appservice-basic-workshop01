"""App Service 워크숍 데모 앱 (Flask).

- VERSION 상수는 슬롯/카나리 실습에서 sed로 치환된다 (v1 → v2).
"""
import os
import socket
import sys
import time
from datetime import datetime, timezone

# 프로세스 시작 시각 — 앱 설정 변경 재시작(04)·Auto-heal 재활용(11) 관찰용
STARTED_AT = datetime.now(timezone.utc).isoformat(timespec="seconds")

from flask import Flask, request, jsonify

app = Flask(__name__)

VERSION = "v1"
COLORS = {"v1": "#2563eb", "v2": "#16a34a"}  # v1=파랑, v2=초록


def _clamp(raw, cap):
    """쿼리 파라미터를 0–cap 정수로 강제(음수·비수치는 0)."""
    try:
        return max(0, min(int(raw), cap))
    except (TypeError, ValueError):
        return 0


def _apply_startup_delay(raw=None):
    """Apply an opt-in process startup delay for the scaling workshop."""
    value = os.environ.get("STARTUP_DELAY_SECONDS") if raw is None else raw
    delay = _clamp(value, 30)
    if delay:
        time.sleep(delay)
    return delay


_apply_startup_delay()


def _slot():
    # Linux App Service는 컨테이너에 WEBSITE_SLOT_NAME을 주입하지 않음(실측).
    # WEBSITE_HOSTNAME(슬롯별 호스트명)에서 슬롯 이름을 파싱해 보완한다.
    #   production: app-x.azurewebsites.net → site명과 동일
    #   staging:    app-x-staging.azurewebsites.net → site명 뒤에 -<slot>
    slot = os.environ.get("WEBSITE_SLOT_NAME")
    if slot:
        return slot
    host = os.environ.get("WEBSITE_HOSTNAME", "")
    site = os.environ.get("WEBSITE_SITE_NAME", "")
    prefix = f"{site}-"
    hostname = host.split(".")[0]
    if site and hostname.startswith(prefix):
        return hostname[len(prefix):]
    return "production"


def _info():
    return {
        "version": VERSION,
        "color": COLORS.get(VERSION, "#6b7280"),
        "slot": _slot(),
        "instance": os.environ.get("WEBSITE_INSTANCE_ID", socket.gethostname())[:8],
        "message": os.environ.get("WELCOME_MESSAGE", "App Service 워크숍에 오신 것을 환영합니다"),
        "started_at": STARTED_AT,
        "python": sys.version.split()[0],
    }


@app.get("/")
def home():
    i = _info()
    return (
        f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<title>App Service 워크숍 {i['version']}</title></head>
<body style="margin:0;display:flex;min-height:100vh;align-items:center;justify-content:center;
background:{i['color']};color:#fff;font-family:sans-serif;text-align:center">
<div>
  <h1 style="font-size:5rem;margin:0">{i['version']}</h1>
  <p style="font-size:1.5rem">{i['message']}</p>
  <p>slot: <b>{i['slot']}</b> · instance: <b>{i['instance']}</b></p>
</div></body></html>""",
        200,
        {"Content-Type": "text/html; charset=utf-8"},
    )


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/api/info")
def api_info():
    return jsonify(_info())


@app.get("/load")
def load():
    sec = _clamp(request.args.get("sec"), 20)
    end = time.monotonic() + sec
    while time.monotonic() < end:
        pass  # CPU 소모(busy loop)
    return jsonify(burned_sec=sec, instance=_info()["instance"])


@app.get("/slow")
def slow():
    sec = _clamp(request.args.get("sec", "5"), 10)
    time.sleep(sec)
    return jsonify(slept=sec, instance=_info()["instance"])


@app.get("/cache")
def cache():
    import redis  # Redis 연결 실패는 아래에서 unavailable 응답으로 처리

    host = os.environ.get("REDIS_HOST", "localhost")
    try:
        r = redis.Redis(host=host, port=6379, socket_connect_timeout=2)
        visits = r.incr("visits")
        return jsonify(cache="ok", visits=visits, redis_host=host)
    except redis.exceptions.RedisError:
        return jsonify(
            cache="unavailable",
            hint="Redis 사이드카가 없습니다. 모듈 10을 참고하세요.",
            redis_host=host,
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
