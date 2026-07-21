from datetime import datetime, timezone

from scripts.observe_instances import ObservationStore, parse_sample


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def test_parse_sample_calculates_first_response_age():
    sample = parse_sample(
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

    assert parse_sample({}, observed) is None
    assert parse_sample({"instance": "", "started_at": "2026-07-21T02:00:00Z"}, observed) is None
    assert parse_sample({"instance": None, "started_at": "2026-07-21T02:00:00Z"}, observed) is None
    assert parse_sample({"instance": "worker02", "started_at": "not-a-time"}, observed) is None


def test_store_ignores_baseline_and_duplicate_instances():
    store = ObservationStore("worker01")
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
