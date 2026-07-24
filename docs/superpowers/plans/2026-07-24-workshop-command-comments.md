# Workshop Command Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add concise Korean purpose comments to every instructional and validation Bash block across workshop modules 01–12.

**Architecture:** A structural document contract parses each module before `## 트러블슈팅` and requires every ordinary Bash block to contain at least one shell comment. Documentation changes are split into modules 01–04, 05–08, and 09–12 so each group can be reviewed and validated independently without changing commands.

**Tech Stack:** Markdown, Bash, Python, pytest, Azure CLI, Git

## Global Constraints

- Apply comments to numbered instructional steps and validation sections only.
- Do not modify Bash blocks under `## 트러블슈팅`.
- Add comments at logical operation boundaries, not before every command.
- Explain why the operation is performed and what state or evidence it changes.
- Do not change commands, options, variable names, ordering, expected output, screenshots, or learning outcomes.
- Reuse existing accurate comments instead of duplicating them.
- Confirm non-obvious Azure CLI semantics against Microsoft documentation.
- Keep the untracked local file `out.text` out of every commit.
- After local `main` integration, push `main` to GitHub and verify local and remote SHAs match.

---

## File Structure

- `scripts/tests/test_workshop_command_comments_contract.py` — structural contract for all 12 modules.
- `docs/01-prerequisites.md` through `docs/04-app-settings.md` — foundation workflow comments.
- `docs/05-deployment-slots-swap.md` through `docs/08-observability.md` — deployment and operations workflow comments.
- `docs/09-easy-auth.md` through `docs/12-cleanup.md` — optional feature and cleanup workflow comments.

---

### Task 1: Explain Modules 01–04 and Add the Comment Contract

**Files:**
- Create: `scripts/tests/test_workshop_command_comments_contract.py`
- Modify: `docs/01-prerequisites.md`
- Modify: `docs/02-environment-setup.md`
- Modify: `docs/03-deploy-code.md`
- Modify: `docs/04-app-settings.md`

**Interfaces:**
- Consumes: Foundation modules 01–04.
- Produces: `bash_blocks_before_troubleshooting(document: str) -> list[str]`, the initial four-module contract, and commented foundation workflows.

- [ ] **Step 1: Create the structural contract**

Create `scripts/tests/test_workshop_command_comments_contract.py`:

```python
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
MODULES = [
    "01-prerequisites.md",
    "02-environment-setup.md",
    "03-deploy-code.md",
    "04-app-settings.md",
]


def bash_blocks_before_troubleshooting(document):
    instructional_content = document.split("## 트러블슈팅", 1)[0]
    return re.findall(
        r"^```bash\n(.*?)\n```$",
        instructional_content,
        flags=re.MULTILINE | re.DOTALL,
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_instructional_bash_blocks_have_purpose_comments(module_name):
    document = (ROOT / "docs" / module_name).read_text(encoding="utf-8")
    uncommented = [
        block.splitlines()[0]
        for block in bash_blocks_before_troubleshooting(document)
        if not any(line.startswith("# ") for line in block.splitlines())
    ]

    assert not uncommented, (
        f"{module_name} has Bash blocks without purpose comments: {uncommented}"
    )
```

- [ ] **Step 2: Run the contract to verify it fails**

Run:

```bash
python3 -m pytest scripts/tests/test_workshop_command_comments_contract.py -q
```

Expected: FAIL for modules with uncommented instructional Bash blocks.

- [ ] **Step 3: Add module 01 logical-boundary comments**

Insert these exact comments into the matching Bash blocks without changing the commands:

```bash
# 현재 로그인한 구독과 Azure CLI 버전을 확인합니다.

# 워크숍 리소스를 만들 구독으로 전환한 뒤 선택 결과를 확인합니다.

# 워크숍에서 사용할 Application Insights, Easy Auth, Log Analytics 확장을 설치합니다.

# 워크숍 리포지토리를 복제하고 작업 디렉터리로 이동합니다.

# 구독과 리포지토리 준비 상태를 최종 확인합니다.
```

Use one comment for each of the five pre-troubleshooting Bash blocks in
`docs/01-prerequisites.md`, in document order.

- [ ] **Step 4: Add the missing module 02 validation comment**

Keep the detailed resource-creation comments already present. Add this comment
to the validation Bash block:

```bash
# Web App이 실행 중이고 올바른 호스트 이름을 사용하는지 확인합니다.
```

- [ ] **Step 5: Add module 03 logical-boundary comments**

Add these comments to the uncommented blocks:

```bash
# 이전 모듈의 리소스 변수를 복원하고 현재 Web App URL을 다시 계산합니다.

# zip 배포 시 App Service가 requirements.txt를 사용해 서버 측 Oryx 빌드를 수행하도록 설정합니다.

# Flask 앱을 zip으로 묶고 App Service에 배포합니다.

# 배포된 앱의 헬스 상태와 런타임 정보를 외부 URL에서 확인합니다.

# 새 터미널에서 요청을 보내 로그 스트림에 기록할 이벤트를 생성합니다.

# 배포 결과와 현재 인스턴스 정보를 최종 확인합니다.
```

Preserve the existing comments that distinguish log configuration from live
log streaming.

- [ ] **Step 6: Add module 04 logical-boundary comments**

Add these comments to the uncommented blocks:

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.

# WELCOME_MESSAGE 앱 설정을 추가해 런타임 환경 변수를 변경합니다.

# 변경된 메시지와 재시작된 프로세스 시각을 최종 확인합니다.
```

Keep the existing comments for the pre-change observation and the
post-restart wait.

- [ ] **Step 7: Run the module-group tests**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py \
  app/tests/test_app.py \
  -q
git diff --check
```

Expected: modules 01–04 pass the structural contract.

- [ ] **Step 8: Commit modules 01–04**

```bash
git add scripts/tests/test_workshop_command_comments_contract.py \
  docs/01-prerequisites.md docs/02-environment-setup.md \
  docs/03-deploy-code.md docs/04-app-settings.md
git commit -m "Explain foundation workshop commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Explain Modules 05–08

**Files:**
- Modify: `scripts/tests/test_workshop_command_comments_contract.py`
- Modify: `docs/05-deployment-slots-swap.md`
- Modify: `docs/06-traffic-split-canary.md`
- Modify: `docs/07-autoscale.md`
- Modify: `docs/08-observability.md`

**Interfaces:**
- Consumes: The contract from Task 1 and existing autoscale/observability contracts.
- Produces: Commented deployment-slot, canary, automatic-scaling, and observability workflows.

- [ ] **Step 1: Expand the contract to modules 05–08 and verify it fails**

Append these entries to `MODULES`:

```python
    "05-deployment-slots-swap.md",
    "06-traffic-split-canary.md",
    "07-autoscale.md",
    "08-observability.md",
```

Run:

```bash
python3 -m pytest scripts/tests/test_workshop_command_comments_contract.py -q
```

Expected: modules 05–08 FAIL because their uncommented blocks are now covered.

- [ ] **Step 2: Add module 05 slot lifecycle comments**

Add these comments to the uncommented blocks in document order:

```bash
# 이전 모듈의 리소스 변수를 복원하고 production과 staging URL을 구성합니다.

# production과 동일한 앱 구성을 가진 staging 배포 슬롯을 생성합니다.

# 소스 버전을 v2로 바꾸어 배포 패키지를 만든 뒤 로컬 소스는 v1로 복원합니다.
# v2 패키지를 staging 슬롯에 배포하고 슬롯 응답을 확인합니다.

# staging의 v2를 production으로 스왑하고 두 슬롯의 버전을 확인합니다.

# staging 슬롯에 v2가 배포되어 있는지 확인합니다.

# 롤백 후 production=v1, staging=v2 상태인지 최종 확인합니다.
```

Keep the existing rollback comment in Step 4.

- [ ] **Step 3: Add module 06 traffic-routing comments**

Add these comments to the uncommented blocks:

```bash
# 이전 모듈의 리소스 변수를 복원하고 슬롯 URL을 구성합니다.

# 라우팅 쿠키로 staging 또는 production 슬롯을 강제 선택해 각각의 버전을 확인합니다.

# 20% 분기 규칙을 제거하고 staging의 v2를 production으로 승격합니다.

# production에 남은 가중치 라우팅 규칙이 없는지 확인합니다.

# 카나리 승격 후 production이 v2를 제공하는지 확인합니다.
```

Keep the existing comments that explain the 20% split and cookie-free sampling.

- [ ] **Step 4: Add module 07 autoscale and Prewarmed comments**

Add one or more of these exact comments to every currently uncommented block,
matching the operation described by its heading:

```bash
# 관찰 스크립트를 현재 리포지토리의 절대 경로로 실행할 수 있도록 기준 경로를 저장합니다.

# 이전 모듈의 리소스 변수를 복원하고 Web App 및 Plan 리소스 ID를 조회합니다.

# P0v4 Plan에서 Automatic scaling과 최대 탄력 인스턴스 수를 설정합니다.
# Web App의 Always-ready 및 Prewarmed 인스턴스 수를 초기화합니다.

# Plan과 Web App에 적용된 Automatic scaling 값을 확인합니다.

# 동시 요청 부하를 만들 hey 도구를 설치합니다.

# hey가 현재 셸에서 실행 가능한지 확인합니다.

# A/B 결과 파일 경로를 준비하고 앱 시작 지연을 적용합니다.

# 앱 재시작 후 /health가 정상화될 때까지 기다립니다.

# 시험 A를 위해 Prewarmed 인스턴스를 0으로 설정합니다.

# 부하 시작 전 요청을 처리하는 기준 인스턴스 하나를 확인합니다.

# 시험 A의 부하, 인스턴스 관찰, InstanceCount 메트릭 수집을 동시에 실행합니다.

# 시험 B 전에 scale-in되어 기준 인스턴스 하나로 돌아왔는지 확인합니다.

# 시험 B를 위해 Prewarmed 인스턴스를 1로 설정합니다.

# 시험 B에 시험 A와 동일한 부하와 관찰 조건을 적용합니다.

# 두 시험의 InstanceCount 타임라인을 같은 형식으로 출력합니다.

# 두 시험에서 관찰된 인스턴스별 시작·최초 응답 시각을 출력합니다.

# A/B 관찰 범위와 파일 유효성을 요약해 비교 가능한 결과인지 확인합니다.
```

Do not alter observer functions, process handling, ARM API versions, or A/B
conditions.

- [ ] **Step 5: Add module 08 observability comments**

Add these comments to the uncommented blocks:

```bash
# 이전 모듈의 리소스 변수와 Application Insights 리소스 이름을 복원합니다.

# App Service의 HTTP·콘솔·플랫폼 로그와 메트릭을 Log Analytics로 전송합니다.

# Log Analytics에서 App Service HTTP 로그를 경로와 상태 코드별로 집계합니다.

# Application Insights 연결 문자열과 App Service 관리형 Python 에이전트를 활성화합니다.

# 연결 문자열을 노출하지 않고 관리형 계측에 필요한 두 설정이 존재하는지 확인합니다.

# 앱 설정 변경으로 재시작된 Web App이 다시 정상화될 때까지 기다립니다.

# 정상·느린·404 요청을 생성해 성능과 실패 분석용 텔레메트리를 만듭니다.

# AppRequests 적재를 기다린 뒤 경로별 요청 수와 응답 시간 분포를 조회합니다.
```

Keep the existing traffic-generation comment in Step 2.

- [ ] **Step 6: Run modules 05–08 contracts**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py \
  scripts/tests/test_autoscale_doc_contract.py \
  scripts/tests/test_observability_doc_contract.py \
  scripts/tests/test_rehearsal_contract.py \
  -q
git diff --check
```

Expected: modules 01–08 pass their contracts.

- [ ] **Step 7: Commit modules 05–08**

```bash
git add scripts/tests/test_workshop_command_comments_contract.py \
  docs/05-deployment-slots-swap.md \
  docs/06-traffic-split-canary.md docs/07-autoscale.md \
  docs/08-observability.md
git commit -m "Explain operations workshop commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 3: Explain Modules 09–12

**Files:**
- Modify: `scripts/tests/test_workshop_command_comments_contract.py`
- Modify: `docs/09-easy-auth.md`
- Modify: `docs/10-sidecar-option.md`
- Modify: `docs/11-autoheal-option.md`
- Modify: `docs/12-cleanup.md`

**Interfaces:**
- Consumes: The contract from Task 1 and the existing Easy Auth contract.
- Produces: Commented identity, sidecar, Auto-heal, and cleanup workflows.

- [ ] **Step 1: Expand the contract to modules 09–12 and verify it fails**

Append these entries to `MODULES`:

```python
    "09-easy-auth.md",
    "10-sidecar-option.md",
    "11-autoheal-option.md",
    "12-cleanup.md",
```

Run:

```bash
python3 -m pytest scripts/tests/test_workshop_command_comments_contract.py -q
```

Expected: modules 09–12 FAIL because their uncommented blocks are now covered.

- [ ] **Step 2: Add module 09 comments outside the completed Step 1 block**

Preserve all existing Step 1 identity comments. Add:

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.

# 인증 설정을 auth v2 스키마로 올리고 Microsoft Entra 공급자를 연결합니다.
# 미인증 브라우저 요청을 Entra 로그인 페이지로 보내도록 Easy Auth를 활성화합니다.

# API 클라이언트와 브라우저 요청이 각각 401과 302를 반환하는지 확인합니다.

# 미인증 API·브라우저 응답을 다시 확인합니다.

# Easy Auth가 활성화되고 미인증 동작이 RedirectToLoginPage인지 확인합니다.
```

- [ ] **Step 3: Add module 10 sidecar comments**

Keep existing comments for Easy Auth disablement, graceful degradation, and
visit-count checks. Add:

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.

# Redis를 보조 컨테이너로 추가하고 Web App을 재시작해 새 컨테이너 구성을 적용합니다.

# Web App에 연결된 main·sidecar 컨테이너 목록을 확인합니다.

# 여러 인스턴스에서 증가 결과가 갈라지지 않도록 현재 인스턴스 수를 확인합니다.

# 모듈 09를 수행했다면 다음 브라우저 실습을 위해 Easy Auth를 다시 활성화합니다.

# Redis sidecar가 Web App 구성에 남아 있는지 최종 확인합니다.

# 연속 요청에서 Redis의 visits 값이 증가하는지 최종 확인합니다.
```

- [ ] **Step 4: Add module 11 Auto-heal comments**

Keep the existing baseline, trigger, and recycle-observation comments. Add:

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.

# /slow와 /api/info를 직접 호출할 수 있도록 Easy Auth를 일시 비활성화합니다.

# Auto-heal 요청 횟수가 한 인스턴스에 모이도록 현재 인스턴스 수를 확인합니다.

# 3초 초과 요청이 2분 동안 5회 발생하면 프로세스를 재활용하도록 Auto-heal을 설정합니다.

# started_at 변경으로 프로세스 재활용 여부를 최종 확인합니다.
```

- [ ] **Step 5: Add module 12 cleanup comments**

Keep the existing note that the Entra app registration lives outside the
resource group. Add:

```bash
# 정리할 워크숍 리소스 그룹 이름을 이전 SUFFIX로 복원합니다.

# App Service, Plan, Log Analytics, Application Insights를 포함한 리소스 그룹 삭제를 시작합니다.

# 리소스 그룹과 선택적 Entra 앱 등록이 삭제되었는지 확인합니다.

# 리허설과 관찰 과정에서 생성한 로컬 임시 파일만 삭제합니다.

# Azure 리소스와 Entra 앱 등록이 남아 있지 않은지 최종 확인합니다.
```

- [ ] **Step 6: Run modules 09–12 contracts**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py \
  scripts/tests/test_easy_auth_doc_contract.py \
  -q
git diff --check
```

Expected: all 12 modules pass the structural comment contract.

- [ ] **Step 7: Commit modules 09–12**

```bash
git add scripts/tests/test_workshop_command_comments_contract.py \
  docs/09-easy-auth.md docs/10-sidecar-option.md \
  docs/11-autoheal-option.md docs/12-cleanup.md
git commit -m "Explain optional workshop commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 4: Verify and Synchronize the Complete Workshop

**Files:**
- Verify: `docs/01-prerequisites.md` through `docs/12-cleanup.md`
- Verify: `scripts/tests/test_workshop_command_comments_contract.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: Verified local and GitHub `main` with consistently explained executable blocks.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
python3 -m pytest scripts/tests app/tests -q
```

Expected: all tests PASS with zero failures.

- [ ] **Step 2: Verify troubleshooting blocks were not included in the contract**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py -q
```

Expected: 12 parameterized module cases PASS.

- [ ] **Step 3: Check patch integrity and scope**

Run:

```bash
git diff --check
git status --short
git --no-pager diff origin/main..HEAD -- docs scripts/tests
```

Expected: only comment additions, the new contract, design/plan commits, and
the pre-existing untracked `out.text`; no command or troubleshooting changes.

- [ ] **Step 4: Synchronize GitHub**

Run:

```bash
git fetch origin main --quiet
git rebase origin/main
python3 -m pytest scripts/tests app/tests -q
git push origin main
git fetch origin main --quiet
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Expected: any nonconflicting remote updates are preserved, tests PASS after
rebase, push succeeds, and local/remote SHAs match.
