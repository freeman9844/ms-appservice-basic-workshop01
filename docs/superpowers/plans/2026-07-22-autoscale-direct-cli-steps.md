# Autoscale Steps 3-6 Direct CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Bash helper-function workflow in module 07 steps 3-6 with directly executable Azure CLI-oriented command blocks.

**Architecture:** Keep the existing Prewarmed A/B experiment and its Python observer, but expose every mutation, read-back, metric check, load process, result rendering, and restoration command directly in the workshop document. Expand the Markdown contract tests in two increments: preparation/Trial A first, then Trial B/results/restoration.

**Tech Stack:** Markdown, Bash, Azure CLI, `curl`, `jq`, `hey`, Python `pytest`

## Global Constraints

- Step 1 Automatic scaling configuration and step 2 `hey` installation remain unchanged.
- `scripts/rehearsal.sh` remains the safety-oriented automated rehearsal.
- `scripts/observe_instances.py` and the existing 180-second load/observer parameters remain unchanged.
- Steps 3 through 6 must contain no user-defined Bash functions.
- Failure guidance must direct participants to the step 6 restoration block.
- The final state remains Automatic scaling enabled, Maximum burst 5, Always-ready 1, Prewarmed 1, no `STARTUP_DELAY_SECONDS`, and a healthy application.
- Do not add a prime load or an `InstanceCount>=2` gate.

---

## File Structure

- `scripts/tests/test_autoscale_doc_contract.py`: Defines executable contracts for the direct-command structure and prevents helper functions from returning.
- `docs/07-autoscale.md`: Replaces helper definitions and calls with direct commands while preserving the experiment and expected output.

### Task 1: Convert Preparation and Trial A

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:212-638`

**Interfaces:**
- Consumes: Existing `section()` test helper, `$RG`, `$APP`, `$APP_ID`, `$PLAN_ID`, `$APP_URL`, and `$REPO_DIR` initialized earlier in the module.
- Produces: `$AB_DIR`, `$NO_PREWARM_OBSERVATIONS`, `$PREWARM_OBSERVATIONS`, `BASELINE_INSTANCE`, `HEY_PID`, `OBSERVER_STATUS`, and `HEY_STATUS` for direct use by steps 4-6.

- [ ] **Step 1: Replace the obsolete helper-order contract with failing direct-command contracts**

Add `import re` above the existing `Path` import:

```python
import re
from pathlib import Path
```

Replace `test_reusable_helpers_are_defined_before_step_three_uses_them` with:

```python
FUNCTION_DEFINITION = re.compile(
    r"(?m)^[A-Za-z_][A-Za-z0-9_]*\(\) \{"
)


def test_steps_three_and_four_use_direct_commands():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )
    step_four = section(
        text,
        "## 4단계 — 시험 A",
        "## 5단계 — scale-in 게이트 후 시험 B",
    )

    assert FUNCTION_DEFINITION.search(step_three) is None
    assert FUNCTION_DEFINITION.search(step_four) is None

    preparation_snippets = {
        "startup delay mutation": (
            'az webapp config appsettings set -g "$RG" -n "$APP" \\\n'
            "  --settings STARTUP_DELAY_SECONDS=20 --output none"
        ),
        "health polling": "for attempt in $(seq 1 18); do",
        "plan read-back": (
            '--query "properties.{automaticScaling:elasticScaleEnabled,'
            'maximumBurst:maximumElasticWorkerCount}"'
        ),
        "web app read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "trial A output": (
            'NO_PREWARM_OBSERVATIONS="$AB_DIR/'
            'prewarmed-0-observations.json"'
        ),
        "trial B output": (
            'PREWARM_OBSERVATIONS="$AB_DIR/'
            'prewarmed-1-observations.json"'
        ),
    }
    for label, snippet in preparation_snippets.items():
        assert snippet in step_three, label

    trial_a_snippets = {
        "Prewarmed zero PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":0}}\''
        ),
        "Prewarmed read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "single instance metric": "az monitor metrics list",
        "baseline instance": "BASELINE_INSTANCE=$(curl -fsS --max-time 10",
        "load command": 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"',
        "observer command": (
            'python3 "$REPO_DIR/scripts/observe_instances.py"'
        ),
        "load wait": 'wait "$HEY_PID"',
        "observer exit": "OBSERVER_STATUS=$?",
        "load exit": "HEY_STATUS=$?",
        "restoration guidance": "6단계의 **모듈 기본 상태로 복원**",
    }
    for label, snippet in trial_a_snippets.items():
        assert snippet in step_four, label
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: the new test fails because steps 3 and 4 still define and call helper
functions.

- [ ] **Step 3: Replace step 3 helper definitions with direct preparation commands**

Keep the existing two introductory paragraphs in step 3. Replace everything
from `🟢 **실행 — 기준 상태 확인과 A/B 관찰용 헬퍼 정의**` through the current
step 3 expected output with:

````markdown
🟢 **실행 — 시작 지연 설정과 결과 경로 준비**

```bash
AB_DIR="${AB_DIR:-$HOME/appservice-prewarmed-ab}"
mkdir -p "$AB_DIR"
NO_PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-0-observations.json"
PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-1-observations.json"

az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings STARTUP_DELAY_SECONDS=20 --output none &&
echo "STARTUP_DELAY_SECONDS=20 설정 완료"
```

> ⚠️ 오류가 출력되거나 완료 메시지가 보이지 않으면 다음 단계로 진행하지 마세요. 설정을 변경한 뒤 중단해야 한다면 6단계의 **모듈 기본 상태로 복원** 명령을 실행합니다.

🟢 **실행 — 앱 준비 상태 확인**

```bash
for attempt in $(seq 1 18); do
  HEALTH_BODY=$(curl -fsS --max-time 10 "$APP_URL/health" 2>/dev/null || true)
  if jq -e '.status == "ok"' >/dev/null 2>&1 <<< "$HEALTH_BODY"; then
    printf '%s\n' "$HEALTH_BODY"
    break
  fi
  if [ "$attempt" -eq 18 ]; then
    echo "/health 확인 실패: 6단계의 복원 명령을 실행하세요." >&2
    false
  fi
  sleep 5
done
```

📋 **예상 출력**

```json
{"status":"ok"}
```

🟢 **실행 — Automatic scaling 설정 재확인**

```bash
az rest --method get \
  --uri "${PLAN_ID}?api-version=2024-11-01" \
  --query "properties.{automaticScaling:elasticScaleEnabled,maximumBurst:maximumElasticWorkerCount}"

az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "automaticScaling": true,
  "maximumBurst": 5
}
{
  "alwaysReady": 1,
  "prewarmed": 1
}
```

> 👁️ `InstanceCount` 메트릭은 시험 시작 전·시험 사이에 단일 인스턴스 기준 상태를 확인하는 용도로만 사용합니다. 실제 관찰값은 `observe_instances.py`가 저장하는 `started_at`, `first_seen_at`, `first_response_age`입니다.
````

- [ ] **Step 4: Replace Trial A's function with direct commands**

Keep the existing step 4 introduction. Replace its execution block with:

````markdown
🟢 **실행 — Prewarmed=0 설정**

```bash
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":0}}' \
  --output none &&
az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "alwaysReady": 1,
  "prewarmed": 0
}
```

🟢 **실행 — 단일 인스턴스 기준 상태 확인**

```bash
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Maximum \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --query "value[0].timeseries[0].data[?maximum != null].{time:timeStamp,count:maximum}" \
  -o table
```

> 👁️ 최신 행의 `count`가 `1`인지 확인합니다. 아직 2 이상이면 30초 정도 기다린 뒤 같은 조회 명령을 다시 실행합니다.

🟢 **실행 — 시험 A 관찰**

```bash
BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
  jq -er 'select((.instance | type) == "string" and (.instance | test("\\S"))) | .instance') &&
echo "Prewarmed=0 기준 instance: $BASELINE_INSTANCE"

hey -z 180s -c 100 -q 10 "$APP_URL/api/info" \
  > "$AB_DIR/hey-burst-0.out" &
HEY_PID=$!

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

echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS"
if [ "$OBSERVER_STATUS" -ne 0 ] || [ "$HEY_STATUS" -ne 0 ]; then
  echo "시험 A 실패: 다음 시험으로 진행하지 말고 6단계의 복원 명령을 실행하세요." >&2
  false
fi
```

> ⚠️ `observer exit=0, hey exit=0`일 때만 시험 B로 진행합니다. observer가 2로 종료되면 새 instance를 관찰하지 못한 것이므로 복원 후 3단계부터 다시 시도합니다.
````

Retain the existing Trial A expected output and its explanation.

- [ ] **Step 5: Run the targeted contract test**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: all current tests pass.

- [ ] **Step 6: Commit preparation and Trial A**

```bash
git add scripts/tests/test_autoscale_doc_contract.py docs/07-autoscale.md
git commit -m "docs: simplify autoscale preparation and trial A" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

### Task 2: Convert Trial B, Results, and Restoration

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:640-830`

**Interfaces:**
- Consumes: `$AB_DIR`, `$NO_PREWARM_OBSERVATIONS`, and `$PREWARM_OBSERVATIONS` established by step 3.
- Produces: A direct Trial B observation file, combined TSV output, and the documented module default state.

- [ ] **Step 1: Write failing contracts for steps 5 and 6**

Add:

```python
def test_steps_five_and_six_use_direct_commands():
    text = DOC.read_text(encoding="utf-8")
    step_five = section(
        text,
        "## 5단계 — scale-in 게이트 후 시험 B",
        "## 6단계 — 결과 해석 및 정리",
    )
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 검증",
    )

    assert FUNCTION_DEFINITION.search(step_five) is None
    assert FUNCTION_DEFINITION.search(step_six) is None

    trial_b_snippets = {
        "single instance metric": "az monitor metrics list",
        "Prewarmed one PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":1}}\''
        ),
        "baseline instance": "BASELINE_INSTANCE=$(curl -fsS --max-time 10",
        "load output": '"$AB_DIR/hey-burst-1.out"',
        "observer output": '--output "$PREWARM_OBSERVATIONS"',
        "load command": 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"',
        "observer command": (
            'python3 "$REPO_DIR/scripts/observe_instances.py"'
        ),
        "load wait": 'wait "$HEY_PID"',
        "restoration guidance": "6단계의 복원 명령",
    }
    for label, snippet in trial_b_snippets.items():
        assert snippet in step_five, label

    assert step_five.count(
        'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
    ) == 1
    assert "prime_url" not in step_five
    assert "wait_for_prewarmed" not in step_five

    restoration_snippets = {
        "Trial A result": '"$NO_PREWARM_OBSERVATIONS"',
        "Trial B result": '"$PREWARM_OBSERVATIONS"',
        "default PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":1}}\''
        ),
        "startup delay deletion": (
            "az webapp config appsettings delete"
        ),
        "health polling": "for attempt in $(seq 1 18); do",
        "plan read-back": (
            '--query "properties.{automaticScaling:elasticScaleEnabled,'
            'maximumBurst:maximumElasticWorkerCount}"'
        ),
        "web read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "startup delay read-back": (
            '--query "[?name==\'STARTUP_DELAY_SECONDS\'] | length(@)"'
        ),
    }
    for label, snippet in restoration_snippets.items():
        assert snippet in step_six, label
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: the new test fails because steps 5 and 6 still define helper
functions.

- [ ] **Step 3: Replace Trial B's function with direct commands**

Keep the existing step 5 introduction and expected output. Replace its execution
block with:

````markdown
🟢 **실행 — 시험 B 시작 전 단일 인스턴스 기준 상태 확인**

```bash
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Maximum \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --query "value[0].timeseries[0].data[?maximum != null].{time:timeStamp,count:maximum}" \
  -o table
```

> 👁️ 최신 행의 `count`가 `1`이 될 때까지 30초 정도 간격으로 같은 명령을 다시 실행합니다. 별도의 prime 부하나 `InstanceCount>=2` 확인은 하지 않습니다.

🟢 **실행 — Prewarmed=1 설정**

```bash
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none &&
az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "alwaysReady": 1,
  "prewarmed": 1
}
```

🟢 **실행 — 시험 B 관찰**

```bash
BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
  jq -er 'select((.instance | type) == "string" and (.instance | test("\\S"))) | .instance') &&
echo "Prewarmed=1 기준 instance: $BASELINE_INSTANCE"

hey -z 180s -c 100 -q 10 "$APP_URL/api/info" \
  > "$AB_DIR/hey-burst-1.out" &
HEY_PID=$!

python3 "$REPO_DIR/scripts/observe_instances.py" \
  --url "$APP_URL/api/info" \
  --baseline-instance "$BASELINE_INSTANCE" \
  --duration 180 \
  --concurrency 30 \
  --request-timeout 5 \
  --output "$PREWARM_OBSERVATIONS"
OBSERVER_STATUS=$?

wait "$HEY_PID"
HEY_STATUS=$?

echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS"
if [ "$OBSERVER_STATUS" -ne 0 ] || [ "$HEY_STATUS" -ne 0 ]; then
  echo "시험 B 실패: 결과를 해석하지 말고 6단계의 복원 명령을 실행하세요." >&2
  false
fi
```

> ⚠️ `observer exit=0, hey exit=0`일 때만 결과를 해석합니다.
````

- [ ] **Step 4: Replace result and restoration functions with direct commands**

Replace the step 6 result execution block with:

````markdown
🟢 **실행 — 결과 표 출력**

```bash
jq -r '
  ["trial","instance","started_at","first_seen_at","first_response_age"],
  (.[] | ["Prewarmed=0", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)])
  | @tsv
' "$NO_PREWARM_OBSERVATIONS"

jq -r '
  .[] | ["Prewarmed=1", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv
' "$PREWARM_OBSERVATIONS"

echo "[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다."
```
````

Keep the expected result table and interpretation. Replace the restoration
function and call with:

````markdown
🟢 **실행 — 모듈 기본 상태로 복원**

> 👁️ 시험 A 또는 B가 실패했을 때도 아래 블록을 즉시 실행할 수 있습니다.

```bash
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none &&
az webapp config appsettings delete -g "$RG" -n "$APP" \
  --setting-names STARTUP_DELAY_SECONDS --output none &&
echo "Always-ready=1, Prewarmed=1 복원 및 STARTUP_DELAY_SECONDS 삭제 완료"
```

🟢 **실행 — 복원 후 앱 준비 확인**

```bash
for attempt in $(seq 1 18); do
  HEALTH_BODY=$(curl -fsS --max-time 10 "$APP_URL/health" 2>/dev/null || true)
  if jq -e '.status == "ok"' >/dev/null 2>&1 <<< "$HEALTH_BODY"; then
    printf '%s\n' "$HEALTH_BODY"
    break
  fi
  if [ "$attempt" -eq 18 ]; then
    echo "/health 확인 실패: 다음 모듈로 진행하지 마세요." >&2
    false
  fi
  sleep 5
done
```

🟢 **실행 — 복원 상태 조회**

```bash
az rest --method get \
  --uri "${PLAN_ID}?api-version=2024-11-01" \
  --query "properties.{automaticScaling:elasticScaleEnabled,maximumBurst:maximumElasticWorkerCount}"

az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"

az webapp config appsettings list -g "$RG" -n "$APP" \
  --query "[?name=='STARTUP_DELAY_SECONDS'] | length(@)" -o tsv
```
````

Retain the existing note describing the final module state. Move the three
existing expected outputs for Plan state, Web App state, and startup-setting
count so they appear immediately after the matching commands in the new
`복원 상태 조회` block. Delete the later `### 정리 상태 확인` subsection, which
would otherwise duplicate those commands and outputs. Keep `### A/B 관찰 파일
확인` unchanged.

- [ ] **Step 5: Run targeted and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
python3 -m pytest scripts/tests -q
```

Expected: all documentation contract tests and the complete test suite pass.

- [ ] **Step 6: Verify the final diff**

Run:

```bash
git diff --check
git status --short
```

Expected: only `docs/07-autoscale.md` and
`scripts/tests/test_autoscale_doc_contract.py` are modified by the
implementation.

- [ ] **Step 7: Commit Trial B and restoration**

```bash
git add scripts/tests/test_autoscale_doc_contract.py docs/07-autoscale.md
git commit -m "docs: simplify autoscale trial B and cleanup" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
