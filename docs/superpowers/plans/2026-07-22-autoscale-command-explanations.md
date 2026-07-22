# Autoscale Command Explanations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add concise purpose and confirmation guidance before every execution block in module 07 steps 3-6.

**Architecture:** Add one or two `> 👁️` sentences between each execution heading and its Bash block without changing any command. Extend the existing documentation contract with a marker-to-required-terms table so all 13 explanations remain adjacent and meaningful.

**Tech Stack:** Markdown, Python, `pytest`

## Global Constraints

- Scope is limited to the 13 labeled execution blocks in steps 3 through 6.
- Each explanation is one or two block-level sentences, not a line-by-line option reference.
- Explanations state what the command does, why it is needed, and what to confirm where applicable.
- Do not alter command syntax, parameters, output paths, expected outputs, or error-handling behavior.
- Update the common-state `REPO_DIR` note so it refers to `scripts/observe_instances.py`, not removed helpers.
- Existing direct-command and control-flow contracts must remain unchanged.

---

## File Structure

- `scripts/tests/test_autoscale_doc_contract.py`: Adds the adjacency and required-content contract for all 13 explanations.
- `docs/07-autoscale.md`: Adds concise Korean explanations and corrects the stale `REPO_DIR` note.

### Task 1: Explain Every Step 3-6 Command Block

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:20-560`

**Interfaces:**
- Consumes: Existing Markdown execution markers and the `section()` helper.
- Produces: A test helper named `explanation_before_bash()` and 13 adjacent explanations.

- [ ] **Step 1: Write the failing explanation contract**

Add this helper after `code_block_after()`:

```python
def explanation_before_bash(text, marker):
    between = text.split(marker, 1)[1].split("```bash", 1)[0]
    assert "> 👁️" in between, marker
    return between
```

Add this test after the existing step 3-6 direct-command tests:

```python
def test_steps_three_through_six_explain_each_execution_block():
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

    contracts = [
        (
            step_three,
            "🟢 **실행 — 시작 지연 설정과 결과 경로 준비**",
            ["STARTUP_DELAY_SECONDS=20", "JSON"],
        ),
        (
            step_three,
            "🟢 **실행 — 앱 준비 상태 확인**",
            ["최대 18회", "status", "ok"],
        ),
        (
            step_three,
            "🟢 **실행 — Automatic scaling 설정 재확인**",
            ["Maximum burst", "Always-ready", "Prewarmed"],
        ),
        (
            step_four,
            "🟢 **실행 — Prewarmed=0 설정**",
            ["Prewarmed", "0", "조회"],
        ),
        (
            step_four,
            "🟢 **실행 — 단일 인스턴스 기준 상태 확인**",
            ["최근 10분", "1분", "count=1"],
        ),
        (
            step_four,
            "🟢 **실행 — 시험 A 관찰**",
            ["기준 instance", "180초", "새 instance", "exit code"],
        ),
        (
            step_five,
            "🟢 **실행 — 시험 B 시작 전 단일 인스턴스 기준 상태 확인**",
            ["시험 A", "scale-in", "count=1"],
        ),
        (
            step_five,
            "🟢 **실행 — Prewarmed=1 설정**",
            ["Prewarmed", "1", "조회"],
        ),
        (
            step_five,
            "🟢 **실행 — 시험 B 관찰**",
            ["기준 instance", "180초", "새 instance", "exit code"],
        ),
        (
            step_six,
            "🟢 **실행 — 결과 표 출력**",
            ["두 JSON", "TSV", "승자"],
        ),
        (
            step_six,
            "🟢 **실행 — 모듈 기본 상태로 복원**",
            ["Always-ready=1", "Prewarmed=1", "STARTUP_DELAY_SECONDS"],
        ),
        (
            step_six,
            "🟢 **실행 — 복원 후 앱 준비 확인**",
            ["최대 18회", "status", "ok"],
        ),
        (
            step_six,
            "🟢 **실행 — 복원 상태 조회**",
            ["Plan", "Web App", "STARTUP_DELAY_SECONDS"],
        ),
    ]

    for block, marker, required_terms in contracts:
        explanation = explanation_before_bash(block, marker)
        for term in required_terms:
            assert term in explanation, (marker, term)

    assert (
        "`REPO_DIR`는 `scripts/observe_instances.py`의 경로를 고정하기 위해 "
        "여기서 항상 정의합니다."
    ) in text
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: the new test fails at the first execution marker because the required
adjacent explanation is absent.

- [ ] **Step 3: Correct the common-state note**

Replace:

```markdown
> `REPO_DIR`는 이후 모든 헬퍼가 쓰는 고정 경로이므로 여기서 항상 정의합니다.
```

with:

```markdown
> `REPO_DIR`는 `scripts/observe_instances.py`의 경로를 고정하기 위해 여기서 항상 정의합니다.
```

- [ ] **Step 4: Add the three step 3 explanations**

Insert these paragraphs immediately after their matching execution headings:

```markdown
> 👁️ 두 시험의 결과를 저장할 디렉터리와 JSON 파일 경로를 먼저 준비하고, 새 프로세스의 시작 지연을 관찰할 수 있도록 `STARTUP_DELAY_SECONDS=20`을 앱 설정에 추가합니다.
```

```markdown
> 👁️ 앱 설정 변경으로 프로세스가 재시작될 수 있으므로 `/health`를 최대 18회 확인합니다. 응답 JSON의 `status`가 `ok`일 때만 다음 명령으로 진행합니다.
```

```markdown
> 👁️ Plan에서는 Automatic scaling과 Maximum burst를, Web App에서는 Always-ready와 Prewarmed 값을 다시 조회합니다. 각각 `true`·`5`와 `1`·`1`인지 확인합니다.
```

- [ ] **Step 5: Add the three step 4 explanations**

Insert:

```markdown
> 👁️ 시험 A 조건을 만들기 위해 Always-ready는 1로 유지하고 Prewarmed만 0으로 변경합니다. PATCH 직후 같은 설정을 조회하여 `prewarmed=0`이 반영됐는지 확인합니다.
```

```markdown
> 👁️ 최근 10분의 `InstanceCount` Maximum 값을 1분 간격으로 조회합니다. 최신 행이 `count=1`이면 이전 확장이 정리된 단일 인스턴스 기준 상태입니다.
```

```markdown
> 👁️ 현재 응답 중인 기준 instance를 먼저 기록한 뒤 `hey`로 180초간 부하를 보내고, observer는 기준 instance를 제외한 새 instance의 최초 응답 시점을 JSON에 저장합니다. 완료 후 observer와 `hey`의 exit code가 모두 0인지 확인합니다.
```

- [ ] **Step 6: Add the three step 5 explanations**

Insert:

```markdown
> 👁️ 시험 A 부하로 늘어난 인스턴스가 scale-in됐는지 다시 확인합니다. 최신 메트릭이 `count=1`이 된 뒤에만 시험 B를 시작합니다.
```

```markdown
> 👁️ 시험 B 조건을 만들기 위해 Prewarmed를 1로 되돌리고 즉시 조회합니다. 출력에서 Always-ready와 Prewarmed가 모두 1인지 확인합니다.
```

```markdown
> 👁️ 시험 A와 동일하게 기준 instance를 확보한 뒤 180초 부하와 observer를 실행하며, 이번에는 새 instance 관찰 결과를 Prewarmed=1 JSON에 저장합니다. 두 프로세스의 exit code가 모두 0이어야 결과 비교를 진행합니다.
```

- [ ] **Step 7: Add the four step 6 explanations**

Insert:

```markdown
> 👁️ 두 JSON 파일을 읽어 Trial A와 B의 instance별 시작·최초 응답 시각을 하나의 TSV 표로 출력합니다. 이 표는 관찰 타임라인을 비교하기 위한 것이며 단일 실행의 속도 승자를 계산하지 않습니다.
```

Replace the existing restoration note with:

```markdown
> 👁️ Always-ready=1과 Prewarmed=1로 되돌리고, 관찰을 위해 추가한 `STARTUP_DELAY_SECONDS`를 삭제합니다. 시험 A 또는 B가 실패했을 때도 이 복원 블록을 즉시 실행할 수 있습니다.
```

Insert:

```markdown
> 👁️ 설정 복원으로 앱 프로세스가 다시 시작될 수 있으므로 `/health`를 최대 18회 확인합니다. 응답 JSON의 `status`가 `ok`가 아니면 다음 모듈로 진행하지 않습니다.
```

Insert:

```markdown
> 👁️ Plan과 Web App 설정을 차례로 조회하고 `STARTUP_DELAY_SECONDS`가 남아 있는지도 확인합니다. Automatic scaling·Maximum burst·Always-ready·Prewarmed가 종료 상태와 일치하고 설정 개수가 0이어야 합니다.
```

- [ ] **Step 8: Run targeted and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
python3 -m pytest scripts/tests -q
```

Expected: the documentation contract and complete test suite pass.

- [ ] **Step 9: Verify only explanatory content changed**

Run:

```bash
git diff --check
git diff --word-diff=porcelain -- docs/07-autoscale.md
git status --short
```

Expected: no Bash command, parameter, output path, expected output, or
error-handling line is changed; only explanatory Markdown, the stale common
note, and the contract test are modified.

- [ ] **Step 10: Commit**

```bash
git add docs/07-autoscale.md scripts/tests/test_autoscale_doc_contract.py
git commit -m "docs: explain autoscale execution commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
