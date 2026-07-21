import json
import multiprocessing
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from scripts import observe_instances as oi


ROOT = Path(__file__).resolve().parents[2]
HEADER = "trial\tinstance\tstarted_at\tfirst_seen_at\tfirst_response_age"
SCRIPT_HEADER = "printf 'trial\\tinstance\\tstarted_at\\tfirst_seen_at\\tfirst_response_age\\n'"
DISCLAIMER = "[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다."


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_parse_sample_calculates_first_response_age():
    sample = oi.parse_sample(
        {"instance": "worker02", "started_at": "2026-07-21T02:00:00+00:00"},
        utc("2026-07-21T02:00:27Z"),
    )

    assert sample == {
        "instance": "worker02",
        "started_at": "2026-07-21T02:00:00Z",
        "first_seen_at": "2026-07-21T02:00:27Z",
        "first_response_age": 27,
    }


def test_parse_sample_rejects_invalid_payloads():
    observed = utc("2026-07-21T02:00:27Z")

    assert oi.parse_sample({}, observed) is None
    assert oi.parse_sample({"instance": "", "started_at": "2026-07-21T02:00:00Z"}, observed) is None
    assert oi.parse_sample({"instance": " \t", "started_at": "2026-07-21T02:00:00Z"}, observed) is None
    assert oi.parse_sample({"instance": None, "started_at": "2026-07-21T02:00:00Z"}, observed) is None
    assert oi.parse_sample({"instance": "worker02", "started_at": "not-a-time"}, observed) is None


def test_store_ignores_baseline_and_duplicate_instances():
    store = oi.ObservationStore("worker01")
    first = {
        "instance": "worker02",
        "started_at": "2026-07-21T02:00:00Z",
        "first_seen_at": "2026-07-21T02:00:27Z",
        "first_response_age": 27,
    }

    assert store.add({**first, "instance": "worker01"}) is False
    assert store.add(first) is True
    assert store.add({**first, "first_seen_at": "2026-07-21T02:00:40Z"}) is False
    assert store.values() == [first]


class _FakeResponse:
    def __init__(self, *, status=200, body=b"", read_error=None):
        self.status = status
        self.body = body
        self.read_error = read_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        if self.read_error is not None:
            raise self.read_error
        return self.body


def test_fetch_ignores_invalid_http_body(monkeypatch):
    responses = iter(
        [
            _FakeResponse(body=b"\xff"),
            _FakeResponse(read_error=OSError("boom")),
        ]
    )
    monkeypatch.setattr(oi, "urlopen", lambda url, timeout: next(responses))

    assert oi.fetch("http://example.invalid", 1) is None
    assert oi.fetch("http://example.invalid", 1) is None


def test_main_returns_0_1_and_2(monkeypatch, tmp_path, capsys):
    output = tmp_path / "observations.json"
    observed = {
        "instance": "worker02",
        "started_at": "2026-07-21T02:00:00Z",
        "first_seen_at": "2026-07-21T02:00:27Z",
        "first_response_age": 27,
    }

    monkeypatch.setattr(oi, "observe", lambda *args, **kwargs: [observed])
    assert (
        oi.main(
            [
                "--url",
                "http://example.invalid/api/info",
                "--baseline-instance",
                "worker01",
                "--duration",
                "1",
                "--concurrency",
                "1",
                "--request-timeout",
                "1",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert json.loads(output.read_text(encoding="utf-8")) == [observed]

    monkeypatch.setattr(oi, "observe", lambda *args, **kwargs: [])
    assert (
        oi.main(
            [
                "--url",
                "http://example.invalid/api/info",
                "--baseline-instance",
                "worker01",
                "--duration",
                "1",
                "--concurrency",
                "1",
                "--request-timeout",
                "1",
                "--output",
                str(output),
            ]
        )
        == 2
    )

    def fail_observe(*args, **kwargs):
        raise AssertionError("observe should not run for invalid arguments")

    monkeypatch.setattr(oi, "observe", fail_observe)
    assert (
        oi.main(
            [
                "--url",
                "http://example.invalid/api/info",
                "--baseline-instance",
                "worker01",
                "--duration",
                "0",
                "--concurrency",
                "1",
                "--request-timeout",
                "1",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert "must be positive" in capsys.readouterr().err
    assert (
        oi.main(
            [
                "--url",
                "http://example.invalid/api/info",
                "--baseline-instance",
                " \t",
                "--duration",
                "1",
                "--concurrency",
                "1",
                "--request-timeout",
                "1",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert "baseline-instance must not be empty or whitespace" in capsys.readouterr().err

    rehearsal = (ROOT / "scripts/rehearsal.sh").read_text(encoding="utf-8")
    docs = (ROOT / "docs/07-autoscale.md").read_text(encoding="utf-8")

    assert SCRIPT_HEADER in rehearsal
    assert f'echo "{DISCLAIMER}"' in rehearsal
    assert HEADER in docs
    assert DISCLAIMER in docs

    assert (
        'echo "[07] ${label}에서 새 instance를 관찰하지 못했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 시도했습니다. 부하를 다시 걸어 3단계부터 재실행하세요." >&2\n      return 1'
        in rehearsal
    )
    assert "trial_exit=$?" not in rehearsal


class _FakeFuture:
    def __init__(self, value):
        self._value = value

    def result(self, timeout=None):
        return self._value

    def cancel(self):
        return False


class _FakeExecutor:
    def __init__(self, max_workers):
        self.max_workers = max_workers
        self.submitted = []

    def submit(self, fn, url, timeout):
        self.submitted.append((url, timeout))
        return _FakeFuture(fn(url, timeout))

    def shutdown(self, wait=True, cancel_futures=False):
        self.shutdown_args = (wait, cancel_futures)


def test_observe_stops_when_deadline_is_reached(monkeypatch):
    executor = _FakeExecutor(max_workers=2)
    submitted_payloads = iter(
        [
            {"instance": "worker02", "started_at": "2026-07-21T02:00:00Z"},
            {"instance": "worker03", "started_at": "2026-07-21T02:00:00Z"},
        ]
    )
    monotonic_values = iter([0.0, 0.0, 0.0, 0.1, 1.1, 1.2, 1.3])
    sleep_calls = []

    monkeypatch.setattr(oi, "ThreadPoolExecutor", lambda max_workers: executor)
    monkeypatch.setattr(oi, "as_completed", lambda futures, timeout=None: list(futures))
    monkeypatch.setattr(oi.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(oi.time, "sleep", lambda value: sleep_calls.append(value))
    monkeypatch.setattr(
        oi,
        "fetch",
        lambda url, timeout: next(submitted_payloads),
    )
    monkeypatch.setattr(
        oi,
        "parse_sample",
        lambda payload, observed_at: {
            "instance": payload["instance"],
            "started_at": payload["started_at"],
            "first_seen_at": "2026-07-21T02:00:27Z",
            "first_response_age": 27,
        },
    )

    observations = oi._observe_threaded("http://example.invalid/api/info", "baseline", 1, 2, 5)

    assert observations == [
        {
            "instance": "worker02",
            "started_at": "2026-07-21T02:00:00Z",
            "first_seen_at": "2026-07-21T02:00:27Z",
            "first_response_age": 27,
        }
    ]
    assert executor.max_workers == 2
    assert executor.submitted == [
        ("http://example.invalid/api/info", 1),
        ("http://example.invalid/api/info", 1),
    ]
    assert sleep_calls == []
    assert executor.shutdown_args == (False, True)


def test_fetch_ignores_transport_oserror(monkeypatch):
    def fail(*args, **kwargs):
        raise ConnectionResetError("connection reset")

    monkeypatch.setattr(oi, "urlopen", fail)

    assert oi.fetch("http://example.invalid", 1) is None


class _BlockedFuture:
    def __init__(self):
        self.cancelled = False

    def result(self, timeout=None):
        raise TimeoutError

    def cancel(self):
        self.cancelled = True
        return True


class _BlockedExecutor:
    def __init__(self, max_workers):
        self.future = _BlockedFuture()
        self.shutdown_args = None

    def submit(self, fn, url, timeout):
        return self.future

    def shutdown(self, wait=True, cancel_futures=False):
        self.shutdown_args = (wait, cancel_futures)


def test_observe_cancels_blocked_futures_without_waiting(monkeypatch):
    executor = _BlockedExecutor(max_workers=1)
    clock = iter([0.0, 0.0, 0.0, 2.0, 2.0])

    monkeypatch.setattr(oi, "ThreadPoolExecutor", lambda max_workers: executor)
    monkeypatch.setattr(oi, "as_completed", lambda futures, timeout=None: (_ for _ in ()).throw(TimeoutError))
    monkeypatch.setattr(oi.time, "monotonic", lambda: next(clock))

    assert oi._observe_threaded("http://example.invalid", "baseline", 1, 1, 5) == []
    assert executor.future.cancelled is True
    assert executor.shutdown_args == (False, True)


class _BlockedLoopbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.server.request_started.set()
        try:
            self.wfile.write(b"{")
            self.wfile.flush()
            while not self.server.release.wait(0.01):
                self.wfile.write(b" ")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, format, *args):
        return


class _DaemonThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False


def test_observe_hard_deadline_reaps_blocked_child_and_worker():
    server = _DaemonThreadingHTTPServer(("127.0.0.1", 0), _BlockedLoopbackHandler)
    server.request_started = threading.Event()
    server.release = threading.Event()
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    started_at = time.monotonic()
    try:
        with pytest.raises(oi.ObservationExecutionError, match="hard deadline"):
            oi.observe(
                f"http://127.0.0.1:{server.server_port}/blocked",
                "baseline",
                0.25,
                1,
                30,
            )
        assert server.request_started.is_set()
    finally:
        server.release.set()
        server.shutdown()
        server.server_close()
        server_thread.join(1)

    elapsed = time.monotonic() - started_at
    assert elapsed < 2
    assert not server_thread.is_alive()
    assert not any(process.is_alive() for process in multiprocessing.active_children())
