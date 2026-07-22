# Prewarmed Benefit Interpretation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make step 6 quantify and accurately explain the observed Prewarmed consistency and tail-risk benefit.

**Architecture:** Add a dynamic `jq -s` summary after the raw timeline, then replace the two-line interpretation with four evidence-based subsections. Protect the summary, official mechanism, observed values, limitations, and alternate-result guidance with a documentation contract.

**Tech Stack:** Markdown, Bash, `jq`, Python, `pytest`

## Global Constraints

- Preserve Trial A/B execution, raw timeline, restoration, and final state.
- Interpret the current run as consistency near the approximately 20-second readiness floor and lower observed tail risk.
- Do not claim guaranteed speed, percentage improvement, or causal proof.
- State the unequal sample counts and client-observation limitations.
- Link the official Microsoft Learn Automatic scaling documentation.

---

### Task 1: Add Summary Metrics and Evidence-Based Interpretation

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Modify: `docs/07-autoscale.md:500-550`

**Interfaces:**
- Consumes: `$NO_PREWARM_OBSERVATIONS` and `$PREWARM_OBSERVATIONS`.
- Produces: A five-column summary table and four interpretation subsections.

- [ ] **Step 1: Write the failing contract**

Add:

```python
def test_step_six_explains_the_observed_prewarmed_benefit():
    text = DOC.read_text(encoding="utf-8")
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "🟢 **실행 — 모듈 기본 상태로 복원**",
    )

    required_snippets = {
        "summary heading": "🟢 **실행 — 관찰 범위 요약**",
        "dynamic summary": "jq -s -r '",
        "summary columns": (
            '["trial","samples","min_age","max_age","range"]'
        ),
        "minimum": "$ages[0]",
        "maximum": "$ages[-1]",
        "range": "($ages[-1] - $ages[0])",
        "official link": (
            "https://learn.microsoft.com/azure/app-service/"
            "manage-automatic-scaling"
        ),
        "buffer mechanism": "warmed capacity buffer",
        "readiness floor": "약 20초의 readiness floor",
        "Trial A evidence": "22–46초",
        "Trial A range": "24초",
        "Trial B evidence": "23초",
        "tail framing": "긴 지연 꼬리",
        "unequal samples": "4개 대 2개",
        "client observation": "`first_seen_at`은 클라이언트",
        "no internal label": "active/Prewarmed 상태",
        "no causality": "인과관계를 증명하지는 않습니다",
        "alternate result": "이번 실행에서는 이점이 관찰되지 않은 것",
    }

    for label, snippet in required_snippets.items():
        assert snippet in step_six, label

    expected_summary = "\n".join(
        [
            "trial\\tsamples\\tmin_age\\tmax_age\\trange",
            "Prewarmed=0\\t4\\t22\\t46\\t24",
            "Prewarmed=1\\t2\\t23\\t23\\t0",
        ]
    )
    assert expected_summary in step_six
```

- [ ] **Step 2: Verify RED**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
```

Expected: the new test fails because the summary and interpretation are absent.

- [ ] **Step 3: Add the dynamic summary command**

After the raw timeline expected output, add:

````markdown
🟢 **실행 — 관찰 범위 요약**

> 👁️ 두 JSON의 `first_response_age`를 시험별로 정렬하여 표본 수, 최솟값, 최댓값, 범위를 계산합니다. 최솟값은 준비 하한 근접성, 최댓값과 범위는 긴 지연 꼬리와 관찰값의 일관성을 보는 지표입니다.

```bash
jq -s -r '
  ["trial","samples","min_age","max_age","range"],
  (to_entries[] |
    .key as $trial_index |
    (.value | map(.first_response_age) | sort) as $ages |
    [
      (if $trial_index == 0 then "Prewarmed=0" else "Prewarmed=1" end),
      ($ages | length),
      $ages[0],
      $ages[-1],
      ($ages[-1] - $ages[0])
    ]
  ) | @tsv
' "$NO_PREWARM_OBSERVATIONS" "$PREWARM_OBSERVATIONS"
```

📋 **예상 출력** (2026-07-21 리허설 예시)

```text
trial	samples	min_age	max_age	range
Prewarmed=0	4	22	46	24
Prewarmed=1	2	23	23	0
```
````

- [ ] **Step 4: Replace the existing two interpretation bullets**

Replace them with:

```markdown
### 무엇이 Prewarmed의 이점인가

Microsoft Learn의 [Automatic scaling in Azure App Service](https://learn.microsoft.com/azure/app-service/manage-automatic-scaling)는 Prewarmed instance를 HTTP scale·activation 시 사용하는 **warmed capacity buffer**로 설명합니다. 목적은 모든 확장 시간을 일정하게 보장하는 것이 아니라, 새 처리 용량이 필요할 때 처음부터 준비하는 cold-start 부담을 줄여 확장 전환을 더 부드럽게 만드는 것입니다.

### 이번 실측에서 보인 이점

`started_at`은 인위적인 `STARTUP_DELAY_SECONDS=20` 적용 전에 기록되므로 약 20초의 readiness floor가 있습니다.

- Trial A(Prewarmed=0)는 4개 instance가 22–46초에 처음 관찰됐고, 최댓값 46초·범위 24초로 긴 지연 꼬리와 큰 편차가 있었습니다.
- Trial B(Prewarmed=1)는 2개 instance가 모두 23초에 관찰되어 readiness floor에 가까웠고, 이번 실행에서는 긴 지연 꼬리가 보이지 않았습니다.
- 가장 빠른 값은 A 22초, B 23초이므로 “Prewarmed가 가장 빠른 instance를 더 빠르게 만들었다”는 결과는 아닙니다. 이번 실측에서 보인 이점은 **새 capacity가 준비 하한 근처에서 더 일관되게 응답에 투입되고, 긴 tail이 관찰될 위험이 낮아진 모습**입니다.

운영 관점에서는 갑작스러운 HTTP 부하에서 일부 새 instance의 투입이 오래 지연되는 경우를 줄여, 기존 instance에 부하가 오래 집중되거나 응답 지연이 길어질 위험을 완화하는 것이 Prewarmed의 가치입니다.

### 이 결과가 증명하지 않는 것

- 단일 실행이며 표본 수도 4개 대 2개로 다르므로 통계적 우위나 개선 비율을 계산할 수 없습니다.
- `first_seen_at`은 클라이언트 observer가 처음 응답을 받은 시각이며 Azure 내부의 정확한 activation·routing 시각이 아닙니다.
- `AutomaticScalingInstanceCount`는 배포된 Prewarmed instance를 포함할 수 있지만, 개별 응답 instance의 active/Prewarmed 상태를 구분하지 않습니다.
- 이 시험은 사용자 요청의 latency·오류율이나 Azure 내부 allocation 이벤트를 수집하지 않습니다.

따라서 결과는 공식 warmed-buffer 메커니즘과 **일관된 방향의 외부 관찰 증거**이지만, Prewarmed가 차이를 만들었다는 인과관계를 증명하지는 않습니다.

### 다른 결과가 나오면

Trial B의 최댓값·범위가 Trial A와 비슷하거나 더 크다면 Prewarmed가 무효라는 뜻이 아니라, **이번 실행에서는 이점이 관찰되지 않은 것**입니다. 6단계로 복원하고 `InstanceCount=1` scale-in 기준 상태를 다시 확보한 뒤 같은 조건으로 반복해 여러 실행의 tail과 범위를 함께 비교합니다.
```

- [ ] **Step 5: Run targeted and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q
python3 -m pytest scripts/tests -q
```

Expected: all tests pass.

- [ ] **Step 6: Validate the summary command with rehearsal artifacts**

Run the new `jq -s` expression against:

```text
/home/jungwoonlee/.copilot/session-state/f7cbb370-388b-4811-86c0-7d97531f7500/files/prewarmed-0-observations.json
/home/jungwoonlee/.copilot/session-state/f7cbb370-388b-4811-86c0-7d97531f7500/files/prewarmed-1-observations.json
```

Expected:

```text
trial	samples	min_age	max_age	range
Prewarmed=0	4	22	46	24
Prewarmed=1	2	23	23	0
```

- [ ] **Step 7: Commit**

```bash
git add docs/07-autoscale.md scripts/tests/test_autoscale_doc_contract.py
git commit -m "docs: clarify observed Prewarmed benefit" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
