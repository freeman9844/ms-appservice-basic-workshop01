# Automatic Scaling Metric Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record `AutomaticScalingInstanceCount` throughout each Prewarmed A/B burst and correlate its one-minute capacity timeline with the existing new-instance response observations.

**Architecture:** Add a dependency-free Python observer that polls Azure Monitor through `az`, de-duplicates metric buckets, prints changes live, and atomically persists a validated JSON object. Both the workshop commands and `scripts/rehearsal.sh` run this observer before `hey`, wait for it after the 180-second instance observation, and reject any trial whose metric, instance, or load process fails.

**Tech Stack:** Python 3 standard library, Azure CLI, Bash, `jq`, `pytest`

## Global Constraints

- Use metric `AutomaticScalingInstanceCount`, aggregation `Maximum`, and interval `PT1M`.
- Poll every 30 seconds for 240 seconds: 180 seconds of load plus up to 60 seconds of Azure Monitor ingestion allowance.
- Keep `InstanceCount` unchanged as the single-instance baseline gate.
- Persist `trial_started_at`, `metric_timestamp`, `observed_at`, and numeric `instance_count`.
- Use `prewarmed-0-instance-count.json` and `prewarmed-1-instance-count.json`.
- Exit `0` only when at least one valid metric sample is atomically persisted; exit `1` for unrecoverable execution, parse, argument, or write errors; exit `2` when successful queries produce no valid samples.
- Require metric observer, instance observer, and `hey` exit codes to all be zero before continuing.
- Do not change the app API, `hey -z 180s -c 100 -q 10` load, `STARTUP_DELAY_SECONDS=20`, scaling configuration, or single-run evidence limitations.
- Treat the metric timeline as supporting evidence only: it does not distinguish active from Prewarmed capacity, expose instance IDs, or provide exact activation time.

---

## File Structure

- Create `scripts/observe_scaling_metric.py`: Azure Monitor polling, payload parsing, bucket replacement, live output, exit codes, and atomic JSON persistence.
- Create `scripts/tests/test_observe_scaling_metric.py`: focused unit and CLI-contract tests for the new observer.
- Modify `scripts/rehearsal.sh`: process lifecycle, output validation, trial failure propagation, and metric timeline printing.
- Modify `scripts/tests/test_rehearsal_contract.py`: static contracts for metric PID cleanup, invocation ordering, status preservation, and JSON validation.
- Modify `docs/07-autoscale.md`: participant commands, explanations, output paths, timeline display, and interpretation limits.
- Modify `scripts/tests/test_autoscale_doc_contract.py`: static contracts for the documented Trial A/B and step 6 flow.

### Task 1: Build the Automatic Scaling Metric Observer

**Files:**
- Create: `scripts/observe_scaling_metric.py`
- Create: `scripts/tests/test_observe_scaling_metric.py`

**Interfaces:**
- Consumes: Azure CLI command `az monitor metrics list --resource <id> --metric AutomaticScalingInstanceCount --interval PT1M --aggregation Maximum --start-time <UTC> -o json`
- Produces: `parse_metric_samples(payload: object, observed_at: datetime, earliest: datetime) -> list[dict]`
- Produces: `MetricStore.upsert(sample: dict) -> bool` and `MetricStore.values() -> list[dict]`
- Produces: `observe(resource: str, duration: int, poll_interval: int) -> tuple[datetime, list[dict]]`
- Produces: CLI `main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: Write parsing and replacement tests**

Create `scripts/tests/test_observe_scaling_metric.py` with:

```python
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
        {"timeStamp": "2026-07-22T01:00:00Z", "maximum": 1},
        {"timeStamp": "2026-07-22T01:02:00Z", "maximum": 2.0},
        {"timestamp": "2026-07-22T01:03:00+00:00", "maximum": 3},
        {"timeStamp": "bad", "maximum": 4},
        {"timeStamp": "2026-07-22T01:03:00Z", "maximum": None},
        {"timeStamp": "2026-07-22T01:03:00Z", "maximum": 1.5},
        {"timeStamp": "2026-07-22T01:03:00Z", "maximum": True},
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
            "instance_count": 3,
        },
    ]


def test_parse_metric_samples_rejects_malformed_envelopes():
    observed_at = utc("2026-07-22T01:03:30Z")
    earliest = utc("2026-07-22T01:01:00Z")

    assert osm.parse_metric_samples(None, observed_at, earliest) == []
    assert osm.parse_metric_samples({}, observed_at, earliest) == []
    assert osm.parse_metric_samples({"value": []}, observed_at, earliest) == []
    assert osm.parse_metric_samples(
        {"value": [{"timeseries": "bad"}]}, observed_at, earliest
    ) == []


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
    assert store.upsert({**later, "observed_at": "2026-07-22T01:04:00Z", "instance_count": 3}) is True
    assert store.values() == [
        earlier,
        {
            "metric_timestamp": "2026-07-22T01:03:00Z",
            "observed_at": "2026-07-22T01:04:00Z",
            "instance_count": 3,
        },
    ]
```

- [ ] **Step 2: Run the parsing tests and verify they fail**

Run:

```bash
python3 -m pytest scripts/tests/test_observe_scaling_metric.py -v
```

Expected: collection fails with `ImportError: cannot import name 'observe_scaling_metric' from 'scripts'`.

- [ ] **Step 3: Implement timestamp parsing, payload parsing, and `MetricStore`**

Create `scripts/observe_scaling_metric.py` with these definitions:

```python
#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path


METRIC_NAME = "AutomaticScalingInstanceCount"
AGGREGATION = "Maximum"
INTERVAL = "PT1M"


class MetricObservationError(RuntimeError):
    pass


class MetricQueryError(MetricObservationError):
    """Retryable non-zero Azure CLI result."""
    pass


class MetricFatalError(MetricObservationError):
    """Unrecoverable process-start or JSON-decoding failure."""
    pass


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_metric_samples(payload, observed_at, earliest):
    try:
        rows = payload["value"][0]["timeseries"][0]["data"]
    except (KeyError, IndexError, TypeError):
        return []
    if not isinstance(rows, list):
        return []

    samples = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = row.get("timeStamp", row.get("timestamp"))
        maximum = row.get("maximum")
        if not isinstance(timestamp, str):
            continue
        if isinstance(maximum, bool) or not isinstance(maximum, (int, float)):
            continue
        if maximum < 0 or not float(maximum).is_integer():
            continue
        try:
            metric_time = _utc(timestamp)
        except ValueError:
            continue
        if metric_time < earliest:
            continue
        samples.append(
            {
                "metric_timestamp": _format_utc(metric_time),
                "observed_at": _format_utc(observed_at),
                "instance_count": int(maximum),
            }
        )
    return sorted(samples, key=lambda sample: sample["metric_timestamp"])


class MetricStore:
    def __init__(self):
        self._samples = {}

    def upsert(self, sample):
        timestamp = sample["metric_timestamp"]
        current = self._samples.get(timestamp)
        if current == sample or (
            current is not None
            and current["instance_count"] == sample["instance_count"]
        ):
            return False
        self._samples[timestamp] = sample
        return True

    def values(self):
        return [self._samples[key] for key in sorted(self._samples)]
```

- [ ] **Step 4: Run the parsing tests and verify they pass**

Run:

```bash
python3 -m pytest scripts/tests/test_observe_scaling_metric.py -v
```

Expected: `3 passed`.

- [ ] **Step 5: Add polling, retry, exit-code, and atomic-write tests**

Append:

```python
def test_observe_retries_query_errors_and_returns_samples(monkeypatch):
    calls = []
    clock = iter([0.0, 0.0, 30.0, 60.0])
    responses = iter(
        [
            osm.MetricQueryError("temporary az failure"),
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "maximum": 2}),
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "maximum": 2}),
        ]
    )

    monkeypatch.setattr(osm.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(osm.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        osm,
        "_now",
        lambda: utc("2026-07-22T01:03:00Z"),
    )

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
            metric_payload({"timeStamp": "2026-07-22T01:02:00Z", "maximum": 2}),
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


def test_main_writes_atomic_output_and_returns_0_1_and_2(monkeypatch, tmp_path, capsys):
    output = tmp_path / "metric.json"
    started_at = utc("2026-07-22T01:03:00Z")
    sample = {
        "metric_timestamp": "2026-07-22T01:03:00Z",
        "observed_at": "2026-07-22T01:03:30Z",
        "instance_count": 2,
    }
    args = [
        "--resource", "resource",
        "--duration", "240",
        "--poll-interval", "30",
        "--output", str(output),
    ]

    monkeypatch.setattr(osm, "observe", lambda *unused, **kwargs: (started_at, [sample]))
    assert osm.main(args) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {
        "metric": "AutomaticScalingInstanceCount",
        "aggregation": "Maximum",
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

    monkeypatch.setattr(osm, "observe", lambda *unused, **kwargs: (started_at, [sample]))
    monkeypatch.setattr(
        osm,
        "write_atomic",
        lambda *unused: (_ for _ in ()).throw(OSError("disk full")),
    )
    assert osm.main(args) == 1
    assert "metric observation failed: disk full" in capsys.readouterr().err

    assert osm.main(["--resource", "resource", "--duration", "0", "--output", str(output)]) == 1
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
        raise AssertionError("MetricQueryError was not raised")
```

- [ ] **Step 6: Implement Azure CLI polling and atomic output**

Complete `scripts/observe_scaling_metric.py` with:

```python
def _now():
    return datetime.now(timezone.utc)


def fetch_metric(resource, start_time):
    command = [
        "az", "monitor", "metrics", "list",
        "--resource", resource,
        "--metric", METRIC_NAME,
        "--interval", INTERVAL,
        "--aggregation", AGGREGATION,
        "--start-time", start_time,
        "-o", "json",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise MetricFatalError(f"failed to start az: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"az exited {completed.returncode}"
        raise MetricQueryError(detail)
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise MetricFatalError(f"invalid Azure CLI JSON: {error}") from error


def observe(resource, duration, poll_interval, fetcher=fetch_metric):
    started_at = _now()
    earliest = started_at.replace(second=0, microsecond=0) - timedelta(minutes=1)
    query_start = _format_utc(earliest)
    deadline = time.monotonic() + duration
    store = MetricStore()
    last_error = None

    print("metric_timestamp\tobserved_at\tinstance_count", flush=True)
    while True:
        observed_at = _now()
        try:
            payload = fetcher(resource, query_start)
            last_error = None
            for sample in parse_metric_samples(payload, observed_at, earliest):
                if store.upsert(sample):
                    print(
                        f"{sample['metric_timestamp']}\t{sample['observed_at']}\t"
                        f"{sample['instance_count']}",
                        flush=True,
                    )
        except MetricQueryError as error:
            last_error = error
            print(f"metric query failed; retrying: {error}", file=sys.stderr, flush=True)

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(poll_interval, remaining))

    if last_error is not None:
        raise last_error
    return started_at, store.values()


def write_atomic(path, payload):
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            json.dump(payload, temporary, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--resource", required=True)
    parser.add_argument("--duration", type=int, default=240)
    parser.add_argument("--poll-interval", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return 1 if getattr(error, "code", 1) else 0
    if args.duration <= 0 or args.poll_interval <= 0:
        print("duration and poll-interval must be positive", file=sys.stderr)
        return 1
    if not args.resource.strip():
        print("resource must not be empty or whitespace", file=sys.stderr)
        return 1

    try:
        started_at, samples = observe(
            args.resource,
            args.duration,
            args.poll_interval,
        )
        payload = {
            "metric": METRIC_NAME,
            "aggregation": AGGREGATION,
            "interval": INTERVAL,
            "trial_started_at": _format_utc(started_at),
            "poll_interval_seconds": args.poll_interval,
            "duration_seconds": args.duration,
            "samples": samples,
        }
        write_atomic(args.output, payload)
    except (MetricObservationError, OSError) as error:
        print(f"metric observation failed: {error}", file=sys.stderr)
        return 1
    return 0 if samples else 2


if __name__ == "__main__":
    raise SystemExit(main())
```

The final query occurs at the 240-second boundary. With a 180-second load,
polls at 210 and 240 seconds provide the full 60-second post-load ingestion
allowance.

- [ ] **Step 7: Run the observer tests**

Run:

```bash
python3 -m pytest scripts/tests/test_observe_scaling_metric.py -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit the observer**

```bash
git add scripts/observe_scaling_metric.py scripts/tests/test_observe_scaling_metric.py
git commit -m "feat: observe automatic scaling metric"
```

### Task 2: Integrate Metric Observation into the Automated Rehearsal

**Files:**
- Modify: `scripts/rehearsal.sh:16-67,295-393,458-540`
- Modify: `scripts/tests/test_rehearsal_contract.py`

**Interfaces:**
- Consumes: `scripts/observe_scaling_metric.py --resource "$APP_ID" --duration 240 --poll-interval 30 --output <path>`
- Consumes: metric JSON object defined in Task 1
- Produces: `stop_tracked_metric_observer()`, global `METRIC_OBSERVER_PID`, `METRIC_FAILURE`, and `METRIC_STATUS`
- Produces: `run_instance_age_trial <label> <instance-json> <metric-json> <hey-output>`

- [ ] **Step 1: Write failing rehearsal contract tests**

Append to `scripts/tests/test_rehearsal_contract.py`:

```python
def test_rehearsal_tracks_and_stops_metric_observer():
    hey_stop = REHEARSAL.split("stop_tracked_hey() {", 1)[1].split(
        "stop_tracked_metric_observer() {", 1
    )[0]
    metric_stop = REHEARSAL.split("stop_tracked_metric_observer() {", 1)[1].split(
        "cleanup() {", 1
    )[0]
    assert 'METRIC_OBSERVER_PID=""' in REHEARSAL
    assert "stop_tracked_metric_observer()" in REHEARSAL
    assert 'if [ -n "$METRIC_OBSERVER_PID" ]; then' in REHEARSAL
    assert 'kill "$pid"' in metric_stop
    assert 'wait "$pid"' in metric_stop
    assert 'return "$status"' in metric_stop
    assert 'wait "$pid" 2>/dev/null || true' not in metric_stop
    assert 'return "$status"' in hey_stop
    assert 'wait "$pid" 2>/dev/null || true' not in hey_stop
    assert REHEARSAL.index("stop_tracked_metric_observer()") < REHEARSAL.index("cleanup()")


def test_rehearsal_runs_metric_observer_before_load_for_both_trials():
    invocation = 'python3 "$REPO_DIR/scripts/observe_scaling_metric.py"'
    assert REHEARSAL.count(invocation) == 1
    run_trial = REHEARSAL.split("run_instance_age_trial() {", 1)[1].split(
        "handle_trial_observations() {", 1
    )[0]
    assert '--resource "$APP_ID"' in run_trial
    assert "--duration 240" in run_trial
    assert "--poll-interval 30" in run_trial
    assert '--output "$metric_file"' in run_trial
    assert run_trial.index(invocation) < run_trial.index(
        'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
    )
    assert "METRIC_STATUS=$metric_status" in run_trial
    assert "METRIC_FAILURE=1" in run_trial
    assert "실패: observer=${observer_status}, hey=${HEY_STATUS}, metric=${METRIC_STATUS}" in REHEARSAL


def test_rehearsal_validates_metric_files_and_prints_timeline():
    assert 'NO_PREWARM_METRICS="$TMP_DIR/prewarmed-0-instance-count.json"' in REHEARSAL
    assert 'PREWARM_METRICS="$TMP_DIR/prewarmed-1-instance-count.json"' in REHEARSAL
    assert ".metric == \"AutomaticScalingInstanceCount\"" in REHEARSAL
    assert '(.samples | type == "array" and length > 0)' in REHEARSAL
    assert ".metric_timestamp" in REHEARSAL
    assert ".observed_at" in REHEARSAL
    assert ".instance_count" in REHEARSAL
    assert "trial_started_at" in REHEARSAL
    assert "fromdateiso8601" in REHEARSAL
```

Before appending these tests, remove the following DOCS-specific assertions
from `test_rehearsal_preserves_hey_failures_and_stops_tracked_pid`.
Documentation status text belongs in `test_autoscale_doc_contract.py` and
changes in Task 3:

```python
assert 'echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS"' in DOCS
assert "시험 A 실패: 다음 시험으로 진행하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
assert "시험 B 실패: 결과를 해석하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
assert "동시에 실패했습니다" not in DOCS
assert "HEY_STATUS=$hey_status" not in DOCS
assert 'return "$observer_status"' not in DOCS
assert 'return "$hey_status"' not in DOCS
```

In the same existing test, replace:

```python
assert "동시에 실패했습니다" in REHEARSAL
```

with the three-status summary assertion already included in
`test_rehearsal_runs_metric_observer_before_load_for_both_trials`.

- [ ] **Step 2: Run the rehearsal contract and verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_rehearsal_contract.py -v
```

Expected: the three new tests fail because metric process tracking and files are absent.

- [ ] **Step 3: Add metric process state and cleanup**

In `scripts/rehearsal.sh`, add globals beside `HEY_PID`:

```bash
METRIC_OBSERVER_PID=""
METRIC_FAILURE=0
METRIC_STATUS=0
```

Add after `stop_tracked_hey`:

```bash
stop_tracked_metric_observer() {
  local pid=$METRIC_OBSERVER_PID
  local process_state status=0
  [ -n "$pid" ] || return 0
  if kill -0 "$pid" 2>/dev/null; then
    process_state=$(ps -o stat= -p "$pid" 2>/dev/null || true)
    if [[ "$process_state" != *Z* ]]; then
      if kill "$pid" 2>/dev/null; then
        if wait "$pid" 2>/dev/null; then
          status=0
        else
          status=$?
        fi
        METRIC_OBSERVER_PID=""
        return "$status"
      fi
    fi
  fi
  if wait "$pid" 2>/dev/null; then
    status=0
  else
    status=$?
  fi
  METRIC_OBSERVER_PID=""
  return "$status"
}
```

At the start of `cleanup`, before `stop_tracked_hey`, add:

```bash
if [ -n "$METRIC_OBSERVER_PID" ]; then
  stop_tracked_metric_observer || cleanup_status=1
fi
```

Also replace the successful-kill branch in the existing `stop_tracked_hey`
with status-preserving logic:

```bash
if kill "$pid" 2>/dev/null; then
  if wait "$pid" 2>/dev/null; then
    status=0
  else
    status=$?
  fi
  HEY_PID=""
  return "$status"
fi
```

- [ ] **Step 4: Start and wait for all three trial processes**

Change `run_instance_age_trial` to accept:

```bash
local metric_file=$3
local hey_output=$4
local baseline_instance observer_status=0 hey_status=0 metric_status=0
METRIC_FAILURE=0
METRIC_STATUS=0
```

Immediately before `hey`, add:

```bash
python3 "$REPO_DIR/scripts/observe_scaling_metric.py" \
  --resource "$APP_ID" \
  --duration 240 \
  --poll-interval 30 \
  --output "$metric_file" &
METRIC_OBSERVER_PID=$!
```

When the instance observer fails, call both tracked stop functions, preserve
both statuses, and return the instance observer status:

```bash
if [ "$observer_status" -ne 0 ]; then
  if stop_tracked_hey; then hey_status=0; else hey_status=$?; fi
  if stop_tracked_metric_observer; then metric_status=0; else metric_status=$?; fi
  HEY_STATUS=$hey_status
  METRIC_STATUS=$metric_status
  [ "$hey_status" -ne 0 ] && HEY_FAILURE=1
  [ "$metric_status" -ne 0 ] && METRIC_FAILURE=1
  return "$observer_status"
fi
```

After waiting for `hey`, wait for the metric observer:

```bash
if wait "$METRIC_OBSERVER_PID"; then
  metric_status=0
else
  metric_status=$?
fi
METRIC_OBSERVER_PID=""
METRIC_STATUS=$metric_status
if [ "$metric_status" -ne 0 ]; then
  METRIC_FAILURE=1
  echo "$label AutomaticScalingInstanceCount 관찰이 실패했습니다 (exit=$metric_status)." >&2
fi
```

Keep returning `observer_status`; `handle_trial_observations` evaluates
`HEY_FAILURE` and `METRIC_FAILURE` before validating either JSON file.

- [ ] **Step 5: Validate metric failures and output shape**

Change `handle_trial_observations` to accept `metric_file=$3`. Before its
existing observer-status `case`, add:

```bash
if [ "$HEY_FAILURE" = "1" ] || [ "$METRIC_FAILURE" = "1" ]; then
  if ! restore_prewarmed_demo; then
    echo "[07] ${label} 실행 실패 후 복원에도 실패했습니다." >&2
  fi
  echo "[07] ${label} 실패: observer=${observer_status}, hey=${HEY_STATUS}, metric=${METRIC_STATUS}. 복원 및 검증 후 시험을 중단합니다." >&2
  return 1
fi
```

Replace the entire observer status `0` branch so the existing early
`return 0` cannot bypass metric validation:

```bash
0)
  if ! jq -e 'type == "array" and length > 0' "$observation_file" >/dev/null 2>&1; then
    if ! restore_prewarmed_demo; then
      echo "[07] ${label} 관찰 JSON 검증 실패 후 복원에도 실패했습니다." >&2
    fi
    echo "[07] ${label} 관찰 도구가 유효한 JSON 배열을 남기지 못했습니다." >&2
    return 1
  fi
  if ! jq -e '
    (.metric == "AutomaticScalingInstanceCount") and
    (((try (.trial_started_at | fromdateiso8601) catch null) | type) == "number") and
    (.samples | type == "array" and length > 0) and
    (.samples | all(
      (((try (.metric_timestamp | fromdateiso8601) catch null) | type) == "number") and
      (((try (.observed_at | fromdateiso8601) catch null) | type) == "number") and
      (.instance_count | type == "number")
    ))
  ' "$metric_file" >/dev/null 2>&1
  then
    if ! restore_prewarmed_demo; then
      echo "[07] ${label} metric JSON 검증 실패 후 복원에도 실패했습니다." >&2
    fi
    echo "[07] ${label} AutomaticScalingInstanceCount 결과가 유효하지 않습니다." >&2
    return 1
  fi
  return 0
  ;;
```

- [ ] **Step 6: Add trial paths, arguments, and rehearsal timeline**

Define:

```bash
NO_PREWARM_METRICS="$TMP_DIR/prewarmed-0-instance-count.json"
PREWARM_METRICS="$TMP_DIR/prewarmed-1-instance-count.json"
```

Call:

```bash
run_instance_age_trial "Prewarmed=0" "$NO_PREWARM_OBSERVATIONS" \
  "$NO_PREWARM_METRICS" "$TMP_DIR/hey-burst-0.out"
handle_trial_observations "시험 A" "$NO_PREWARM_OBSERVATIONS" \
  "$NO_PREWARM_METRICS" "$observer_status"

run_instance_age_trial "Prewarmed=1" "$PREWARM_OBSERVATIONS" \
  "$PREWARM_METRICS" "$TMP_DIR/hey-burst-1.out"
handle_trial_observations "시험 B" "$PREWARM_OBSERVATIONS" \
  "$PREWARM_METRICS" "$observer_status"
```

Adjust the handler positional parameters to match:

```bash
local label=$1
local observation_file=$2
local metric_file=$3
local observer_status=$4
```

Before the existing instance timeline, print:

```bash
printf 'trial\ttrial_started_at\tmetric_timestamp\tobserved_at\tinstance_count\n'
jq -r --arg trial "Prewarmed=0" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$NO_PREWARM_METRICS"
jq -r --arg trial "Prewarmed=1" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$PREWARM_METRICS"
```

- [ ] **Step 7: Run focused tests and shell syntax validation**

Run:

```bash
bash -n scripts/rehearsal.sh &&
python3 -m pytest \
  scripts/tests/test_observe_scaling_metric.py \
  scripts/tests/test_rehearsal_contract.py -v
```

Expected: shell syntax succeeds and all selected tests pass.

- [ ] **Step 8: Commit rehearsal integration**

```bash
git add scripts/rehearsal.sh scripts/tests/test_rehearsal_contract.py
git commit -m "feat: record scaling metric in rehearsal"
```

### Task 3: Update the Workshop Commands and Interpretation

**Files:**
- Modify: `docs/07-autoscale.md:220-590`
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `scripts/tests/test_rehearsal_contract.py`

**Interfaces:**
- Consumes: Task 1 CLI and JSON contract
- Produces: copy-and-run Trial A/B commands with `METRIC_PID`, `METRIC_STATUS`, and trial-specific metric paths
- Produces: step 6 capacity timeline table followed by the existing instance and range tables

- [ ] **Step 1: Write failing document contract tests**

Append:

```python
def test_trials_record_automatic_scaling_instance_count():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(text, "## 3단계 — Prewarmed A/B 비교 준비", "## 4단계 — 시험 A")
    step_four = section(text, "## 4단계 — 시험 A", "## 5단계 — scale-in 게이트 후 시험 B")
    step_five = section(text, "## 5단계 — scale-in 게이트 후 시험 B", "## 6단계 — 결과 해석 및 정리")

    assert 'NO_PREWARM_METRICS="$AB_DIR/prewarmed-0-instance-count.json"' in step_three
    assert 'PREWARM_METRICS="$AB_DIR/prewarmed-1-instance-count.json"' in step_three

    for label, block, output in [
        ("Trial A", step_four, "$NO_PREWARM_METRICS"),
        ("Trial B", step_five, "$PREWARM_METRICS"),
    ]:
        command = code_block_after(block, f"🟢 **실행 — 시험 {'A' if label == 'Trial A' else 'B'} 관찰**")
        metric = 'python3 "$REPO_DIR/scripts/observe_scaling_metric.py"'
        load = 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
        assert metric in command, label
        assert '--resource "$APP_ID"' in command, label
        assert "--duration 240" in command, label
        assert "--poll-interval 30" in command, label
        assert f'--output "{output}"' in command, label
        assert command.index(metric) < command.index(load), label
        assert "METRIC_PID=$!" in command, label
        assert 'wait "$METRIC_PID"' in command, label
        assert "METRIC_STATUS=$?" in command, label
        assert "metric exit=$METRIC_STATUS" in command, label


def test_step_six_prints_and_limits_metric_timeline():
    text = DOC.read_text(encoding="utf-8")
    step_six = section(text, "## 6단계 — 결과 해석 및 정리", "## 검증")

    assert "🟢 **실행 — AutomaticScalingInstanceCount 타임라인 출력**" in step_six
    assert "trial_started_at" in step_six
    assert "metric_timestamp" in step_six
    assert "observed_at" in step_six
    assert "instance_count" in step_six
    assert "`PT1M`" in step_six
    assert "active와 Prewarmed를 구분하지" in step_six
    assert "instance ID" in step_six
    assert "정확한 activation 시각" in step_six
    assert "capacity 효율" in step_six
    assert "보조 증거" in step_six
```

Update the existing Trial A/B explanation contracts from
`"두 exit code가 모두 0"` to `"세 exit code가 모두 0"`.

Add these DOCS assertions back to
`test_rehearsal_preserves_hey_failures_and_stops_tracked_pid` in
`scripts/tests/test_rehearsal_contract.py`:

```python
assert 'echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS, metric exit=$METRIC_STATUS"' in DOCS
assert "시험 A 실패: 세 결과를 비교하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
assert "시험 B 실패: 세 결과를 비교하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
```

- [ ] **Step 2: Run the document contract and verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -v
```

Expected: the two new tests fail because metric paths, commands, and timeline text are absent.

- [ ] **Step 3: Add metric output paths and preparation explanation**

In step 3, extend the path block:

```bash
NO_PREWARM_METRICS="$AB_DIR/prewarmed-0-instance-count.json"
PREWARM_METRICS="$AB_DIR/prewarmed-1-instance-count.json"
```

Explain that the `observations.json` files contain response instances, while
the `instance-count.json` files contain Azure Monitor capacity buckets. Replace
the final step 3 note with:

```markdown
> 👁️ `InstanceCount`는 시험 시작 전·시험 사이의 단일 인스턴스 기준 상태
> 확인에만 사용합니다. 각 시험 중에는 `AutomaticScalingInstanceCount`를
> 30초마다 조회해 1분 단위 capacity 변화를 별도 JSON으로 저장하고,
> `observe_instances.py`는 실제 응답에 나타난 새 instance를 기록합니다.
```

- [ ] **Step 4: Update Trial A and Trial B command flow**

For each trial, add a command-flow item before `hey` explaining:

```markdown
> `observe_scaling_metric.py`는 `AutomaticScalingInstanceCount`를 30초마다
> 최대 240초 관찰합니다. 180초 부하가 끝난 뒤에도 Azure Monitor 수집
> 지연을 위해 최대 60초 더 기다리며, 화면과 시험별 JSON에 기록합니다.
```

Start it before `hey`:

```bash
python3 "$REPO_DIR/scripts/observe_scaling_metric.py" \
  --resource "$APP_ID" \
  --duration 240 \
  --poll-interval 30 \
  --output "$NO_PREWARM_METRICS" &
METRIC_PID=$!
```

Use `$PREWARM_METRICS` in Trial B. Preserve the existing direct CLI style and
capture every status immediately after its command:

```bash
python3 "$REPO_DIR/scripts/observe_instances.py" \
  --url "$APP_URL/api/info" \
  --baseline-instance "$BASELINE_INSTANCE" \
  --duration 180 \
  --concurrency 30 \
  --request-timeout 5 \
  --output "$NO_PREWARM_OBSERVATIONS"
OBSERVER_STATUS=$?

wait "$HEY_PID"
HEY_STATUS=$?
wait "$METRIC_PID"
METRIC_STATUS=$?

echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS, metric exit=$METRIC_STATUS"
if [ "$OBSERVER_STATUS" -ne 0 ] || [ "$HEY_STATUS" -ne 0 ] || [ "$METRIC_STATUS" -ne 0 ]; then
  echo "시험 A 실패: 세 결과를 비교하지 말고 6단계의 복원 명령을 실행하세요." >&2
  false
fi
```

Use the same structure and Trial B wording for the second command.

- [ ] **Step 5: Add the step 6 metric timeline**

Before the existing instance result table, add:

```markdown
🟢 **실행 — AutomaticScalingInstanceCount 타임라인 출력**

> 👁️ `trial_started_at`은 metric observer를 시작한 시험 orchestration
> 시각입니다. 각 `metric_timestamp`는 Azure Monitor의 1분 집계 구간이고,
> `observed_at`은 해당 값을 CLI에서 처음 확인한 시각입니다.

```bash
printf 'trial\ttrial_started_at\tmetric_timestamp\tobserved_at\tinstance_count\n'
jq -r --arg trial "Prewarmed=0" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$NO_PREWARM_METRICS"
jq -r --arg trial "Prewarmed=1" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$PREWARM_METRICS"
```
```

Add this illustrative output, explicitly retaining the “예시” label:

```text
trial	trial_started_at	metric_timestamp	observed_at	instance_count
Prewarmed=0	2026-07-22T01:02:03Z	2026-07-22T01:02:00Z	2026-07-22T01:02:34Z	1
Prewarmed=0	2026-07-22T01:02:03Z	2026-07-22T01:03:00Z	2026-07-22T01:03:35Z	4
Prewarmed=1	2026-07-22T01:12:10Z	2026-07-22T01:12:00Z	2026-07-22T01:12:40Z	2
Prewarmed=1	2026-07-22T01:12:10Z	2026-07-22T01:13:00Z	2026-07-22T01:13:41Z	3
```

- [ ] **Step 6: Connect the metric and response timelines without overclaiming**

Add this interpretation before “이번 실측에서 보인 이점”:

```markdown
### capacity 증가와 새 응답 instance를 함께 보는 법

1. `trial_started_at`으로 시험 시작 구간을 확인합니다.
2. `AutomaticScalingInstanceCount`가 1에서 2 이상으로 변한 첫
   `metric_timestamp`를 찾습니다.
3. instance 표의 `first_seen_at`과 나란히 보며 capacity 증가 구간 뒤에
   새 instance 응답이 언제 관찰됐는지 확인합니다.

`AutomaticScalingInstanceCount`는 배포된 Prewarmed instance를 포함할 수
있지만 active와 Prewarmed를 구분하지 않고 instance ID도 제공하지
않습니다. 또한 `PT1M` 집계와 수집 지연이 있으므로
`metric_timestamp`를 Azure 내부의 정확한 activation 시각으로 해석할 수
없습니다. 응답에서 관찰된 instance 수가 적다는 사실도 capacity 효율
향상을 의미하지 않습니다. 이 타임라인은 warmed capacity buffer의
동작 방향을 이해하기 위한 보조 증거이며 인과관계 증명은 아닙니다.
```

Preserve the existing `first_response_age` table, range summary, recorded
rehearsal values, restoration commands, and alternate-result guidance.

- [ ] **Step 7: Run focused and full validation**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_observe_scaling_metric.py \
  scripts/tests/test_rehearsal_contract.py \
  scripts/tests/test_autoscale_doc_contract.py -v &&
bash -n scripts/rehearsal.sh &&
python3 -m pytest -q
```

Expected: all selected tests pass, Bash syntax succeeds, and the full suite
passes.

- [ ] **Step 8: Commit workshop integration**

```bash
git add docs/07-autoscale.md \
  scripts/tests/test_autoscale_doc_contract.py \
  scripts/tests/test_rehearsal_contract.py
git commit -m "docs: add scaling capacity timeline"
```
