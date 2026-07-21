# Automatic Scaling CLI Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make module 07 step 1 a short, sequential Azure CLI copy-paste flow while preserving the reusable safety helpers needed by the later A/B trials.

**Architecture:** Replace the step 1 function wrapper with direct `az rest` PATCH commands joined by `&&`, followed by immediate read-back commands. Move the reusable verification and Prewarmed configuration functions to the step 3 helper section, leaving the automated rehearsal unchanged.

**Tech Stack:** Markdown, Bash snippets, Azure CLI, `az rest`, pytest.

## Global Constraints

- Keep ARM API version `2024-11-01`.
- Keep Automatic scaling=true, Maximum burst=5, Always-ready=1, and Prewarmed=1.
- Keep the P0v4 SKU object unchanged.
- The Plan PATCH and Web App PATCH must be connected with `&&`.
- Step 1 must not define `verify_plan_configuration`, `set_prewarmed_configuration`, or `enable_autoscale`.
- `verify_plan_configuration` and `set_prewarmed_configuration` must be defined in step 3 before their first use.
- Do not modify `scripts/rehearsal.sh`.
- Do not run Azure mutation commands during implementation validation.

---

### Task 1: Simplify Module 07 Step 1

**Files:**
- Create: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:120-260`
- Test: `scripts/tests/test_autoscale_doc_contract.py`

**Interfaces:**
- Consumes: existing `$RG`, `$PLAN`, and `$APP` Cloud Shell variables.
- Produces: direct step 1 PATCH/read-back commands and step 3 helper definitions used by `prepare_instance_age_demo`, trial A, trial B, and restoration.

- [ ] **Step 1: Write the failing document contract tests**

Create `scripts/tests/test_autoscale_doc_contract.py`:

```python
from pathlib import Path


DOC = Path(__file__).parents[2] / "docs" / "07-autoscale.md"


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def test_step_one_is_direct_cli_flow():
    text = DOC.read_text(encoding="utf-8")
    step_one = section(
        text,
        "## 1단계 — Automatic scaling 활성화",
        "## 2단계 — hey 부하 도구 설치",
    )

    assert "verify_plan_configuration()" not in step_one
    assert "set_prewarmed_configuration()" not in step_one
    assert "enable_autoscale()" not in step_one
    assert "maximumElasticWorkerCount\":5" in step_one
    assert "preWarmedInstanceCount\":1" in step_one
    assert "--output none &&" in step_one
    assert 'echo "Automatic scaling 설정 완료"' in step_one


def test_reusable_helpers_are_defined_before_step_three_uses_them():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )

    verify_definition = step_three.index("verify_plan_configuration()")
    set_definition = step_three.index("set_prewarmed_configuration()")
    first_prepare_use = step_three.index("prepare_instance_age_demo()")

    assert verify_definition < first_prepare_use
    assert set_definition < first_prepare_use
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q scripts/tests/test_autoscale_doc_contract.py
```

Expected: both tests fail because the functions are still in step 1 and the direct `&&` flow is absent.

- [ ] **Step 3: Replace step 1 with the direct CLI block**

Use this exact execution block:

```bash
PLAN_ID=$(az appservice plan show -g $RG -n $PLAN --query id -o tsv)
APP_ID=$(az webapp show -g $RG -n $APP --query id -o tsv)

az rest --method patch \
  --uri "${PLAN_ID}?api-version=2024-11-01" \
  --body '{"sku":{"name":"P0v4","tier":"PremiumV4","size":"P0v4","family":"Pv4","capacity":1},"properties":{"elasticScaleEnabled":true,"maximumElasticWorkerCount":5}}' \
  --output none &&
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none &&
echo "Automatic scaling 설정 완료"
```

Immediately after it, retain the existing two read-back commands and expected JSON output. Add this sentence before the read-back block:

```markdown
> ⚠️ 오류가 출력되거나 `Automatic scaling 설정 완료`가 보이지 않으면 다음 단계로 진행하지 말고, `$RG`, `$PLAN`, `$APP` 값과 오류 메시지를 확인한 뒤 1단계를 다시 실행합니다.
```

- [ ] **Step 4: Move the two reusable helper definitions to step 3**

Move the existing definitions without changing their behavior:

```bash
verify_plan_configuration() {
  local settings
  if ! settings=$(az rest --method get \
    --uri "${PLAN_ID}?api-version=2024-11-01" \
    --query "properties.{elasticScaleEnabled:elasticScaleEnabled,maximumElasticWorkerCount:maximumElasticWorkerCount}" \
    --output json)
  then
    echo "Plan 설정 read-back에 실패했습니다." >&2
    return 1
  fi
  if ! jq -e '(.elasticScaleEnabled == true and .maximumElasticWorkerCount == 5)' \
    >/dev/null <<< "$settings"
  then
    echo "Plan 설정 read-back이 예상과 다릅니다: $settings" >&2
    return 1
  fi
}

set_prewarmed_configuration() {
  local expected=$1 settings
  if ! az rest --method patch \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --body "{\"properties\":{\"minimumElasticInstanceCount\":1,\"preWarmedInstanceCount\":${expected}}}" \
    --output none
  then
    echo "Always-ready/Prewarmed 설정 변경에 실패했습니다 (expected=$expected)." >&2
    return 1
  fi
  if ! settings=$(az rest --method get \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}" \
    --output json)
  then
    echo "Always-ready/Prewarmed 설정 read-back에 실패했습니다." >&2
    return 1
  fi
  if ! jq -e --argjson expected "$expected" \
    '(.alwaysReady == 1 and .prewarmed == $expected)' >/dev/null <<< "$settings"
  then
    echo "Always-ready/Prewarmed 설정 read-back이 예상과 다릅니다: $settings" >&2
    return 1
  fi
}
```

Place them in the first step 3 helper code block before `wait_for_health`, `restore_autoscale_defaults`, and `prepare_instance_age_demo`.

- [ ] **Step 5: Run focused and complete local validation**

Run:

```bash
/home/jungwoonlee/appservice/.venv/bin/pytest -q scripts/tests/test_autoscale_doc_contract.py
/home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests scripts/tests
bash -n scripts/rehearsal.sh
python3 - <<'PY'
from pathlib import Path

path = Path("docs/07-autoscale.md")
assert path.read_text(encoding="utf-8").count("```") % 2 == 0
PY
git diff --check
```

Expected: 2 focused tests pass, the complete suite passes, Bash syntax exits 0, Markdown fences are balanced, and `git diff --check` prints nothing.

- [ ] **Step 6: Commit**

```bash
git add docs/07-autoscale.md scripts/tests/test_autoscale_doc_contract.py
git commit -m "docs: simplify autoscale CLI step"
```
