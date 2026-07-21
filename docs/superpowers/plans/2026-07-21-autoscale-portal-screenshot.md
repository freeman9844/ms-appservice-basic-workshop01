# Autoscale Portal Screenshot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the supplied Azure Portal Scale out screenshot and an accurate Portal confirmation directly after module 07 step 1's expected CLI output.

**Architecture:** Extend the existing documentation contract test so placement, visible values, wording, image path, and PNG presence are executable requirements. Then copy the supplied image into `docs/images/` and add a module 04/06-style Portal note without changing the existing autoscale commands.

**Tech Stack:** Markdown, PNG, Python `unittest`

## Global Constraints

- Insert the Portal guidance after the step 1 expected JSON output and before the existing ARM property explanation.
- Use the navigation path **Azure Portal > Web App > App Service plan > Scale out**.
- Confirm only the values visible in the screenshot: **Automatic**, **Maximum burst = 5**, and **Always ready instances = 1**.
- Do not claim that the screenshot confirms `Prewarmed = 1`; the CLI read-back remains authoritative for that value.
- Store the image at `docs/images/07-automatic-scaling-portal.png`.
- Do not change rehearsal scripts, application code, or autoscale configuration commands.

---

## File Structure

- `scripts/tests/test_autoscale_doc_contract.py`: Adds the executable contract for Portal guidance placement, copy, visible values, alt text, and image availability.
- `docs/images/07-automatic-scaling-portal.png`: Stores the supplied 1005 x 780 Azure Portal screenshot.
- `docs/07-autoscale.md`: Adds the Portal navigation guidance and screenshot immediately after step 1's expected output.

### Task 1: Add the Step 1 Portal Confirmation

**Files:**
- Modify: `scripts/tests/test_autoscale_doc_contract.py`
- Create: `docs/images/07-automatic-scaling-portal.png`
- Modify: `docs/07-autoscale.md:160-180`

**Interfaces:**
- Consumes: The existing `section(text, start, end)` helper and the supplied screenshot at `/mnt/c/Users/jungwoonlee/AppData/Local/Temp/wmux/screenshot-1784624385426.png`.
- Produces: A stable Markdown image reference to `images/07-automatic-scaling-portal.png` and a contract test named `test_step_one_shows_portal_confirmation`.

- [ ] **Step 1: Write the failing documentation contract test**

Add the image constant below the existing `DOC` constant:

```python
IMAGE = DOC.parent / "images" / "07-automatic-scaling-portal.png"
```

Add this test after `test_step_one_is_direct_cli_flow`:

```python
def test_step_one_shows_portal_confirmation():
    text = DOC.read_text(encoding="utf-8")
    step_one = section(
        text,
        "## 1단계 — Automatic scaling 활성화",
        "## 2단계 — hey 부하 도구 설치",
    )
    portal_note = (
        "> 👁️ CLI로 설정한 Automatic scaling은 "
        "**Azure Portal 관리 콘솔**에서도 확인할 수 있습니다."
    )
    portal_path = (
        "> Web App 리소스에서 **App Service plan > Scale out**로 이동하면 "
        "**Scale out method = Automatic**, **Maximum burst = 5**, "
        "**Always ready instances = 1**을 확인할 수 있습니다."
    )
    portal_disclaimer = (
        "> 이 화면에는 Prewarmed 값이 표시되지 않으므로 "
        "`Prewarmed = 1`은 위 CLI 조회 결과로 확인합니다."
    )
    image_markdown = (
        "![Azure Portal Scale out 화면에서 Automatic, Maximum burst 5, "
        "Always ready instances 1 확인]"
        "(images/07-automatic-scaling-portal.png)"
    )

    assert portal_note in step_one
    assert portal_path in step_one
    assert portal_disclaimer in step_one
    assert "🖼️ **예상 화면 — Azure Portal Automatic scaling 설정**" in step_one
    assert image_markdown in step_one
    assert step_one.index(portal_note) < step_one.index(
        "> 👁️ ARM 속성 `elasticScaleEnabled`"
    )
    assert IMAGE.is_file()
    assert IMAGE.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
```

- [ ] **Step 2: Run the targeted test and verify it fails**

Run:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_autoscale_doc_contract.py' -v
```

Expected: `test_step_one_shows_portal_confirmation` fails because the Portal note and image do not exist yet. The existing two contract tests continue to pass.

- [ ] **Step 3: Copy the supplied screenshot into the documentation image directory**

Run:

```bash
cp /mnt/c/Users/jungwoonlee/AppData/Local/Temp/wmux/screenshot-1784624385426.png \
  docs/images/07-automatic-scaling-portal.png
```

Confirm the copied file is the expected PNG:

```bash
file docs/images/07-automatic-scaling-portal.png
sha256sum docs/images/07-automatic-scaling-portal.png
```

Expected:

```text
docs/images/07-automatic-scaling-portal.png: PNG image data, 1005 x 780, 8-bit/color RGB, non-interlaced
d6e1c159a3599ddda399730791fa911735b5c93c22c9a477662f43018a1f94a7  docs/images/07-automatic-scaling-portal.png
```

- [ ] **Step 4: Add the Portal guidance after the expected JSON output**

In `docs/07-autoscale.md`, insert the following block after the closing fence of
the step 1 expected JSON output and before the ARM property explanation:

```markdown
> 👁️ CLI로 설정한 Automatic scaling은 **Azure Portal 관리 콘솔**에서도 확인할 수 있습니다.
> Web App 리소스에서 **App Service plan > Scale out**로 이동하면 **Scale out method = Automatic**, **Maximum burst = 5**, **Always ready instances = 1**을 확인할 수 있습니다.
> 이 화면에는 Prewarmed 값이 표시되지 않으므로 `Prewarmed = 1`은 위 CLI 조회 결과로 확인합니다.

🖼️ **예상 화면 — Azure Portal Automatic scaling 설정**

![Azure Portal Scale out 화면에서 Automatic, Maximum burst 5, Always ready instances 1 확인](images/07-automatic-scaling-portal.png)
```

Do not edit the two PATCH commands, the two GET commands, or their query
expressions.

- [ ] **Step 5: Run the targeted documentation contract test**

Run:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_autoscale_doc_contract.py' -v
```

Expected: all three tests pass.

- [ ] **Step 6: Check Markdown and repository integrity**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only the test, module 07 Markdown, and the new
PNG are modified or added by this task.

- [ ] **Step 7: Commit the implementation**

```bash
git add scripts/tests/test_autoscale_doc_contract.py \
  docs/07-autoscale.md \
  docs/images/07-automatic-scaling-portal.png
git commit -m "docs: add autoscale portal confirmation" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

Expected: one commit containing the documentation contract, guidance, and
screenshot asset.
