# Prewarmed Observation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a short, metric-based exercise to module 07 that demonstrates a Prewarmed instance being allocated before it becomes an active request-serving instance.

**Architecture:** Extend the existing Automatic scaling workflow with a low-traffic phase and query the Web App `InstanceCount` Azure Monitor metric. Then retain the existing high-load phase to connect the metric increase to multiple application instance IDs, and mirror the sequence in the rehearsal script.

**Tech Stack:** Markdown, Bash, Azure CLI, Azure Monitor metrics, App Service Automatic scaling

## Global Constraints

- Keep the P0v4 App Service Plan and the ARM REST workaround already used for Automatic scaling.
- Use the production Web App resource ID stored in `$APP_ID`.
- Query metric name `InstanceCount`, displayed by Azure as `Automatic Scaling Instance Count`.
- Use `Maximum` aggregation and `PT1M` interval.
- Do not claim that a Prewarmed instance is serving normal traffic while it remains a buffer.
- Allow up to three minutes for metric ingestion and report an inconclusive observation honestly.
- Do not change application code, dependencies, or Maximum scale limit.
- Do not execute commands against the user's Azure resources during implementation.

---

### Task 1: Add the Prewarmed metric observation to module 07

**Files:**
- Modify: `docs/07-autoscale.md`

**Interfaces:**
- Consumes: `$APP_ID`, `$APP_URL`, and `hey` established by module 07 steps 1–2.
- Produces: A new step that exposes `LATEST_INSTANCE_COUNT` and documents how `InstanceCount` represents active plus allocated Prewarmed instances.

- [ ] **Step 1: Write the failing documentation regression check**

Run:

```bash
cd /home/jungwoonlee/appservice
set -e
grep -q '^## 3단계 — 낮은 트래픽으로 Prewarmed 할당 관찰' docs/07-autoscale.md
grep -q -- '--metric InstanceCount' docs/07-autoscale.md
grep -q 'LATEST_INSTANCE_COUNT' docs/07-autoscale.md
grep -q '최대 3분' docs/07-autoscale.md
```

Expected: FAIL because the new observation step does not exist.

- [ ] **Step 2: Add the low-traffic and metric observation step**

Insert a new step after the `hey` installation step. It must:

1. Query the last ten minutes of `InstanceCount` and show the idle baseline.
2. Run `hey -z 60s -c 5 -q 2 "$APP_URL/api/info"`.
3. Poll every 30 seconds, up to six times.
4. Requery the last ten minutes and extract the maximum integer using `jq`.
5. Stop early when the value is at least `2`.

Use this command structure:

```bash
START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Maximum \
  --start-time "$START" \
  --query "value[0].timeseries[0].data[?maximum != null].{time:timeStamp,instances:maximum}" \
  -o table

hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > /tmp/hey-prewarmed.out

LATEST_INSTANCE_COUNT=0
for attempt in $(seq 1 6); do
  START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
  LATEST_INSTANCE_COUNT=$(az monitor metrics list \
    --resource "$APP_ID" \
    --metric InstanceCount \
    --interval PT1M \
    --aggregation Maximum \
    --start-time "$START" -o json |
    jq '[.value[0].timeseries[0].data[].maximum // empty] | max // 0 | floor')
  echo "InstanceCount=$LATEST_INSTANCE_COUNT"
  [ "$LATEST_INSTANCE_COUNT" -ge 2 ] && break
  sleep 30
done
```

Explain that idle `1` represents the Always-ready instance, while `2` after traffic indicates an additional Prewarmed buffer has been allocated. State that the metric includes the Prewarmed instance and that metric ingestion can lag.

- [ ] **Step 3: Renumber and connect the existing load phases**

Rename the existing phases:

- Existing step 3 becomes `## 4단계 — 높은 부하로 Prewarmed 활성화 및 확장 관찰`.
- Existing step 4 becomes `## 5단계 — 부하 제거 및 축소(scale-in) 관찰`.

In step 4, explain that a prepared buffer can transition to an active instance and that the appearance of multiple instance IDs confirms active request distribution, not merely allocation.

- [ ] **Step 4: Add validation and troubleshooting guidance**

Add a validation subsection that reruns the `InstanceCount` query and interprets:

- `1`: only the Always-ready instance is currently allocated.
- `2` or more: active and Prewarmed allocations are included.
- No recent points: wait 30–60 seconds and retry, or inspect **Web App > Monitoring > Metrics > Automatic Scaling Instance Count**.

Add troubleshooting text that a value remaining at `1` is inconclusive rather than proof that Prewarmed failed, because low traffic and metric timing vary.

- [ ] **Step 5: Run the documentation regression check**

Run:

```bash
cd /home/jungwoonlee/appservice
set -e
grep -q '^## 3단계 — 낮은 트래픽으로 Prewarmed 할당 관찰' docs/07-autoscale.md
grep -q -- '--metric InstanceCount' docs/07-autoscale.md
grep -q 'LATEST_INSTANCE_COUNT' docs/07-autoscale.md
grep -q '최대 3분' docs/07-autoscale.md
n=$(grep -c '^```' docs/07-autoscale.md)
test $((n % 2)) -eq 0
git diff --check
```

Expected: PASS with no output except optional command echoes.

- [ ] **Step 6: Commit module documentation**

```bash
git add docs/07-autoscale.md
git commit -m "docs: demonstrate prewarmed instance allocation" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Mirror the observation in the rehearsal script

**Files:**
- Modify: `scripts/rehearsal.sh`

**Interfaces:**
- Consumes: `APP_ID`, `APP_URL`, `TMP_DIR`, and `hey` configured in the module 07 rehearsal block.
- Produces: A logged `InstanceCount` observation before the existing high-load rehearsal.

- [ ] **Step 1: Write the failing rehearsal regression check**

Run:

```bash
cd /home/jungwoonlee/appservice
set -e
grep -q 'hey-prewarmed.out' scripts/rehearsal.sh
grep -q 'InstanceCount' scripts/rehearsal.sh
grep -q 'PREWARMED_INSTANCE_COUNT' scripts/rehearsal.sh
```

Expected: FAIL because the rehearsal has no Prewarmed observation phase.

- [ ] **Step 2: Add the low-traffic phase**

Immediately before the existing `hey -z 120s` command, add:

```bash
hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > "$TMP_DIR/hey-prewarmed.out"
PREWARMED_INSTANCE_COUNT=0
for attempt in $(seq 1 6); do
  START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
  PREWARMED_INSTANCE_COUNT=$(az monitor metrics list \
    --resource "$APP_ID" --metric InstanceCount --interval PT1M \
    --aggregation Maximum --start-time "$START" -o json |
    jq '[.value[0].timeseries[0].data[].maximum // empty] | max // 0 | floor')
  echo "[07] Prewarmed 관찰 InstanceCount=$PREWARMED_INSTANCE_COUNT"
  [ "$PREWARMED_INSTANCE_COUNT" -ge 2 ] && break
  sleep 30
done
```

Do not exit when the value remains below `2`; print:

```bash
[ "$PREWARMED_INSTANCE_COUNT" -ge 2 ] ||
  echo "[07] Prewarmed 메트릭 미확인 — 메트릭 적재 지연 가능"
```

- [ ] **Step 3: Run targeted validation**

Run:

```bash
cd /home/jungwoonlee/appservice
bash -n scripts/rehearsal.sh
set -e
grep -q 'hey-prewarmed.out' scripts/rehearsal.sh
grep -q 'InstanceCount' scripts/rehearsal.sh
grep -q 'PREWARMED_INSTANCE_COUNT' scripts/rehearsal.sh
git diff --check
```

Expected: PASS.

- [ ] **Step 4: Commit rehearsal changes**

```bash
git add scripts/rehearsal.sh
git commit -m "test: rehearse prewarmed metric observation" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Verify the complete workshop change

**Files:**
- Verify: `docs/07-autoscale.md`
- Verify: `scripts/rehearsal.sh`
- Verify: `README.md`

**Interfaces:**
- Consumes: Completed Tasks 1–2.
- Produces: A verified and synchronized module 07 scenario.

- [ ] **Step 1: Update the workshop duration if required**

The scenario adds 60 seconds of traffic plus up to three minutes of metric waiting. Update the README module 07 duration row from `12–18분` to `16–22분`, and describe the added Prewarmed observation.

- [ ] **Step 2: Run final static validation**

Run:

```bash
cd /home/jungwoonlee/appservice
bash -n scripts/rehearsal.sh
git diff --check
for file in README.md docs/*.md; do
  n=$(grep -c '^```' "$file")
  test $((n % 2)) -eq 0
done
grep -q 'InstanceCount' docs/07-autoscale.md
grep -q 'PREWARMED_INSTANCE_COUNT' scripts/rehearsal.sh
```

Expected: PASS.

- [ ] **Step 3: Review the final diff**

Run:

```bash
git --no-pager diff -- README.md docs/07-autoscale.md scripts/rehearsal.sh
```

Confirm that:

- No Azure mutation command was executed during implementation.
- The low-traffic phase precedes the high-load phase.
- Metric delays are handled without false success.
- Existing P0v4 ARM REST configuration remains unchanged.

- [ ] **Step 4: Commit and push**

```bash
git add README.md docs/07-autoscale.md scripts/rehearsal.sh
git commit -m "docs: complete prewarmed observation workflow" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
git push origin main
```
