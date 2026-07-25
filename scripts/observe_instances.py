#!/usr/bin/env python3
import argparse
import json
import multiprocessing
import sys
import time
from concurrent.futures import TimeoutError as FutureTimeoutError
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


HARD_DEADLINE_GRACE = 0.25
PROCESS_REAP_GRACE = 0.2
PROCESS_START_GRACE = 5


def _utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return parsed.astimezone(timezone.utc)


def _format_utc(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_sample(payload, observed_at, load_started_at):
    if not isinstance(payload, dict):
        return None
    instance = payload.get("instance")
    started_at = payload.get("started_at")
    if not isinstance(instance, str) or not instance.strip():
        return None
    if not isinstance(started_at, str) or not started_at:
        return None
    try:
        started = _utc(started_at)
    except ValueError:
        return None
    age = int((observed_at - started).total_seconds())
    load_delay = int((observed_at - load_started_at).total_seconds())
    if age < 0 or load_delay < 0:
        return None
    return {
        "instance": instance,
        "started_at": _format_utc(started),
        "first_seen_at": _format_utc(observed_at),
        "first_response_age": age,
        "load_to_first_response_seconds": load_delay,
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
    except (HTTPError, URLError, OSError, TimeoutError):
        return None


def _observe_threaded(
    url,
    baseline_instance,
    load_started_at,
    duration,
    concurrency,
    request_timeout,
):
    deadline = time.monotonic() + duration
    store = ObservationStore(baseline_instance)
    pool = ThreadPoolExecutor(max_workers=concurrency)
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            timeout = min(request_timeout, remaining)
            futures = [pool.submit(fetch, url, timeout) for _ in range(concurrency)]
            try:
                completed_timeout = max(0, deadline - time.monotonic())
                for future in as_completed(futures, timeout=completed_timeout):
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    try:
                        payload = future.result(timeout=remaining)
                    except Exception:
                        continue
                    sample = parse_sample(
                        payload,
                        datetime.now(timezone.utc),
                        load_started_at,
                    )
                    if store.add(sample):
                        print(
                            f"{sample['instance']}\t{_format_utc(load_started_at)}\t"
                            f"{sample['first_seen_at']}\t"
                            f"{sample['load_to_first_response_seconds']}\t"
                            f"{sample['started_at']}\t{sample['first_response_age']}",
                            flush=True,
                        )
            except FutureTimeoutError:
                pass
            finally:
                for future in futures:
                    future.cancel()
            remaining = deadline - time.monotonic()
            if remaining > 0:
                time.sleep(min(0.2, remaining))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return store.values()


class ObservationExecutionError(RuntimeError):
    pass


def _observe_child(
    connection,
    url,
    baseline_instance,
    load_started_at,
    duration,
    concurrency,
    request_timeout,
):
    try:
        connection.send(("started", None))
        connection.send(
            (
                "ok",
                _observe_threaded(
                    url,
                    baseline_instance,
                    load_started_at,
                    duration,
                    concurrency,
                    request_timeout,
                ),
            )
        )
    except BaseException as error:
        try:
            connection.send(("error", f"{type(error).__name__}: {error}"))
        except (BrokenPipeError, EOFError, OSError):
            pass
    finally:
        connection.close()


def _multiprocessing_context():
    return multiprocessing.get_context("spawn")


def _terminate_and_reap(process):
    if process.is_alive():
        process.terminate()
        process.join(PROCESS_REAP_GRACE)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(PROCESS_REAP_GRACE)
    if process.is_alive():
        raise ObservationExecutionError("observation child could not be reaped")


def observe(
    url,
    baseline_instance,
    load_started_at,
    duration,
    concurrency,
    request_timeout,
):
    context = _multiprocessing_context()
    parent_connection, child_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_observe_child,
        args=(
            child_connection,
            url,
            baseline_instance,
            load_started_at,
            duration,
            concurrency,
            request_timeout,
        ),
        daemon=True,
    )
    started = False
    try:
        try:
            process.start()
        except (OSError, RuntimeError) as error:
            raise ObservationExecutionError(f"failed to start observation child: {error}") from error
        started = True
        child_connection.close()
        if not parent_connection.poll(PROCESS_START_GRACE):
            if process.is_alive():
                _terminate_and_reap(process)
            raise ObservationExecutionError(
                f"observation child did not start within {PROCESS_START_GRACE} seconds"
            )
        try:
            status, payload = parent_connection.recv()
        except (EOFError, OSError) as error:
            if process.is_alive():
                _terminate_and_reap(process)
            else:
                process.join()
            raise ObservationExecutionError(
                f"observation child exited before startup handshake (exit={process.exitcode})"
            ) from error
        if status != "started":
            if status == "error":
                raise ObservationExecutionError(payload)
            raise ObservationExecutionError(
                f"observation child returned unexpected startup status: {status}"
            )

        process.join(duration + HARD_DEADLINE_GRACE)
        if process.is_alive():
            _terminate_and_reap(process)
            raise ObservationExecutionError("observation exceeded its hard deadline")
        if not parent_connection.poll(0):
            raise ObservationExecutionError(
                f"observation child exited without a result (exit={process.exitcode})"
            )
        try:
            status, payload = parent_connection.recv()
        except (EOFError, OSError) as error:
            raise ObservationExecutionError(
                f"observation child exited without a readable result (exit={process.exitcode})"
            ) from error
        if status == "error":
            raise ObservationExecutionError(payload)
        return payload
    finally:
        if started:
            if process.is_alive():
                _terminate_and_reap(process)
            else:
                process.join()
            process.close()
        child_connection.close()
        parent_connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--baseline-instance", required=True)
    parser.add_argument("--load-started-at", required=True)
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
    if not args.baseline_instance.strip():
        print("baseline-instance must not be empty or whitespace", file=sys.stderr)
        return 1
    try:
        load_started_at = _utc(args.load_started_at)
    except ValueError:
        print(
            "load-started-at must be an ISO-8601 timestamp with timezone",
            file=sys.stderr,
        )
        return 1

    print(
        "instance\tload_started_at\tfirst_seen_at\t"
        "load_to_first_response_seconds\tstarted_at\tfirst_response_age",
        flush=True,
    )
    try:
        observations = observe(
            args.url,
            args.baseline_instance,
            load_started_at,
            args.duration,
            args.concurrency,
            args.request_timeout,
        )
    except ObservationExecutionError as error:
        print(f"observation failed: {error}", file=sys.stderr)
        return 1
    try:
        payload = {
            "load_started_at": _format_utc(load_started_at),
            "observations": observations,
        }
        args.output.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as error:
        print(f"failed to write {args.output}: {error}", file=sys.stderr)
        return 1
    return 0 if observations else 2


if __name__ == "__main__":
    raise SystemExit(main())
