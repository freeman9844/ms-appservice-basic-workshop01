# CLI Extension Placement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Centralize normal Azure CLI extension installation in module 01 and add the supplied Log Analytics query screenshot to module 08 Step 3.

**Architecture:** Documentation contract tests define the installation boundary: module 01 installs all required extensions, while modules 02 and 08 only consume them. Troubleshooting retains recovery installation commands. The supplied PNG is copied into `docs/images/` and referenced by the Step 3 expected-screen block.

**Tech Stack:** Markdown, pytest document contracts, PNG documentation asset

## Global Constraints

- `docs/01-prerequisites.md` is the only normal installation location for `application-insights`, `authV2`, and `log-analytics`.
- Troubleshooting installation commands remain available.
- Azure resource creation and query commands remain unchanged.
- Use `docs/images/08-log-analytics-kql-results.png` for the supplied screenshot.

---

### Task 1: Centralize CLI Extension Installation

**Files:**
- Create: `scripts/tests/test_observability_doc_contract.py`
- Modify: `docs/02-environment-setup.md`
- Modify: `docs/08-observability.md`

**Interfaces:**
- Consumes: module 01's existing extension installation commands.
- Produces: modules 02 and 08 with no normal-path `az extension add` commands.

- [ ] **Step 1: Write the failing document contract**

Add assertions that split each document before `## 트러블슈팅` and verify:

```python
from pathlib import Path

ROOT = Path(__file__).parents[2]
PREREQUISITES = (ROOT / "docs/01-prerequisites.md").read_text(encoding="utf-8")
ENVIRONMENT_SETUP = (ROOT / "docs/02-environment-setup.md").read_text(encoding="utf-8")
OBSERVABILITY = (ROOT / "docs/08-observability.md").read_text(encoding="utf-8")

prerequisites_main = PREREQUISITES.split("## 트러블슈팅", 1)[0]
environment_setup_main = ENVIRONMENT_SETUP.split("## 트러블슈팅", 1)[0]
observability_main = OBSERVABILITY.split("## 트러블슈팅", 1)[0]

assert "az extension add" not in environment_setup_main
assert "az extension add" not in observability_main
assert "az extension add --name application-insights" in prerequisites_main
assert "az extension add --name authV2" in prerequisites_main
assert "az extension add --name log-analytics" in prerequisites_main
```

- [ ] **Step 2: Run the contract and verify failure**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -v
```

Expected: FAIL because modules 02 and 08 still contain normal-path extension installation commands.

- [ ] **Step 3: Remove redundant normal-path installation**

In `docs/02-environment-setup.md`, remove the `application-insights` installation command and renumber the following command comments.

In `docs/08-observability.md`:

- remove the standalone `log-analytics` installation block from Step 3;
- change the Step 3 explanation to state that module 01 installed the extension;
- remove `az extension add --name application-insights` from Step 4;
- change the Step 4 explanation to state that module 01 installed the extension;
- retain troubleshooting reinstall commands.

- [ ] **Step 4: Run the contract and verify success**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add docs/02-environment-setup.md docs/08-observability.md scripts/tests/test_observability_doc_contract.py
git commit -m "Centralize Azure CLI extension setup"
```

### Task 2: Add the Step 3 Expected Screen

**Files:**
- Create: `docs/images/08-log-analytics-kql-results.png`
- Modify: `scripts/tests/test_observability_doc_contract.py`
- Modify: `docs/08-observability.md`

**Interfaces:**
- Consumes: `/mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784785153017.png`.
- Produces: a repository-local image reference in module 08 Step 3.

- [ ] **Step 1: Write the failing image contract**

Add:

```python
def test_step_three_uses_log_analytics_results_image():
    assert "![Log Analytics에서 AppServiceHTTPLogs KQL 결과 확인](images/08-log-analytics-kql-results.png)" in OBSERVABILITY
    assert (ROOT / "docs/images/08-log-analytics-kql-results.png").is_file()
```

- [ ] **Step 2: Run the image contract and verify failure**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py::test_step_three_uses_log_analytics_results_image -v
```

Expected: FAIL because the image and Markdown reference do not exist.

- [ ] **Step 3: Add the supplied image and Markdown reference**

Copy the supplied PNG to `docs/images/08-log-analytics-kql-results.png`.

Immediately after the Step 3 Portal instructions, add:

```markdown
![Log Analytics에서 AppServiceHTTPLogs KQL 결과 확인](images/08-log-analytics-kql-results.png)
```

- [ ] **Step 4: Run all tests**

Run:

```bash
python3 -m pytest scripts/tests -q
git diff --check
```

Expected: all tests pass and `git diff --check` exits 0.

- [ ] **Step 5: Commit**

```bash
git add docs/08-observability.md docs/images/08-log-analytics-kql-results.png scripts/tests/test_observability_doc_contract.py
git commit -m "Add Log Analytics query screenshot"
```
