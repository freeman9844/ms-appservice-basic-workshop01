# App Service Managed Application Insights Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace application-level Azure Monitor OpenTelemetry instrumentation with App Service-managed Python automatic instrumentation in module 08.

**Architecture:** The Flask application contains no Application Insights dependency or startup configuration. Module 08 and the rehearsal script enable the App Service-managed Python agent by setting the Application Insights connection string and `ApplicationInsightsAgent_EXTENSION_VERSION=~3`, then verify telemetry through the existing workspace-based `AppRequests` queries.

**Tech Stack:** Python 3.12, Flask, Linux Azure App Service, Azure CLI, Application Insights, Log Analytics, pytest, Bash

## Global Constraints

- Automatic instrumentation targets Python 3.12 deployed as code on Linux App Service.
- `APPLICATIONINSIGHTS_CONNECTION_STRING` identifies the existing Application Insights resource.
- `ApplicationInsightsAgent_EXTENSION_VERSION` must be exactly `~3`.
- The Flask application must not depend on or call `azure-monitor-opentelemetry`.
- App Service Python automatic instrumentation does not support Live Metrics.
- Keep workspace-based `AppRequests` queries for Cloud Shell compatibility.
- Do not add custom telemetry, browser instrumentation, container support, or additional OpenTelemetry packages.
- Keep the untracked local file `out.text` out of every commit.

---

## File Structure

- `app/app.py` — Flask application only; remove telemetry bootstrap logic.
- `app/requirements.txt` — application runtime dependencies; remove the Azure Monitor SDK.
- `scripts/tests/test_observability_doc_contract.py` — contract for SDK removal, managed-agent instructions, telemetry validation, and portal guidance.
- `docs/08-observability.md` — participant workflow for managed Application Insights enablement and investigation.
- `docs/images/08-application-insights-live-metrics.png` — obsolete unsupported Live Metrics screenshot; delete it.
- `scripts/tests/test_rehearsal_contract.py` — contract that automated rehearsal uses managed instrumentation.
- `scripts/rehearsal.sh` — automated equivalent of module 08.

---

### Task 1: Remove Application-Level Telemetry Instrumentation

**Files:**
- Modify: `scripts/tests/test_observability_doc_contract.py`
- Modify: `app/app.py:1-18`
- Modify: `app/requirements.txt`

**Interfaces:**
- Consumes: App Service-managed instrumentation defined by module 08.
- Produces: A Flask application with no Application Insights SDK dependency or startup call.

- [ ] **Step 1: Write the failing application instrumentation contract**

Add application file constants near the existing document constants:

```python
APP_SOURCE = (ROOT / "app/app.py").read_text(encoding="utf-8")
APP_REQUIREMENTS = (ROOT / "app/requirements.txt").read_text(encoding="utf-8")
```

Add this test:

```python
def test_application_does_not_embed_application_insights_sdk():
    assert "azure-monitor-opentelemetry" not in APP_REQUIREMENTS
    assert "configure_azure_monitor" not in APP_SOURCE
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in APP_SOURCE
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py::test_application_does_not_embed_application_insights_sdk -q
```

Expected: FAIL because the dependency and startup configuration still exist.

- [ ] **Step 3: Remove telemetry bootstrap code from the Flask app**

Replace the module docstring in `app/app.py` with:

```python
"""App Service 워크숍 데모 앱 (Flask).

- VERSION 상수는 슬롯/카나리 실습에서 sed로 치환된다 (v1 → v2).
"""
```

Delete this block:

```python
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor()
```

- [ ] **Step 4: Remove the SDK dependency**

Change `app/requirements.txt` to:

```text
flask>=3,<4
gunicorn>=22,<24
redis>=5,<6
```

- [ ] **Step 5: Run focused application and contract tests**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_observability_doc_contract.py::test_application_does_not_embed_application_insights_sdk \
  app/tests/test_app.py -q
```

Expected: all selected tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/app.py app/requirements.txt scripts/tests/test_observability_doc_contract.py
git commit -m "Remove application-level Application Insights SDK" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Document Managed Agent Enablement and Portal Investigation

**Files:**
- Modify: `scripts/tests/test_observability_doc_contract.py`
- Modify: `docs/08-observability.md`
- Delete: `docs/images/08-application-insights-live-metrics.png`

**Interfaces:**
- Consumes: Existing variables `RG`, `APP`, `LAW`, `APPI`, and `APP_URL`.
- Produces: A participant workflow that enables and validates App Service-managed Python instrumentation.

- [ ] **Step 1: Replace the Step 4 document contracts**

Rename `test_step_four_uses_application_insights_live_metrics_image` to
`test_step_four_uses_managed_python_instrumentation` and replace its body with:

```python
def test_step_four_uses_managed_python_instrumentation():
    observability_main = main_content(OBSERVABILITY)
    step_four = observability_main.split(
        "## 4단계 — App Service 관리형 Application Insights 활성화", 1
    )[1]

    assert "ApplicationInsightsAgent_EXTENSION_VERSION=~3" in step_four
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in step_four
    assert "AI_SETTINGS_OK=" in step_four
    assert "App Service Python 자동 계측" in step_four
    assert "Live Metrics를 지원하지 않습니다" in step_four
    assert "08-application-insights-live-metrics.png" not in OBSERVABILITY
```

Update the two tests that split Step 4 so they use:

```python
"## 4단계 — App Service 관리형 Application Insights 활성화"
```

Add:

```python
def test_managed_instrumentation_portal_guidance_is_explicit():
    observability_main = main_content(OBSERVABILITY)

    assert "App Service → **Application Insights**" in observability_main
    assert "Enabled" in observability_main
    assert "**Performance**" in observability_main
    assert "**Failures**" in observability_main
    assert "**Transaction search**" in observability_main
    assert "**Application map**" in observability_main
```

- [ ] **Step 2: Run the document contracts to verify they fail**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -q
```

Expected: FAIL because the document still describes SDK instrumentation and Live Metrics.

- [ ] **Step 3: Update the module goal and comparison table**

Change the opening description and goals so they state that App Service-managed
Python automatic instrumentation is enabled through Azure CLI. Set the module
end state to:

```markdown
- 모듈 종료 상태: **진단 설정 활성, App Service 관리형 Application Insights 활성**.
```

Change the Application Insights comparison cells to:

```markdown
| 수집 주체 | **Azure 플랫폼** | **App Service 관리형 Python 에이전트** |
| 활성화 방법 | 진단 설정 구성 | 앱 설정 2개로 App Service 자동 계측 활성화 |
| Linux Python 제약 | 없음 | Python 3.9–3.13 Deploy as Code 지원, 사용자 지정 컨테이너 미지원 |
```

Add this explanation below the table:

```markdown
> 👁️ 이 워크숍은 Linux App Service의 Python 3.12 Deploy as Code 환경이므로 관리형 자동 계측 지원 범위에 해당합니다. 앱 코드에는 Application Insights SDK를 포함하지 않으며, App Service가 Flask 요청을 자동 계측합니다.
```

- [ ] **Step 4: Replace Step 4 activation commands**

Rename the heading:

```markdown
## 4단계 — App Service 관리형 Application Insights 활성화
```

Replace the connection-string-only command with:

```bash
AI_CONN=$(az monitor app-insights component show \
  -g $RG --app $APPI --query connectionString -o tsv)

az webapp config appsettings set -g $RG -n $APP \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN" \
    ApplicationInsightsAgent_EXTENSION_VERSION=~3
```

Add a non-secret verification immediately after it:

```bash
AI_SETTINGS_OK=$(az webapp config appsettings list -g $RG -n $APP \
  --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING' && value!='' ||
             name=='ApplicationInsightsAgent_EXTENSION_VERSION' && value=='~3'] |
            length(@)" -o tsv)

if [ "$AI_SETTINGS_OK" -ne 2 ]; then
  echo "Application Insights 관리형 에이전트 설정 확인 실패" >&2
  false
fi
```

Explain that changing app settings restarts the app and keep the existing
`/health` condition-based wait unchanged.

- [ ] **Step 5: Replace the unsupported Live Metrics guidance**

Delete the Live Metrics expected-screen paragraph and image reference. Add:

```markdown
> 👁️ App Service Python 자동 계측은 **Live Metrics를 지원하지 않습니다**. 요청 데이터가 `AppRequests`에 적재된 뒤 App Service → **Application Insights**에서 `Enabled` 상태를 확인하고, 연결된 Application Insights 리소스의 조사 메뉴를 사용합니다.

### Application Insights에서 추가로 확인할 내용

1. **Performance** — **Investigate > Performance**에서 `GET /slow`을 선택하고 `GET /api/info`보다 긴 duration과 요청 sample을 확인합니다.
2. **Failures** — **Investigate > Failures**에서 `GET /workshop-not-found`와 HTTP 404를 확인합니다.
3. **Transaction search** — 느린 요청 sample을 열어 duration, result code, operation ID와 속성을 확인합니다.
4. **Application map** — 외부 dependency가 없으므로 앱 단일 노드만 표시되는 것이 정상입니다.
```

- [ ] **Step 6: Update troubleshooting for both required settings**

Change the `AppRequests` zero-row checklist so its first item verifies:

```bash
az webapp config appsettings list -g $RG -n $APP \
  --query "[?starts_with(name, 'APPLICATIONINSIGHTS') || name=='ApplicationInsightsAgent_EXTENSION_VERSION'].[name,value]" \
  -o table
```

State that both a nonempty connection string and
`ApplicationInsightsAgent_EXTENSION_VERSION` value `~3` are required. Keep the
restart, traffic generation, ingestion delay, and Cloud Shell audience
troubleshooting.

- [ ] **Step 7: Delete the obsolete screenshot**

Delete:

```text
docs/images/08-application-insights-live-metrics.png
```

- [ ] **Step 8: Run the document contracts**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -q
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add docs/08-observability.md \
  scripts/tests/test_observability_doc_contract.py
git add -u docs/images/08-application-insights-live-metrics.png
git commit -m "Use App Service managed Application Insights" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Align the Automated Rehearsal

**Files:**
- Modify: `scripts/tests/test_rehearsal_contract.py`
- Modify: `scripts/rehearsal.sh:644-653`

**Interfaces:**
- Consumes: `AI_CONN`, `RG`, `APP`, and `APPI` from the rehearsal environment.
- Produces: Rehearsal configuration identical to module 08 managed instrumentation.

- [ ] **Step 1: Write the failing rehearsal contract**

Add:

```python
def test_rehearsal_enables_app_service_managed_application_insights():
    observability = REHEARSAL.split(
        'echo "===== [08] 진단 설정 + KQL + App Insights', 1
    )[1].split(
        'if [ "${SKIP_OPTIONAL:-0}" != "1" ]; then', 1
    )[0]

    assert 'APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN"' in observability
    assert "ApplicationInsightsAgent_EXTENSION_VERSION=~3" in observability
    assert "AI_SETTINGS_OK=" in observability
    assert "configure_azure_monitor" not in REHEARSAL
```

- [ ] **Step 2: Run the rehearsal contract to verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_rehearsal_contract.py::test_rehearsal_enables_app_service_managed_application_insights -q
```

Expected: FAIL because the rehearsal only sets the connection string.

- [ ] **Step 3: Set both managed-agent app settings**

Replace the current app settings command in `scripts/rehearsal.sh` with:

```bash
az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings \
    APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN" \
    ApplicationInsightsAgent_EXTENSION_VERSION=~3 -o none
```

Add this verification before waiting for restart:

```bash
AI_SETTINGS_OK=$(az webapp config appsettings list -g "$RG" -n "$APP" \
  --query "[?name=='APPLICATIONINSIGHTS_CONNECTION_STRING' && value!='' ||
             name=='ApplicationInsightsAgent_EXTENSION_VERSION' && value=='~3'] |
            length(@)" -o tsv)
if [ "$AI_SETTINGS_OK" -ne 2 ]; then
  echo "[08] Application Insights 관리형 에이전트 설정 확인 실패" >&2
  exit 1
fi
```

- [ ] **Step 4: Run rehearsal contracts**

Run:

```bash
python3 -m pytest scripts/tests/test_rehearsal_contract.py -q
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/rehearsal.sh scripts/tests/test_rehearsal_contract.py
git commit -m "Align rehearsal with managed Application Insights" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Verify the Complete Change

**Files:**
- Verify: `app/app.py`
- Verify: `app/requirements.txt`
- Verify: `docs/08-observability.md`
- Verify: `scripts/rehearsal.sh`
- Verify: `scripts/tests/test_observability_doc_contract.py`
- Verify: `scripts/tests/test_rehearsal_contract.py`

**Interfaces:**
- Consumes: Deliverables from Tasks 1 through 3.
- Produces: Evidence that application behavior and workshop contracts remain valid.

- [ ] **Step 1: Confirm no SDK instrumentation remains**

Run:

```bash
rg -n "azure-monitor-opentelemetry|configure_azure_monitor" \
  app docs/08-observability.md scripts/rehearsal.sh
```

Expected: no matches and exit status 1.

- [ ] **Step 2: Confirm managed instrumentation appears in all operational paths**

Run:

```bash
rg -n "ApplicationInsightsAgent_EXTENSION_VERSION=~3" \
  docs/08-observability.md scripts/rehearsal.sh
```

Expected: one or more matches in both files.

- [ ] **Step 3: Run the full repository test suite**

Run:

```bash
python3 -m pytest scripts/tests app/tests -q
```

Expected: all tests PASS with zero failures.

- [ ] **Step 4: Check patch integrity and worktree scope**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only intended changes or commits plus the
pre-existing untracked `out.text`.

- [ ] **Step 5: Review the final commit range**

Run:

```bash
git --no-pager log --oneline -4
git --no-pager diff HEAD~3..HEAD -- \
  app/app.py app/requirements.txt docs/08-observability.md \
  scripts/rehearsal.sh scripts/tests/test_observability_doc_contract.py \
  scripts/tests/test_rehearsal_contract.py
```

Expected: the three implementation commits contain only SDK removal, managed
instrumentation documentation, and rehearsal alignment.
