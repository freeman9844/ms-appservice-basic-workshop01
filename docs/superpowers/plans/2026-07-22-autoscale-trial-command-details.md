# Autoscale Trial Command Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the short Trial A/B observation explanations with five-item command-flow explanations.

**Architecture:** Keep both Bash blocks byte-for-byte unchanged. Add numbered Markdown lists immediately before them and extend the existing documentation contract to require the five concepts for each trial.

**Tech Stack:** Markdown, Python, `pytest`

## Global Constraints

- Change only the explanations for `실행 — 시험 A 관찰` and `실행 — 시험 B 관찰`.
- Use five concise numbered items for each trial.
- Explain baseline capture, `hey`, `HEY_PID`, observer options/output, and exit-code handling.
- Trial B states that its flow matches Trial A and differs in the Prewarmed setting and output files.
- Do not change commands, arguments, paths, expected output, or failure behavior.

---

### Task 1: Expand Trial A and B Observation Explanations

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:338-470`

**Interfaces:**
- Consumes: Existing `explanation_before_bash()` helper and Trial A/B execution markers.
- Produces: Two five-item Markdown explanations protected by a contract test.

- [ ] **Step 1: Write the failing contract**

Add:

```python
def test_trial_observation_explanations_describe_command_flow():
    text = DOC.read_text(encoding="utf-8")
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

    contracts = [
        (
            "Trial A",
            explanation_before_bash(
                step_four, "🟢 **실행 — 시험 A 관찰**"
            ),
            [
                "`curl`과 `jq`",
                "`hey -z 180s -c 100 -q 10`",
                "`HEY_PID=$!`",
                "`--concurrency 30`",
                "`--request-timeout 5`",
                "`$NO_PREWARM_OBSERVATIONS`",
                "두 exit code가 모두 0",
            ],
        ),
        (
            "Trial B",
            explanation_before_bash(
                step_five, "🟢 **실행 — 시험 B 관찰**"
            ),
            [
                "시험 A와 같은 순서",
                "`curl`과 `jq`",
                "`hey -z 180s -c 100 -q 10`",
                "`HEY_PID=$!`",
                "`--concurrency 30`",
                "`--request-timeout 5`",
                "`$PREWARM_OBSERVATIONS`",
                "두 exit code가 모두 0",
            ],
        ),
    ]

    for label, explanation, required_terms in contracts:
        assert explanation.count("\n1. ") == 1, label
        for number in range(2, 6):
            assert f"\n{number}. " in explanation, (label, number)
        for term in required_terms:
            assert term in explanation, (label, term)
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: the new test fails because each trial currently has one paragraph,
not a five-item list.

- [ ] **Step 3: Replace the Trial A explanation**

Replace its current `> 👁️` paragraph with:

```markdown
> 👁️ **시험 A 명령 흐름**
>
> 1. `curl`과 `jq`로 `/api/info` 응답에서 현재 기준 instance ID를 가져옵니다. ID를 얻지 못하면 `if`의 `else`로 이동하므로 부하와 observer는 시작되지 않습니다.
> 2. `hey -z 180s -c 100 -q 10`은 180초 동안 최대 100개 동시 worker를 사용하고 worker당 초당 10개 요청으로 `/api/info`에 부하를 보냅니다. `&`로 백그라운드 실행하며 요약 결과는 `$AB_DIR/hey-burst-0.out`에 저장합니다.
> 3. `HEY_PID=$!`는 방금 백그라운드로 시작한 `hey`의 PID를 저장합니다. 뒤의 `wait "$HEY_PID"`가 정확한 부하 프로세스의 완료와 종료 상태를 확인할 때 사용합니다.
> 4. `observe_instances.py`는 기준 instance를 제외하고 180초 동안 `--concurrency 30`으로 응답을 관찰하며, 각 요청은 `--request-timeout 5`로 제한합니다. 발견한 새 instance의 타임라인은 `$NO_PREWARM_OBSERVATIONS` JSON에 저장합니다.
> 5. observer가 끝나면 `wait`로 `hey` 종료까지 기다리고 각각의 상태를 `OBSERVER_STATUS`와 `HEY_STATUS`에 저장합니다. 두 exit code가 모두 0일 때만 시험 A를 성공으로 보고 시험 B로 진행합니다.
```

- [ ] **Step 4: Replace the Trial B explanation**

Replace its current `> 👁️` paragraph with:

```markdown
> 👁️ **시험 B 명령 흐름**
>
> 1. 시험 A와 같은 순서로 `curl`과 `jq`를 사용해 현재 기준 instance ID를 확보합니다. 차이는 앞 단계에서 Prewarmed=1로 설정했다는 점이며, ID 확보 실패 시 부하를 시작하지 않습니다.
> 2. `hey -z 180s -c 100 -q 10`으로 시험 A와 동일한 180초 부하를 백그라운드 실행합니다. 부하 조건은 동일하게 유지하고 출력 파일만 `$AB_DIR/hey-burst-1.out`을 사용합니다.
> 3. `HEY_PID=$!`에 Trial B `hey` 프로세스의 PID를 저장하여 뒤의 `wait "$HEY_PID"`가 해당 프로세스의 완료와 종료 상태를 정확히 확인하도록 합니다.
> 4. `observe_instances.py`는 기준 instance를 제외하고 `--concurrency 30`, `--request-timeout 5` 조건으로 새 instance를 관찰합니다. 결과는 Trial B 전용 `$PREWARM_OBSERVATIONS` JSON에 저장합니다.
> 5. observer와 `hey`가 모두 끝난 뒤 두 exit code가 모두 0인지 확인합니다. 하나라도 0이 아니면 결과를 비교하지 않고 6단계 복원 명령을 실행합니다.
```

- [ ] **Step 5: Run targeted and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
python3 -m pytest scripts/tests -q
```

Expected: all tests pass.

- [ ] **Step 6: Verify command blocks are unchanged**

Run:

```bash
git diff --check
git diff --word-diff=porcelain -- docs/07-autoscale.md
```

Expected: only the two explanation paragraphs change in
`docs/07-autoscale.md`; both Bash blocks remain unchanged.

- [ ] **Step 7: Commit**

```bash
git add docs/07-autoscale.md scripts/tests/test_autoscale_doc_contract.py
git commit -m "docs: detail autoscale trial commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
