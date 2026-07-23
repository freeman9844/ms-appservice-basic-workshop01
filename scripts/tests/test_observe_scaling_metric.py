import json
from datetime import datetime, timezone

from scripts import observe_scaling_metric as osm


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def metric_payload(*rows):
    return {
        "value": [
            {
                "timeseries": [
                    {
                        "data": list(rows),
                    }
                ]
            }
        ]
    }


def test_parse_metric_samples_accepts_valid_rows_and_rejects_invalid_rows():
    observed_at = utc("2026-07-22T01:03:30Z")
    earliest = utc("2026-07-22T01:01:00Z")
    payload = metric_payload(
        {"timeStamp": "2026-07-22T01:00:00Z", "average": 1},
        {"timeStamp": "2026-07-22T01:02:00Z", "average": 2.0},
        {"timestamp": "2026-07-22T01:03:00+00:00", "average": 2.5},
        {"timeStamp": "bad", "average": 4},
        {"timeStamp": "2026-07-22T01:03:00Z", "average": None},
        {"timeStamp": "2026-07-22T01:03:00Z", "average": True},
    )

    assert osm.parse_metric_samples(payload, observed_at, earliest) == [
        {
            "metric_timestamp": "2026-07-22T01:02:00Z",
            "observed_at": "2026-07-22T01:03:30Z",
            "instance_count": 2,
        },
        {
            "metric_timestamp": "2026-07-22T01:03:00Z",
            "observed_at": "2026-07-22T01:03:30Z",
            "instance_count": 2.5,
        },
    ]


def test_parse_metric_samples_rejects_malformed_envelopes():
    observed_at = utc("2026-07-22T01:03:30Z")
    earliest = utc("2026-07-22T01:01:00Z")

    assert osm.parse_metric_samples(None, observed_at, earliest) == []
    assert osm.parse_metric_samples({}, observed_at, earliest) == []
    assert osm.parse_metric_samples({"value": []}, observed_at, earliest) == []
    assert (
        osm.parse_metric_samples(
            {"value": [{"timeseries": "bad"}]}, observed_at, earliest
        )
        == []
    )


def test_metric_store_replaces_changed_bucket_and_sorts_timestamps():
    store = osm.MetricStore()
    later = {
        "metric_timestamp": "2026-07-22T01:03:00Z",
        "observed_at": "2026-07-22T01:03:30Z",
        "instance_count": 2,
    }
    earlier = {
        "metric_timestamp": "2026-07-22T01:02:00Z",
        "observed_at": "2026-07-22T01:02:30Z",
        "instance_count": 1,
    }

    assert store.upsert(later) is True
    assert store.upsert(later) is False
    assert store.upsert(earlier) is True
    assert (
        store.upsert(
            {
                **later,
                "observed_at": "2026-07-22T01:04:00Z",
                "instance_count": 3,
            }
        )
        is True
    )
    assert store.values() == [
        earlier,
        {
            "metric_timestamp": "2026-07-22T01:03:00Z",
            "observed_at": "2026-07-22T01:04:00Z",
            "instance_count": 3,
        },
    ]


def test_observe_retries_query_errors_and_returns_samples(monkeypatch):
    calls = []
    clock = iter([0.0, 0.0, 30.0, 60.0])
    responses = iter(
        [
            osm.MetricQueryError("temporary az failure"),
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "average": 2}),
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "average": 2}),
        ]
    )

    monkeypatch.setattr(osm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(osm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(osm, "_now", lambda: utc("2026-07-22T01:03:00Z"))

    def fetch(resource, start_time):
        calls.append((resource, start_time))
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    started_at, samples = osm.observe(
        "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Web/sites/app",
        duration=60,
        poll_interval=30,
        fetcher=fetch,
    )

    assert started_at == utc("2026-07-22T01:03:00Z")
    assert samples == [
        {
            "metric_timestamp": "2026-07-22T01:02:00Z",
            "observed_at": "2026-07-22T01:03:00Z",
            "instance_count": 2,
        }
    ]
    assert calls == [
        (calls[0][0], "2026-07-22T01:02:00Z"),
        (calls[0][0], "2026-07-22T01:02:00Z"),
        (calls[0][0], "2026-07-22T01:02:00Z"),
    ]


def test_observe_raises_when_every_query_fails(monkeypatch):
    clock = iter([0.0, 0.0, 30.0])
    monkeypatch.setattr(osm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(osm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(osm, "_now", lambda: utc("2026-07-22T01:03:00Z"))

    def fail(resource, start_time):
        raise osm.MetricQueryError("az failed")

    try:
        osm.observe("resource", duration=30, poll_interval=30, fetcher=fail)
    except osm.MetricQueryError as error:
        assert "az failed" in str(error)
    else:
        raise AssertionError("MetricQueryError was not raised")


def test_observe_fails_when_the_final_query_does_not_recover(monkeypatch):
    clock = iter([0.0, 0.0, 30.0])
    responses = iter(
        [
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "average": 2}),
            osm.MetricQueryError("final az failure"),
        ]
    )
    monkeypatch.setattr(osm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(osm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(osm, "_now", lambda: utc("2026-07-22T01:03:00Z"))

    def fetch(resource, start_time):
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    try:
        osm.observe("resource", duration=30, poll_interval=30, fetcher=fetch)
    except osm.MetricQueryError as error:
        assert "final az failure" in str(error)
    else:
        raise AssertionError("MetricQueryError was not raised")


def test_observe_records_observed_at_after_metric_fetch(monkeypatch):
    clock = iter([0.0, 0.0])
    fetched = False
    now_calls = 0

    def now():
        nonlocal now_calls
        now_calls += 1
        if now_calls == 1:
            return utc("2026-07-22T01:03:00Z")
        assert fetched is True
        return utc("2026-07-22T01:03:05Z")

    def fetch(resource, start_time):
        nonlocal fetched
        fetched = True
        return metric_payload(
            {"timeStamp": "2026-07-22T01:02:00Z", "average": 2}
        )

    monkeypatch.setattr(osm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(osm, "_now", now)

    started_at, samples = osm.observe(
        "resource",
        duration=0,
        poll_interval=30,
        fetcher=fetch,
    )

    assert started_at == utc("2026-07-22T01:03:00Z")
    assert samples[0]["observed_at"] == "2026-07-22T01:03:05Z"


def test_main_writes_atomic_output_and_returns_0_1_and_2(
    monkeypatch, tmp_path, capsys
):
    output = tmp_path / "metric.json"
    started_at = utc("2026-07-22T01:03:00Z")
    sample = {
        "metric_timestamp": "2026-07-22T01:03:00Z",
        "observed_at": "2026-07-22T01:03:30Z",
        "instance_count": 2,
    }
    args = [
        "--resource",
        "resource",
        "--duration",
        "240",
        "--poll-interval",
        "30",
        "--output",
        str(output),
    ]

    monkeypatch.setattr(
        osm, "observe", lambda *unused, **kwargs: (started_at, [sample])
    )
    assert osm.main(args) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "metric": "InstanceCount",
        "aggregation": "Average",
        "interval": "PT1M",
        "trial_started_at": "2026-07-22T01:03:00Z",
        "poll_interval_seconds": 30,
        "duration_seconds": 240,
        "samples": [sample],
    }
    assert not list(tmp_path.glob(".metric.json.*"))

    monkeypatch.setattr(osm, "observe", lambda *unused, **kwargs: (started_at, []))
    assert osm.main(args) == 2

    def fail(*unused, **kwargs):
        raise osm.MetricFatalError("az failed")

    monkeypatch.setattr(osm, "observe", fail)
    assert osm.main(args) == 1
    assert "metric observation failed: az failed" in capsys.readouterr().err

    monkeypatch.setattr(
        osm, "observe", lambda *unused, **kwargs: (started_at, [sample])
    )
    monkeypatch.setattr(
        osm,
        "write_atomic",
        lambda *unused: (_ for _ in ()).throw(OSError("disk full")),
    )
    assert osm.main(args) == 1
    assert "metric observation failed: disk full" in capsys.readouterr().err

    assert (
        osm.main(
            [
                "--resource",
                "resource",
                "--duration",
                "0",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    assert "duration and poll-interval must be positive" in capsys.readouterr().err


def test_fetch_metric_reports_cli_and_json_errors(monkeypatch):
    class Result:
        returncode = 1
        stdout = ""
        stderr = "authorization failed"

    monkeypatch.setattr(osm.subprocess, "run", lambda *args, **kwargs: Result())
    try:
        osm.fetch_metric("resource", "2026-07-22T01:02:00Z")
    except osm.MetricQueryError as error:
        assert "authorization failed" in str(error)
    else:
        raise AssertionError("MetricQueryError was not raised")

    Result.returncode = 0
    Result.stdout = "{"
    Result.stderr = ""
    try:
        osm.fetch_metric("resource", "2026-07-22T01:02:00Z")
    except osm.MetricFatalError as error:
        assert "invalid Azure CLI JSON" in str(error)
    else:
        raise AssertionError("MetricFatalError was not raised")


def test_observer_uses_supported_web_app_instance_count_metric(monkeypatch):
    captured = {}

    class Result:
        returncode = 0
        stdout = '{"value":[]}'
        stderr = ""

    def run(command, **kwargs):
        captured["command"] = command
        return Result()

    monkeypatch.setattr(osm.subprocess, "run", run)

    assert osm.METRIC_NAME == "InstanceCount"
    assert osm.AGGREGATION == "Average"
    assert osm.fetch_metric("resource", "2026-07-22T01:02:00Z") == {"value": []}
    assert captured["command"][captured["command"].index("--metric") + 1] == "InstanceCount"
    assert captured["command"][captured["command"].index("--aggregation") + 1] == "Average"
