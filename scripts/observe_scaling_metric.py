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
    pass


class MetricFatalError(MetricObservationError):
    pass


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


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


def _now():
    return datetime.now(timezone.utc)


def fetch_metric(resource, start_time):
    command = [
        "az",
        "monitor",
        "metrics",
        "list",
        "--resource",
        resource,
        "--metric",
        METRIC_NAME,
        "--interval",
        INTERVAL,
        "--aggregation",
        AGGREGATION,
        "--start-time",
        start_time,
        "-o",
        "json",
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
            print(
                f"metric query failed; retrying: {error}",
                file=sys.stderr,
                flush=True,
            )

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
