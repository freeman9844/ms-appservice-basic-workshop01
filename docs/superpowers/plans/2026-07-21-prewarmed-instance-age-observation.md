# Prewarmed Instance Age Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unreliable single-run Prewarmed latency winner with a live, instance-by-instance timeline showing how long each new worker had been running before its first observed response.

**Architecture:** Add a standard-library Python observer that polls `/api/info`, validates samples, records each new instance once, and calculates `first_seen_at - started_at`. Both the workshop document and automated rehearsal run the same observer during identical 180-second bursts for `Prewarmed=0` and `Prewarmed=1`; they report observations without asserting that B must be faster.

**Tech Stack:** Python 3.12 standard library, pytest, Bash, Azure CLI/ARM REST, `hey`, `jq`, Markdown.

## Global Constraints

- Keep `STARTUP_DELAY_SECONDS=20`, Automatic scaling enabled, Maximum burst 5, and Always-ready 1.
- Each A/B trial must start only after two fresh post-transition `InstanceCount=1` samples.
- Do not use a `Prewarmed=1` prime load or an `InstanceCount>=2` pre-trial gate.
- Use the same burst in both trials: `hey -z 180s -c 100 -q 10 "$APP_URL/api/info"`.
- Record each non-baseline instance only once with `instance`, `started_at`, `first_seen_at`, and `first_response_age`.
- Invalid HTTP responses, empty IDs, non-string IDs, and invalid timestamps must not become observations.
- Every request timeout must be bounded by the trial's remaining 180-second deadline.
- A trial with no new instance is not evidence about Prewarmed; restore settings and fail with retry guidance.
- Never declare `Prewarmed=1` the winner from total scale-out time alone.
- On every exit after demo activation, restore and verify Always-ready 1, Prewarmed 1, deletion of `STARTUP_DELAY_SECONDS`, and a healthy `/health`.
- Do not execute Azure mutation or load commands during implementation validation.

---

## File Structure

- Create `scripts/observe_instances.py`: reusable HTTP sampler and CLI; owns validation, first-observation deduplication, age calculation, JSON output, and human-readable table output.
- Create `scripts/tests/test_observe_instances.py`: deterministic unit tests for valid samples, invalid inputs, baseline filtering, deduplication, and age calculation.
- Modify `docs/07-autoscale.md`: participant-facing instance-age experiment, interpretation, recovery, and troubleshooting.
- Modify `scripts/rehearsal.sh`: invoke the observer for both trials, remove the buffer gate and latency-winner variables, preserve cleanup.
- Modify `README.md`: adjust module 07 description, live-rehearsal status, totals, and cost duration.

---

### Task 1: Build the Instance Observation Tool

**Files:**
- Create: `scripts/observe_instances.py`
- Create: `scripts/tests/test_observe_instances.py`

**Interfaces:**
- Consumes: `/api/info` JSON containing string `instance` and ISO-8601 string `started_at`.
- Produces: JSON array at `--output` with `instance`, `started_at`, `first_seen_at`, and numeric `first_response_age`; exit 0 when at least one new instance is observed, exit 2 when the deadline expires with none, exit 1 for invalid CLI arguments or output failure.
- CLI:

```text
python3 scripts/observe_instances.py \
  --url "$APP_URL/api/info" \
  --baseline-instance "$BASELINE_INSTANCE" \
  --duration 180 \
  --concurrency 30 \
  --request-timeout 5 \
  --output "$AB_DIR/prewarmed-0-observations.json"
```

- [ ] **Step 1: Write failing tests for parsing and first-observation behavior**

Create `scripts/tests/test_observe_instances.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify the missing module failure**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q scripts/tests/test_observe_instances.py
```

Expected: collection fails with `ModuleNotFoundError: No module named 'scripts.observe_instances'`.

- [ ] **Step 3: Implement parsing, storage, bounded concurrent polling, and CLI output**

Create `scripts/observe_instances.py` with these exact public units:

```python
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
        if not sample or sample["instance"] == self.baseline_instance:
            return False
        if sample["instance"] in self._observations:
            return False
        self._observations[sample["instance"]] = sample
        return True

    def values(self):
        return list(self._observations.values())


def fetch(url, timeout):
    try:
        with urlopen(url, timeout=timeout) as response:
            if response.status != 200:
                return None
            return json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
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
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.concurrency <= 0 or args.request_timeout <= 0:
        parser.error("duration, concurrency, and request-timeout must be positive")

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
```

- [ ] **Step 4: Run the focused tests**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q scripts/tests/test_observe_instances.py
```

Expected: `3 passed`.

- [ ] **Step 5: Run the existing app tests and syntax checks**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests scripts/tests
python3 -m py_compile scripts/observe_instances.py
git diff --check
```

Expected: all tests pass, Python compilation exits 0, and `git diff --check` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add scripts/observe_instances.py scripts/tests/test_observe_instances.py
git commit -m "test: add instance age observer"
```

---

### Task 2: Rewrite Module 07 Around Instance Age

**Files:**
- Modify: `docs/07-autoscale.md:10-14`
- Modify: `docs/07-autoscale.md:203-690`

**Interfaces:**
- Consumes: `scripts/observe_instances.py` CLI and JSON schema from Task 1.
- Produces: learner workflow with `NO_PREWARM_OBSERVATIONS` and `PREWARM_OBSERVATIONS` file paths, truthful interpretation, and existing restoration guarantees.

- [ ] **Step 1: Replace module goals and conceptual explanation**

Replace claims about timing the second instance with:

```markdown
- `STARTUP_DELAY_SECONDS=20`으로 새 프로세스의 시작 준비 시간을 눈에 보이게 만듭니다.
- `/api/info`의 `started_at`과 새 instance의 최초 관찰 시각으로 `first_response_age`를 계산합니다.
- `Prewarmed=0`과 `Prewarmed=1`의 인스턴스별 시작·투입 타임라인을 비교하되, 한 번의 실행에서 어느 쪽이 반드시 더 빠르다고 판정하지 않습니다.
```

Add this interpretation immediately before the helper definitions:

```markdown
`started_at`은 20초 시작 지연 전에 기록됩니다. 따라서 `first_response_age`가 약 20초라면 시작 준비 직후 응답에 투입된 것이고, 그보다 길면 준비를 마친 뒤 실제 응답 전에 대기한 구간이 있었음을 뜻합니다. 이 값은 플랫폼 내부의 active/prewarmed 라벨을 직접 조회한 것이 아니라 앱이 관찰한 외부 증거입니다.
```

- [ ] **Step 2: Remove the unstable buffer and latency helpers**

Delete:

- `wait_for_buffer_allocation`
- `measure_scale_out`
- `NO_PREWARM_SECONDS`
- `PREWARM_SECONDS`
- prime commands `hey -z 60s -c 5 -q 2`
- the numeric improvement calculation
- expected output asserting B is faster

Retain `latest_instance_count`, `wait_for_single_instance`, health checks, and verified restoration.

- [ ] **Step 3: Add the exact participant trial helper**

Define:

```bash
run_instance_age_trial() {
  local label=$1
  local observation_file=$2
  local hey_output=$3
  local baseline_instance observer_status=0

  baseline_instance=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
    jq -er 'select((.instance | type) == "string" and (.instance | length) > 0) | .instance')

  echo "$label 기준 instance: $baseline_instance"
  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$hey_output" &
  HEY_PID=$!

  if python3 ../scripts/observe_instances.py \
    --url "$APP_URL/api/info" \
    --baseline-instance "$baseline_instance" \
    --duration 180 \
    --concurrency 30 \
    --request-timeout 5 \
    --output "$observation_file"
  then
    observer_status=0
  else
    observer_status=$?
  fi

  wait "$HEY_PID" || true
  HEY_PID=""
  return "$observer_status"
}
```

The implementation must preserve the observer's real exit code; use an `if command; then ... else observer_status=$?; fi` form rather than `if ! command`, because `!` would make `$?` equal 0 inside the branch.

- [ ] **Step 4: Write trial A and B blocks**

Trial A:

```bash
NO_PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-0-observations.json"
run_instance_age_trial \
  "Prewarmed=0" \
  "$NO_PREWARM_OBSERVATIONS" \
  "$AB_DIR/hey-burst-0.out"
```

After the fresh two-sample scale-in gate, Trial B:

```bash
PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-1-observations.json"
run_instance_age_trial \
  "Prewarmed=1" \
  "$PREWARM_OBSERVATIONS" \
  "$AB_DIR/hey-burst-1.out"
```

If either observer exits 2 or its JSON array is empty, call the verified restoration helper and stop the pasted function with `return 1`; do not close Cloud Shell.

- [ ] **Step 5: Add result rendering and interpretation**

Use:

```bash
jq -r '
  ["시험","instance","started_at","first_seen_at","first_response_age"],
  (.[] | ["Prewarmed=0", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)])
  | @tsv
' "$NO_PREWARM_OBSERVATIONS"

jq -r '
  .[] | ["Prewarmed=1", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv
' "$PREWARM_OBSERVATIONS"
```

Follow with these rules:

- B has an age materially above 20 seconds: explain that a prepared instance waited before first observed service, consistent with buffer residence.
- A and B are similar: explain that no buffer-residence difference was visible in this run and immediate activation may have occurred.
- Never subtract one trial's total time from the other or call B the winner.

- [ ] **Step 6: Update troubleshooting**

Replace “Prewarmed=1 is not faster” with:

```markdown
### 새 instance의 `first_response_age`가 두 시험에서 비슷함

이는 오류가 아닙니다. 이번 실행에서는 준비된 instance가 곧바로 활성화되어 응답 전 대기 구간이 짧았을 수 있습니다. 단일 실행의 총 scale-out 시간만으로 Prewarmed 효과를 단정하지 말고, 인스턴스별 `started_at`과 `first_seen_at`을 관찰 결과로 기록합니다.
```

Retain scale-in and restoration troubleshooting, and add a no-new-instance retry path.

- [ ] **Step 7: Validate Markdown and shell snippets**

Run:

```bash
python3 - <<'PY'
from pathlib import Path

for path in [Path("docs/07-autoscale.md")]:
    assert path.read_text(encoding="utf-8").count("```") % 2 == 0, path
PY
git diff --check
```

Expected: both commands exit 0.

- [ ] **Step 8: Commit**

```bash
git add docs/07-autoscale.md
git commit -m "docs: observe prewarmed instance age"
```

---

### Task 3: Integrate the Observer Into Rehearsal and Timing

**Files:**
- Modify: `scripts/rehearsal.sh:15-30`
- Modify: `scripts/rehearsal.sh:120-388`
- Modify: `README.md:3`
- Modify: `README.md:96-129`

**Interfaces:**
- Consumes: observer CLI and JSON schema from Task 1; participant flow from Task 2.
- Produces: automated A/B observation files under `$TMP_DIR`, tabular output, interpretation, verified restoration, and corrected workshop duration.

- [ ] **Step 1: Preserve process cleanup for the single burst PID**

Keep `HEY_PID` in the existing EXIT trap. Do not add a second broad trap. The observer runs in the foreground while `hey` runs in the background, so no observer PID is required.

- [ ] **Step 2: Remove obsolete rehearsal logic**

Delete:

- `wait_for_buffer_allocation`
- `measure_scale_out`
- both 60-second prime loads
- `NO_PREWARM_SECONDS` and `PREWARM_SECONDS`
- the numeric “개선” output

Do not change ARM REST setup, fresh baseline sampling, health checks, or verified restoration.

- [ ] **Step 3: Add the rehearsal trial function**

Add:

```bash
run_instance_age_trial() {
  local label=$1
  local observation_file=$2
  local hey_output=$3
  local baseline_instance observer_status=0

  baseline_instance=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
    jq -er 'select((.instance | type) == "string" and (.instance | length) > 0) | .instance')
  echo "$label baseline=$baseline_instance"

  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$hey_output" &
  HEY_PID=$!
  if python3 "$REPO_DIR/scripts/observe_instances.py" \
    --url "$APP_URL/api/info" \
    --baseline-instance "$baseline_instance" \
    --duration 180 \
    --concurrency 30 \
    --request-timeout 5 \
    --output "$observation_file"
  then
    observer_status=0
  else
    observer_status=$?
  fi
  wait "$HEY_PID" || true
  HEY_PID=""
  return "$observer_status"
}
```

- [ ] **Step 4: Run both trials with identical data collection**

Use:

```bash
NO_PREWARM_OBSERVATIONS="$TMP_DIR/prewarmed-0-observations.json"
PREWARM_OBSERVATIONS="$TMP_DIR/prewarmed-1-observations.json"
```

Run A after the Prewarmed=0 fresh baseline and B after the Prewarmed=1 fresh baseline. If either trial returns nonzero or `jq -e 'length > 0'` fails, restore, print retry guidance, and exit 1.

- [ ] **Step 5: Print observations without declaring a winner**

Print one TSV header followed by both files:

```bash
printf 'trial\tinstance\tstarted_at\tfirst_seen_at\tfirst_response_age\n'
jq -r '.[] | ["Prewarmed=0", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv' \
  "$NO_PREWARM_OBSERVATIONS"
jq -r '.[] | ["Prewarmed=1", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv' \
  "$PREWARM_OBSERVATIONS"
echo "[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다."
```

- [ ] **Step 6: Update README timing and status**

Change module 07 to:

```markdown
| 07 | 자동 스케일 | 20–30분 | 인스턴스 나이 A/B 관찰 + 시험 사이 scale-in 5–10분 |
```

Change totals to:

```markdown
| | **코어 (01–08 + 12)** | **≈ 1시간 26분–2시간 5분** | |
| | **전체 (01–12)** | **≈ 1시간 52분–2시간 44분** | |
```

Change the opening and cost prose to the same full range, and replace “라이브 Azure 리허설은 수행하지 않았으므로” with wording that states the prior latency A/B was live-tested and found variable, while the new instance-age flow still requires its final live rehearsal.

- [ ] **Step 7: Run complete local validation**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests scripts/tests
python3 -m py_compile scripts/observe_instances.py
bash -n scripts/rehearsal.sh
python3 - <<'PY'
from pathlib import Path

for path in [Path("README.md"), Path("docs/07-autoscale.md")]:
    assert path.read_text(encoding="utf-8").count("```") % 2 == 0, path
PY
git diff --check
```

Expected: 16 tests pass, Python and Bash syntax checks exit 0, Markdown fences are balanced, and `git diff --check` prints nothing.

- [ ] **Step 8: Commit**

```bash
git add scripts/rehearsal.sh README.md
git commit -m "test: rehearse prewarmed instance age"
```

---

## Final Review and Live Verification

- [ ] Generate a whole-branch review package from the merge base and run a high-capability read-only review.
- [ ] Fix all Critical and Important findings in one coordinated pass and re-review.
- [ ] Deploy the unchanged v1/v2 app code to the existing workshop app only if the observer requires no app changes; otherwise deploy both slots preserving production=v1 and staging=v2.
- [ ] Run module 07 only against `rg-appsvcworkshop-40445`, capture both observation JSON files and console output, and store the log outside git.
- [ ] Verify after the live run:

```bash
az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
az webapp config appsettings list -g "$RG" -n "$APP" \
  --query "[?name=='STARTUP_DELAY_SECONDS'] | length(@)" -o tsv
curl -fsS --max-time 10 "$APP_URL/health"
```

Expected:

```text
alwaysReady=1
prewarmed=1
0
{"status":"ok"}
```

- [ ] Push `main` only after local validation, clean review, live observation output, and restoration verification.
