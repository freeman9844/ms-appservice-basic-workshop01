# Application Insights Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand module 08 Step 4 to demonstrate route-level performance, failures, and individual transaction diagnostics with Application Insights.

**Architecture:** Reuse the existing `/api/info` and `/slow` endpoints and an intentional missing path, so no application code changes are required. Generate a controlled traffic mix, wait for `AppRequests`, summarize performance and failures with KQL, and guide Portal investigation.

**Tech Stack:** Markdown, KQL, Azure CLI, pytest document contracts

## Global Constraints

- Do not modify the Flask application.
- Generate 20 normal, 5 slow, and 5 intentional 404 requests.
- Keep the existing health gate and telemetry ingestion polling.
- Explain that Application Map is expected to contain one node and no dependencies.

---

### Task 1: Add Application Insights Diagnostic Scenarios

**Files:**
- Modify: `scripts/tests/test_observability_doc_contract.py`
- Modify: `docs/08-observability.md`

**Interfaces:**
- Consumes: existing `APP_URL`, `LAW_CID`, `APPI_ID`, and workspace-based `AppRequests`.
- Produces: a repeatable Performance, Failures, and transaction-diagnostics exercise.

- [ ] **Step 1: Write the failing document contract**

Add a test that requires:

```python
assert 'curl -fsS "$APP_URL/api/info"' in step_four
assert 'curl -fsS "$APP_URL/slow?sec=3"' in step_four
assert '"$APP_URL/workshop-not-found"' in step_four
assert "ResultCode" in step_four
assert "Success" in step_four
assert "avg(DurationMs)" in step_four
assert "percentile(DurationMs, 95)" in step_four
assert "**Performance**" in step_four
assert "**Failures**" in step_four
assert "End-to-end transaction details" in step_four
assert "Application Map" in step_four
assert "단일 노드" in step_four
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -v
```

Expected: FAIL because Step 4 only generates `/api/info` traffic.

- [ ] **Step 3: Implement the diagnostic traffic and KQL**

Replace the traffic block with:

```bash
for i in $(seq 1 20); do curl -fsS "$APP_URL/api/info" > /dev/null; done
for i in $(seq 1 5); do curl -fsS "$APP_URL/slow?sec=3" > /dev/null; done
for i in $(seq 1 5); do
  STATUS=$(curl -sS -o /dev/null -w '%{http_code}' "$APP_URL/workshop-not-found")
  [ "$STATUS" = "404" ] || { echo "예상하지 못한 상태 코드: $STATUS" >&2; false; }
done
```

Keep the ingestion polling and update the final KQL to:

```kusto
AppRequests
| where TimeGenerated > ago(30m)
| where _ResourceId =~ '$APPI_ID'
| summarize
    requests=sum(ItemCount),
    avg_ms=round(avg(DurationMs), 1),
    p95_ms=round(percentile(DurationMs, 95), 1)
  by Name, ResultCode, Success
| order by avg_ms desc
```

Add Portal instructions for Performance, Failures, End-to-end transaction details, and the expected single-node Application Map.

- [ ] **Step 4: Run all validation**

Run:

```bash
python3 -m pytest scripts/tests -q
git diff --check
```

Expected: all tests pass and `git diff --check` exits 0.

- [ ] **Step 5: Commit**

```bash
git add docs/08-observability.md scripts/tests/test_observability_doc_contract.py
git commit -m "Expand Application Insights diagnostics exercise"
```
