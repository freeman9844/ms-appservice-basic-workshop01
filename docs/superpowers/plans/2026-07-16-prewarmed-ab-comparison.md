# Prewarmed A/B Comparison Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the indirect Prewarmed metric observation with a sequential A/B experiment that measures how long a second active App Service instance takes to begin responding with Prewarmed set to 0 versus 1.

**Architecture:** Add an opt-in startup delay to the Flask process so cold activation is visible, then run identical low-traffic priming and burst-load phases against the same production app. Measure the first appearance of a second unique `instance` value, wait for full scale-in between trials, restore all settings, and mirror the workflow in the rehearsal script.

**Tech Stack:** Python 3.12, Flask, pytest, Bash, Azure CLI, ARM REST API, `hey`, `jq`

## Global Constraints

- Keep P0v4 and the existing ARM REST workaround for Automatic scaling.
- Use `STARTUP_DELAY_SECONDS=20` only during module 07 and remove it at the end.
- Clamp startup delay to 0–30 seconds; missing, negative, and nonnumeric values produce zero delay.
- Compare the same app, URL, load parameters, and sampling method in both trials.
- Prime both trials with `hey -z 60s -c 5 -q 2`.
- Measure burst activation with `hey -z 180s -c 100 -q 10`.
- Detect active scale-out through two unique `/api/info` `instance` values, not through `InstanceCount` alone.
- Wait for `InstanceCount=1` before each valid trial.
- Restore Prewarmed to 1 and delete `STARTUP_DELAY_SECONDS` even when a trial fails.
- Do not execute Azure mutation or load commands during implementation verification.

---

### Task 1: Add opt-in process startup delay with tests

**Files:**
- Modify: `app/app.py`
- Modify: `app/tests/test_app.py`

**Interfaces:**
- Produces: `_apply_startup_delay(raw=None) -> int`
- Behavior: reads `STARTUP_DELAY_SECONDS` when `raw` is `None`, sleeps only for a positive clamped value, and returns the applied delay.

- [ ] **Step 1: Write failing tests**

Add to `app/tests/test_app.py`:

```python
import pytest


def test_startup_delay_disabled_by_default(monkeypatch):
    calls = []
    monkeypatch.delenv("STARTUP_DELAY_SECONDS", raising=False)
    monkeypatch.setattr(app_module.time, "sleep", calls.append)

    assert app_module._apply_startup_delay() == 0
    assert calls == []


def test_startup_delay_sleeps_for_configured_seconds(monkeypatch):
    calls = []
    monkeypatch.setenv("STARTUP_DELAY_SECONDS", "20")
    monkeypatch.setattr(app_module.time, "sleep", calls.append)

    assert app_module._apply_startup_delay() == 20
    assert calls == [20]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("-1", 0), ("abc", 0), ("99", 30)],
)
def test_startup_delay_is_clamped(monkeypatch, raw, expected):
    calls = []
    monkeypatch.setattr(app_module.time, "sleep", calls.append)

    assert app_module._apply_startup_delay(raw) == expected
    assert calls == ([expected] if expected else [])
```

- [ ] **Step 2: Verify RED**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests/test_app.py -k startup_delay
```

Expected: FAIL with `AttributeError: module 'app' has no attribute '_apply_startup_delay'`.

- [ ] **Step 3: Implement the delay**

After `_clamp` in `app/app.py`, add:

```python
def _apply_startup_delay(raw=None):
    """Apply an opt-in process startup delay for the scaling workshop."""
    value = os.environ.get("STARTUP_DELAY_SECONDS") if raw is None else raw
    delay = _clamp(value, 30)
    if delay:
        time.sleep(delay)
    return delay


_apply_startup_delay()
```

The call must occur once during module import, after `_clamp` exists and before requests are served.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests
```

Expected: `13 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/app.py app/tests/test_app.py
git commit -m "feat: add configurable startup delay" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Replace module 07 metric inference with the A/B experiment

**Files:**
- Modify: `docs/07-autoscale.md`

**Interfaces:**
- Consumes: `$APP_ID`, `$APP_URL`, `hey`, `STARTUP_DELAY_SECONDS`, and the app's `/api/info` response.
- Produces: Bash helpers `latest_instance_count`, `wait_for_single_instance`, and `measure_scale_out`.

- [ ] **Step 1: Write the failing documentation check**

Run:

```bash
set -e
grep -q '^## 3단계 — Prewarmed A/B 비교 준비' docs/07-autoscale.md
grep -q 'NO_PREWARM_SECONDS' docs/07-autoscale.md
grep -q 'PREWARM_SECONDS' docs/07-autoscale.md
grep -q 'STARTUP_DELAY_SECONDS' docs/07-autoscale.md
grep -q 'measure_scale_out' docs/07-autoscale.md
```

Expected: FAIL.

- [ ] **Step 2: Add setup and reusable helpers**

Replace the current steps 3–5 with an A/B workflow. The setup must:

```bash
az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings STARTUP_DELAY_SECONDS=20 --output none

for attempt in $(seq 1 18); do
  curl -fsS "$APP_URL/health" >/dev/null && break
  sleep 5
done
curl -fsS "$APP_URL/health"
```

Define:

```bash
latest_instance_count() {
  local start
  start=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
  az monitor metrics list \
    --resource "$APP_ID" --metric InstanceCount --interval PT1M \
    --aggregation Maximum --start-time "$start" -o json |
    jq '[.value[0].timeseries[0].data[].maximum // empty] | last // 0 | floor'
}

wait_for_single_instance() {
  local count=0
  for attempt in $(seq 1 20); do
    count=$(latest_instance_count)
    echo "InstanceCount=$count"
    [ "$count" -le 1 ] && return 0
    sleep 30
  done
  return 1
}

measure_scale_out() {
  local label=$1
  local output_file=$2
  local result_var=$3
  local started elapsed unique_instances

  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$output_file" &
  local load_pid=$!
  started=$(date +%s)
  printf -v "$result_var" '%s' timeout

  for attempt in $(seq 1 36); do
    unique_instances=$(
      for i in $(seq 1 30); do
        curl -s "$APP_URL/api/info" | jq -r .instance
      done | sort -u | wc -l
    )
    elapsed=$(( $(date +%s) - started ))
    echo "$label: ${elapsed}초, 응답 인스턴스 ${unique_instances}개"
    if [ "$unique_instances" -ge 2 ]; then
      printf -v "$result_var" '%s' "$elapsed"
      break
    fi
    sleep 5
  done

  kill "$load_pid" 2>/dev/null || true
  wait "$load_pid" 2>/dev/null || true
}
```

Explain that `InstanceCount` is only used to establish a clean single-instance baseline; the measured result comes from actual response IDs.

- [ ] **Step 3: Add trial A**

Set Prewarmed to 0:

```bash
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":0}}' \
  --output none

if ! wait_for_single_instance; then
  echo "단일 인스턴스로 축소되지 않았습니다. 다음 시험 명령을 실행하지 마세요."
fi

hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > /tmp/hey-prime-0.out
measure_scale_out "Prewarmed=0" /tmp/hey-burst-0.out NO_PREWARM_SECONDS
echo "Prewarmed=0: $NO_PREWARM_SECONDS"
```

- [ ] **Step 4: Add scale-in gate and trial B**

Require a clean baseline before B:

```bash
if ! wait_for_single_instance; then
  echo "시험 A의 인스턴스가 남아 있습니다. 시험 B 명령을 실행하지 마세요."
fi

az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none

hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > /tmp/hey-prime-1.out
measure_scale_out "Prewarmed=1" /tmp/hey-burst-1.out PREWARM_SECONDS
echo "Prewarmed=1: $PREWARM_SECONDS"
```

- [ ] **Step 5: Add result interpretation and cleanup**

When both values are numeric:

```bash
if [[ "$NO_PREWARM_SECONDS" =~ ^[0-9]+$ && "$PREWARM_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "Prewarmed=0 : ${NO_PREWARM_SECONDS}초"
  echo "Prewarmed=1 : ${PREWARM_SECONDS}초"
  echo "개선         : $((NO_PREWARM_SECONDS - PREWARM_SECONDS))초"
else
  echo "한 시험이 timeout되어 시간 차이를 계산할 수 없습니다."
fi
```

Restore:

```bash
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none
az webapp config appsettings delete -g "$RG" -n "$APP" \
  --setting-names STARTUP_DELAY_SECONDS --output none
```

Document expected output as illustrative, not guaranteed. Add troubleshooting for timeout, failure to scale in, and Prewarmed=1 not being faster.

- [ ] **Step 6: Verify documentation**

Run:

```bash
set -e
grep -q '^## 3단계 — Prewarmed A/B 비교 준비' docs/07-autoscale.md
grep -q 'NO_PREWARM_SECONDS' docs/07-autoscale.md
grep -q 'PREWARM_SECONDS' docs/07-autoscale.md
grep -q 'measure_scale_out' docs/07-autoscale.md
n=$(grep -c '^```' docs/07-autoscale.md)
test $((n % 2)) -eq 0
git diff --check
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add docs/07-autoscale.md
git commit -m "docs: compare prewarmed scale-out latency" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Mirror the A/B flow in rehearsal and update timing

**Files:**
- Modify: `scripts/rehearsal.sh`
- Modify: `README.md`

**Interfaces:**
- Consumes: the helpers and result semantics from Task 2.
- Produces: automated A/B rehearsal output and restored app settings.

- [ ] **Step 1: Write failing static checks**

Run:

```bash
set -e
grep -q 'NO_PREWARM_SECONDS' scripts/rehearsal.sh
grep -q 'PREWARM_SECONDS' scripts/rehearsal.sh
grep -q 'STARTUP_DELAY_SECONDS' scripts/rehearsal.sh
grep -q '25–35분' README.md
```

Expected: FAIL.

- [ ] **Step 2: Replace the current Prewarmed metric block**

Implement the same `latest_instance_count`, `wait_for_single_instance`, and `measure_scale_out` functions in the module 07 rehearsal block. Use `$TMP_DIR` output files.

Add cleanup immediately after setting the startup delay:

```bash
restore_prewarmed_demo() {
  az rest --method patch \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
    -o none || true
  az webapp config appsettings delete -g "$RG" -n "$APP" \
    --setting-names STARTUP_DELAY_SECONDS -o none || true
}
```

Call `restore_prewarmed_demo` on every explicit failure path and once after result output. Do not add a broad `trap` that conflicts with the script's existing resource cleanup.

- [ ] **Step 3: Update README timing**

Change module 07 to:

```markdown
| 07 | 자동 스케일 | 25–35분 | Prewarmed 0/1 A/B 비교 + 시험 사이 scale-in 5–10분 |
```

- [ ] **Step 4: Verify**

Run:

```bash
bash -n scripts/rehearsal.sh
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests
git diff --check
for file in README.md docs/*.md; do
  n=$(grep -c '^```' "$file")
  test $((n % 2)) -eq 0
done
grep -q 'NO_PREWARM_SECONDS' scripts/rehearsal.sh
grep -q 'PREWARM_SECONDS' scripts/rehearsal.sh
grep -q '25–35분' README.md
```

Expected: all tests pass and all checks exit 0.

- [ ] **Step 5: Review and commit**

Run:

```bash
git --no-pager diff -- app/app.py app/tests/test_app.py docs/07-autoscale.md scripts/rehearsal.sh README.md
```

Confirm that cleanup restores Prewarmed=1 and deletes the startup delay.

Commit:

```bash
git add README.md scripts/rehearsal.sh
git commit -m "test: rehearse prewarmed latency comparison" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
