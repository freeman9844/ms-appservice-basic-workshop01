# Observability Validation Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the redundant validation section from module 08 while preserving troubleshooting.

**Architecture:** Add a document contract that defines the removal boundary, then delete the complete `## 검증` block from the participant guide. The existing Step 3 and Step 4 queries remain the operational validation path.

**Tech Stack:** Markdown, Python, pytest, Git

## Global Constraints

- Delete everything from `## 검증` through the content immediately before `## 트러블슈팅`.
- Preserve the complete `## 트러블슈팅` section.
- Do not change Step 3, Step 4, screenshots, commands, or troubleshooting content.
- Keep the untracked local file `out.text` out of commits.
- After local `main` integration, push `main` to GitHub and verify local and remote SHAs match.

---

## File Structure

- `docs/08-observability.md` — remove the repeated validation block.
- `scripts/tests/test_observability_doc_contract.py` — enforce absence of the validation headings and presence of troubleshooting.

---

### Task 1: Remove the Redundant Validation Section

**Files:**
- Modify: `scripts/tests/test_observability_doc_contract.py`
- Modify: `docs/08-observability.md:276-322`

**Interfaces:**
- Consumes: Existing Step 3 and Step 4 operational queries.
- Produces: A shorter module that transitions directly from Application Insights investigation screenshots to troubleshooting.

- [ ] **Step 1: Write the failing removal contract**

Add this test to `scripts/tests/test_observability_doc_contract.py`:

```python
def test_redundant_validation_section_is_removed():
    assert "## 검증" not in OBSERVABILITY
    assert "### HTTP 로그 KQL 확인" not in OBSERVABILITY
    assert "### App Insights 텔레메트리 확인" not in OBSERVABILITY
    assert "## 트러블슈팅" in OBSERVABILITY
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_observability_doc_contract.py::test_redundant_validation_section_is_removed \
  -q
```

Expected: FAIL because `docs/08-observability.md` still contains `## 검증`.

- [ ] **Step 3: Delete the complete validation block**

In `docs/08-observability.md`, delete this boundary and all content between it:

```markdown
## 검증
...
`AppServiceHTTPLogs`에 데이터가 조회되고 `AppRequests` 테이블에 `/api/info` 항목이 확인되면 08 모듈이 완료된 것입니다.

---
```

Keep the preceding separator after the Application map image and make the next
heading:

```markdown
## 트러블슈팅
```

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -q
python3 -m pytest scripts/tests app/tests -q
git diff --check
```

Expected: all tests PASS and `git diff --check` reports no errors.

- [ ] **Step 5: Commit**

```bash
git add docs/08-observability.md scripts/tests/test_observability_doc_contract.py
git commit -m "Remove redundant observability validation section" \
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
