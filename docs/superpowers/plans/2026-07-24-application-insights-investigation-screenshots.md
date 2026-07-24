# Application Insights Investigation Screenshots Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the four supplied Azure Portal screenshots as item-specific sample outputs in module 08 Step 4.

**Architecture:** Copy each unmodified attachment into `docs/images/` with a stable semantic filename. Reference each image immediately after its matching Performance, Failures, Transaction search, or Application map explanation and protect the mapping with a document contract test.

**Tech Stack:** Markdown, PNG, Python, pytest

## Global Constraints

- Preserve the supplied screenshots without cropping, resizing, annotation, or recompression.
- Use the attachment order as the authoritative Performance, Failures, transaction details, and Application map mapping.
- Place each image immediately after its corresponding numbered item.
- Keep all module commands and Application Insights behavior unchanged.
- Keep the untracked local file `out.text` out of the commit.

---

## File Structure

- `docs/images/08-application-insights-performance.png` — Performance sample output.
- `docs/images/08-application-insights-failures.png` — Failures sample output.
- `docs/images/08-application-insights-transaction-details.png` — End-to-end transaction details sample output.
- `docs/images/08-application-insights-application-map.png` — Application map sample output.
- `docs/08-observability.md` — item-local image references and captions.
- `scripts/tests/test_observability_doc_contract.py` — exact reference and file existence contract.

---

### Task 1: Add Investigation Sample Outputs

**Files:**
- Create: `docs/images/08-application-insights-performance.png`
- Create: `docs/images/08-application-insights-failures.png`
- Create: `docs/images/08-application-insights-transaction-details.png`
- Create: `docs/images/08-application-insights-application-map.png`
- Modify: `docs/08-observability.md`
- Modify: `scripts/tests/test_observability_doc_contract.py`

**Interfaces:**
- Consumes: Four PNG attachments in the order supplied by the user.
- Produces: Four stable Markdown image references backed by repository image files.

- [ ] **Step 1: Write the failing screenshot contract**

Add this test to `scripts/tests/test_observability_doc_contract.py`:

```python
def test_step_four_uses_application_insights_investigation_images():
    image_references = {
        "08-application-insights-performance.png": (
            "![Application Insights Performance에서 GET /slow의 "
            "3초 응답 시간 확인]"
        ),
        "08-application-insights-failures.png": (
            "![Application Insights Failures에서 "
            "GET /workshop-not-found 404 확인]"
        ),
        "08-application-insights-transaction-details.png": (
            "![Application Insights End-to-end transaction details에서 "
            "GET /slow 요청 확인]"
        ),
        "08-application-insights-application-map.png": (
            "![Application Insights Application map에서 "
            "App Service 애플리케이션 노드 확인]"
        ),
    }

    for filename, alt_text in image_references.items():
        assert f"{alt_text}(images/{filename})" in OBSERVABILITY
        assert (ROOT / "docs/images" / filename).is_file()
```

- [ ] **Step 2: Run the contract to verify it fails**

Run:

```bash
python3 -m pytest \
  scripts/tests/test_observability_doc_contract.py::test_step_four_uses_application_insights_investigation_images \
  -q
```

Expected: FAIL because the image references and repository files do not exist.

- [ ] **Step 3: Copy the four original PNG attachments**

Run:

```bash
cp /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852867109.png \
  docs/images/08-application-insights-performance.png
cp /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852896900.png \
  docs/images/08-application-insights-failures.png
cp /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852940641.png \
  docs/images/08-application-insights-transaction-details.png
cp /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852979967.png \
  docs/images/08-application-insights-application-map.png
chmod 0644 docs/images/08-application-insights-*.png
```

- [ ] **Step 4: Add each image below its matching numbered item**

Change the four-item section in `docs/08-observability.md` to:

```markdown
1. **Performance** — **Investigate > Performance**에서 `GET /slow`을 선택하고 `GET /api/info`보다 약 3초 긴 duration과 요청 sample을 확인합니다.

   ![Application Insights Performance에서 GET /slow의 3초 응답 시간 확인](images/08-application-insights-performance.png)

2. **Failures** — **Investigate > Failures**에서 `GET /workshop-not-found`와 HTTP 404를 확인합니다. 의도한 실패이므로 워크숍 앱 장애가 아닙니다.

   ![Application Insights Failures에서 GET /workshop-not-found 404 확인](images/08-application-insights-failures.png)

3. **Transaction search** — 느린 요청 sample을 열어 **End-to-end transaction details**의 duration, result code, operation ID와 속성을 확인합니다.

   ![Application Insights End-to-end transaction details에서 GET /slow 요청 확인](images/08-application-insights-transaction-details.png)

4. **Application map** — 외부 HTTP·데이터베이스 dependency가 없으므로 앱 **단일 노드**만 표시되는 것이 정상입니다.

   ![Application Insights Application map에서 App Service 애플리케이션 노드 확인](images/08-application-insights-application-map.png)
```

- [ ] **Step 5: Verify image identity and permissions**

Run:

```bash
sha256sum \
  /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852867109.png \
  docs/images/08-application-insights-performance.png
sha256sum \
  /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852896900.png \
  docs/images/08-application-insights-failures.png
sha256sum \
  /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852940641.png \
  docs/images/08-application-insights-transaction-details.png
sha256sum \
  /mnt/c/Users/JUNGWO~1/AppData/Local/Temp/wmux/screenshot-1784852979967.png \
  docs/images/08-application-insights-application-map.png
stat -c '%a %n' docs/images/08-application-insights-*.png
```

Expected: each source/destination pair has the same SHA-256 value and every
destination has permission `644`.

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
python3 -m pytest scripts/tests/test_observability_doc_contract.py -q
python3 -m pytest scripts/tests app/tests -q
git diff --check
```

Expected: all tests PASS and `git diff --check` reports no errors.

- [ ] **Step 7: Commit**

```bash
git add docs/08-observability.md \
  docs/images/08-application-insights-performance.png \
  docs/images/08-application-insights-failures.png \
  docs/images/08-application-insights-transaction-details.png \
  docs/images/08-application-insights-application-map.png \
  scripts/tests/test_observability_doc_contract.py
git commit -m "Add Application Insights investigation screenshots" \
  -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
