# Workshop Validation Section Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove every standalone `## 검증` section from workshop modules 01–12 while preserving validation embedded in numbered steps.

**Architecture:** Extend the existing workshop documentation contract to reject standalone validation headings in every module. Use that failing contract to drive removal from the seven remaining modules, then run all documentation and application tests before synchronizing `main`.

**Tech Stack:** Markdown, Python, pytest, Git

## Global Constraints

- Inspect `docs/01-prerequisites.md` through `docs/12-cleanup.md`.
- Delete standalone `## 검증` sections only.
- Preserve numbered-step commands, expected outputs, browser checks, and explanatory text.
- Do not change `## 트러블슈팅` or any content after it.
- Modules 07–11 already have no standalone validation section and require no documentation edit.
- Local `main` and GitHub `origin/main` must end at the same commit.

---

### Task 1: Enforce and Remove Standalone Validation Sections

**Files:**
- Modify: `scripts/tests/test_workshop_command_comments_contract.py`
- Modify: `docs/01-prerequisites.md:83-108`
- Modify: `docs/02-environment-setup.md:164-180`
- Modify: `docs/03-deploy-code.md:218-244`
- Modify: `docs/04-app-settings.md:137-170`
- Modify: `docs/05-deployment-slots-swap.md:198-240`
- Modify: `docs/06-traffic-split-canary.md:175-211`
- Modify: `docs/12-cleanup.md:126-154`

**Interfaces:**
- Consumes: Existing `MODULES` list containing all 12 workshop Markdown filenames.
- Produces: A documentation contract that rejects `## 검증` in every workshop module.

- [ ] **Step 1: Write the failing contract test**

Append this test to `scripts/tests/test_workshop_command_comments_contract.py`:

```python
@pytest.mark.parametrize("module_name", MODULES)
def test_modules_do_not_have_standalone_validation_sections(module_name):
    document = (ROOT / "docs" / module_name).read_text(encoding="utf-8")

    assert "\n## 검증\n" not in document
```

- [ ] **Step 2: Run the new test and verify the expected failure**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py::test_modules_do_not_have_standalone_validation_sections \
  -q
```

Expected: seven failures for modules 01–06 and 12. Modules 07–11 pass.

- [ ] **Step 3: Remove the standalone sections**

Delete from each listed document starting at the exact `## 검증` heading and
ending immediately before the next peer section:

| Module | Delete until |
|---|---|
| `01-prerequisites.md` | `## 트러블슈팅` |
| `02-environment-setup.md` | `## 트러블슈팅` |
| `03-deploy-code.md` | `## 트러블슈팅` |
| `04-app-settings.md` | `## 트러블슈팅` |
| `05-deployment-slots-swap.md` | `## 개념 정리` |
| `06-traffic-split-canary.md` | `## 트러블슈팅` |
| `12-cleanup.md` | `## 트러블슈팅` |

Retain the separator immediately before the following peer section. Do not
move validation commands into another section because the numbered steps
already contain the intended checks.

- [ ] **Step 4: Run the focused contracts**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_workshop_command_comments_contract.py \
  -q
```

Expected: 24 tests pass: 12 command-comment cases and 12 no-validation cases.

- [ ] **Step 5: Inspect scope and formatting**

Run:

```bash
git diff --check
git --no-pager diff -- \
  docs/01-prerequisites.md \
  docs/02-environment-setup.md \
  docs/03-deploy-code.md \
  docs/04-app-settings.md \
  docs/05-deployment-slots-swap.md \
  docs/06-traffic-split-canary.md \
  docs/12-cleanup.md \
  scripts/tests/test_workshop_command_comments_contract.py
```

Expected: only the new contract and complete `## 검증` section deletions;
numbered steps and troubleshooting content remain unchanged.

- [ ] **Step 6: Commit the implementation**

```bash
git add \
  scripts/tests/test_workshop_command_comments_contract.py \
  docs/01-prerequisites.md \
  docs/02-environment-setup.md \
  docs/03-deploy-code.md \
  docs/04-app-settings.md \
  docs/05-deployment-slots-swap.md \
  docs/06-traffic-split-canary.md \
  docs/12-cleanup.md
git commit -m "Remove redundant workshop validation sections" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Verify and Synchronize the Workshop

**Files:**
- Verify: `docs/01-prerequisites.md` through `docs/12-cleanup.md`
- Verify: `scripts/tests`
- Verify: `app/tests`

**Interfaces:**
- Consumes: Task 1 documentation and contract changes.
- Produces: Tested and synchronized local and GitHub `main`.

- [ ] **Step 1: Run the complete test suite**

Run:

```bash
python3 -m pytest scripts/tests app/tests -q
```

Expected: all tests pass with zero failures.

- [ ] **Step 2: Confirm all standalone headings are absent**

Run:

```bash
rg '^## 검증$' docs/{01,02,03,04,05,06,07,08,09,10,11,12}-*.md
```

Expected: exit code 1 with no matches.

- [ ] **Step 3: Integrate any remote changes without force pushing**

Run:

```bash
git fetch origin main --quiet
git rebase origin/main
python3 -m pytest scripts/tests app/tests -q
```

Expected: rebase succeeds and all tests pass. If a document conflict occurs,
preserve the newest remote numbered-step and troubleshooting content while
removing only the standalone `## 검증` section.

- [ ] **Step 4: Push and verify synchronization**

Run:

```bash
git push origin main
git fetch origin main --quiet
test "$(git rev-parse main)" = "$(git rev-parse origin/main)"
git status --short
```

Expected: push succeeds, local and remote SHAs match, and the worktree is
clean.
