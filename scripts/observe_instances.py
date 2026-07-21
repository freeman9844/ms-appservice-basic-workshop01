#!/usr/bin/env python3
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_sample(payload, observed_at):
    if not isinstance(payload, dict):
        return None
    instance = payload.get("instance")
    started_at = payload.get("started_at")
    if not isinstance(instance, str) or not instance:
        return None
    if not isinstance(started_at, str) or not started_at:
        return None
    try:
        started = _utc(started_at)
    except ValueError:
        return None
    age = int((observed_at - started).total_seconds())
    if age < 0:
        return None
    return {
        "instance": instance,
        "started_at": _format_utc(started),
        "first_seen_at": _format_utc(observed_at),
        "first_response_age": age,
    }


class ObservationStore:
    def __init__(self, baseline_instance):
        self.baseline_instance = baseline_instance
        self._observations = {}

    def add(self, sample):
        if not sample or sample.get("instance") == self.baseline_instance:
            return False
        instance = sample.get("instance")
        if instance in self._observations:
            return False
        self._observations[instance] = sample
        return True

    def values(self):
        return list(self._observations.values())


def fetch(url, timeout):
    try:
        with urlopen(url, timeout=timeout) as response:
            if getattr(response, "status", 200) != 200:
                return None
            try:
                return json.load(response)
            except (OSError, UnicodeDecodeError, ValueError):
                return None
    except (HTTPError, URLError, TimeoutError):
        return None


def observe(url, baseline_instance, duration, concurrency, request_timeout):
    deadline = time.monotonic() + duration
    store = ObservationStore(baseline_instance)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            timeout = min(request_timeout, remaining)
            futures = [pool.submit(fetch, url, timeout) for _ in range(concurrency)]
            for future in as_completed(futures):
                if time.monotonic() >= deadline:
                    break
                sample = parse_sample(future.result(), datetime.now(timezone.utc))
                if store.add(sample):
                    print(
                        f"{sample['instance']}\t{sample['started_at']}\t"
                        f"{sample['first_seen_at']}\t{sample['first_response_age']}",
                        flush=True,
                    )
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
    return store.values()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--baseline-instance", required=True)
    parser.add_argument("--duration", type=int, default=180)
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument("--request-timeout", type=float, default=5)
    parser.add_argument("--output", type=Path, required=True)
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return 1 if getattr(error, "code", 1) else 0
    if args.duration <= 0 or args.concurrency <= 0 or args.request_timeout <= 0:
        print("duration, concurrency, and request-timeout must be positive", file=sys.stderr)
        return 1

    print("instance\tstarted_at\tfirst_seen_at\tfirst_response_age", flush=True)
    observations = observe(
        args.url,
        args.baseline_instance,
        args.duration,
        args.concurrency,
        args.request_timeout,
    )
    try:
        args.output.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"failed to write {args.output}: {error}", file=sys.stderr)
        return 1
    return 0 if observations else 2


if __name__ == "__main__":
    raise SystemExit(main())
