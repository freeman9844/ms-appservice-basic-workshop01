from datetime import datetime, timezone
import json

from scripts import observe_instances as oi


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


class _FakeFuture:
    def __init__(self, value):
        self._value = value

    def result(self):
        return self._value


class _FakeExecutor:
    def __init__(self, max_workers):
        self.max_workers = max_workers
        self.submitted = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def submit(self, fn, url, timeout):
        self.submitted.append((url, timeout))
        return _FakeFuture(fn(url, timeout))


def test_observe_stops_when_deadline_is_reached(monkeypatch):
    executor = _FakeExecutor(max_workers=2)
    submitted_payloads = iter(
        [
            {"instance": "worker02", "started_at": "2026-07-21T02:00:00Z"},
            {"instance": "worker03", "started_at": "2026-07-21T02:00:00Z"},
        ]
    )
    monotonic_values = iter([0.0, 0.0, 0.0, 1.1, 1.2, 1.3, 1.4])
    sleep_calls = []

    monkeypatch.setattr(oi, "ThreadPoolExecutor", lambda max_workers: executor)
    monkeypatch.setattr(oi, "as_completed", lambda futures: list(futures))
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

    observations = oi.observe("http://example.invalid/api/info", "baseline", 1, 2, 5)

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
    assert sleep_calls == [0]
