# Easy Auth Step 1 Command Comments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Explain every command in module 09 Step 1 directly inside its executable Bash block.

**Architecture:** Add a focused module 09 document contract, then insert concise Korean comments before each logical command without changing command behavior. The comments distinguish user authentication, application credentials, and managed identity.

**Tech Stack:** Markdown, Bash, Python, pytest, Git

## Global Constraints

- Add explanations only as comments inside the Step 1 Bash block.
- Do not change any command, variable, redirect URI, audience, secret handling, or cleanup behavior.
- State that users sign in with their own Microsoft Entra accounts.
- State that the Client ID and Client Secret authenticate the application, not the user.
- State that this step does not enable an App Service managed identity.
- Keep the untracked local file `out.text` out of commits.
- After local `main` integration, push `main` to GitHub and verify local and remote SHAs match.

---

## File Structure

- `docs/09-easy-auth.md` — add command-local Korean comments to Step 1.
- `scripts/tests/test_easy_auth_doc_contract.py` — enforce the command explanations and identity boundary.

---

### Task 1: Explain Easy Auth Step 1 Commands

**Files:**
- Create: `scripts/tests/test_easy_auth_doc_contract.py`
- Modify: `docs/09-easy-auth.md:80-94`

**Interfaces:**
- Consumes: Existing Step 1 Azure CLI commands and Step 2 Easy Auth configuration.
- Produces: A self-explanatory executable block whose commands and runtime behavior remain unchanged.

- [ ] **Step 1: Write the failing module 09 contract**

Create `scripts/tests/test_easy_auth_doc_contract.py`:

```python
from pathlib import Path


ROOT = Path(__file__).parents[2]
EASY_AUTH = (ROOT / "docs/09-easy-auth.md").read_text(encoding="utf-8")


def step_one_content():
    return EASY_AUTH.split(
        "## 1단계 — Entra 앱 등록 및 시크릿 생성", 1
    )[1].split("## 2단계 — Easy Auth 구성 및 활성화", 1)[0]


def test_step_one_explains_each_identity_setup_command():
    step_one = step_one_content()

    assert "Easy Auth v2 명령을 사용하기 위한 CLI 확장" in step_one
    assert "현재 로그인한 Entra 테넌트 ID" in step_one
    assert "App Registration을 생성" in step_one
    assert "Application(Client) ID를 CLIENT_ID에 저장" in step_one
    assert "OpenID Connect ID 토큰 발급" in step_one
    assert "애플리케이션 자신을 증명할 Client Secret" in step_one
    assert "사용자는 자신의 Entra 계정으로 로그인" in step_one
    assert "Managed Identity를 생성하거나 활성화하는 단계가 아닙니다" in step_one
    assert "12 정리에서 App Registration을 삭제" in step_one
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_easy_auth_doc_contract.py::test_step_one_explains_each_identity_setup_command \
  -q
```

Expected: FAIL because the Step 1 Bash block does not contain the required comments.

- [ ] **Step 3: Add comments without changing commands**

Replace the Step 1 Bash block in `docs/09-easy-auth.md` with:

```bash
# 2단계에서 Easy Auth v2 명령을 사용하기 위한 CLI 확장을 준비합니다.
az extension add --name authV2 --upgrade --only-show-errors

# 현재 로그인한 Entra 테넌트 ID를 조회합니다.
TENANT_ID=$(az account show --query tenantId -o tsv)

# 사용자 로그인을 받을 웹앱의 App Registration을 생성합니다.
# Easy Auth 콜백 URI와 단일 테넌트 범위를 지정하고,
# Application(Client) ID를 CLIENT_ID에 저장합니다.
CLIENT_ID=$(az ad app create --display-name "auth-appsvcworkshop-$SUFFIX" \
  --web-redirect-uris "$APP_URL/.auth/login/aad/callback" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)

# Easy Auth가 로그인 사용자 클레임을 받을 수 있도록
# OpenID Connect ID 토큰 발급을 허용합니다.
az ad app update --id $CLIENT_ID --enable-id-token-issuance true

# Easy Auth가 Entra ID에 애플리케이션 자신을 증명할 Client Secret을 생성합니다.
# 사용자는 이 시크릿이 아니라 자신의 Entra 계정으로 로그인합니다.
# Managed Identity를 생성하거나 활성화하는 단계가 아닙니다.
CLIENT_SECRET=$(az ad app credential reset --id $CLIENT_ID --display-name easyauth \
  --query password -o tsv)

# 12 정리에서 App Registration을 삭제할 수 있도록 Client ID를 출력합니다.
echo "CLIENT_ID=$CLIENT_ID"   # ⚠️ 12 정리에서 필요 — 메모
```

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_easy_auth_doc_contract.py -q
python3 -m pytest scripts/tests app/tests -q
git diff --check
```

Expected: all tests PASS and `git diff --check` reports no errors.

- [ ] **Step 5: Commit**

```bash
git add docs/09-easy-auth.md scripts/tests/test_easy_auth_doc_contract.py
git commit -m "Explain Easy Auth app registration commands" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

- [ ] **Step 6: Synchronize GitHub after local main integration**

After the finishing workflow integrates the implementation into `main`, run:

```bash
git push origin main
git fetch origin main --quiet
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Expected: push succeeds and the SHA comparison exits with status 0.
