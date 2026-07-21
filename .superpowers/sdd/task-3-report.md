# Task 3 Report

## Current metadata
- Task 3 HEAD: `6b03d4d`
- Commit range: `78ba23a..6b03d4d`
- Files changed:
  - `README.md`
  - `docs/07-autoscale.md`
  - `scripts/rehearsal.sh`
  - `scripts/tests/test_observe_instances.py`

## Final summary
- `scripts/rehearsal.sh` now uses the approved `observe_instances.py` A/B flow.
- `README.md` and `docs/07-autoscale.md` were aligned with the new instance-age wording and disclaimer.
- `scripts/tests/test_observe_instances.py` was updated to cover the final failure mapping behavior.

## Validation
- Final local validation suite:
  ```bash
  cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && /home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests scripts/tests && python3 -m py_compile scripts/observe_instances.py && bash -n scripts/rehearsal.sh && python3 - <<'PY'
  from pathlib import Path
  for path in [Path('README.md'), Path('docs/07-autoscale.md')]:
      assert path.read_text(encoding='utf-8').count('```') % 2 == 0, path
  PY
  git diff --check
  ```
  Output:
  ```text
  ...................                                                      [100%]
  19 passed in 0.18s
  ```
- No Azure mutation/load commands were run.

## Interim evidence
- [interim] `5f533cf` — initial rehearsal rewrite and README update.
- [interim] `e1c6d64` — disclaimer/output alignment follow-up.
- [interim] `e54bf08` — docs disclaimer alignment.
- [interim] `6b03d4d` — final failure-mapping fix and report update.

## Follow-up: final status-channel bug fix
- `scripts/rehearsal.sh` now returns the observer status channel on every path; `HEY_FAILURE` still carries hey failure separately.
- `docs/07-autoscale.md` mirrors the same return-value contract.
- `scripts/tests/test_rehearsal_contract.py` now guards against the old `return "$hey_status"` regression in both rehearsal and docs.

## Validation
- Full local validation suite:
  ```bash
  cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && PYTHONPATH=$PWD/.deps/root/usr/lib/python3/dist-packages python3 -m pytest -q app/tests scripts/tests && find app scripts -name '*.py' -print0 | xargs -0 python3 -m py_compile && bash -n scripts/rehearsal.sh && python3 -c 'from pathlib import Path; p=Path("docs/07-autoscale.md"); t=p.read_text(encoding="utf-8"); assert t.count("```") % 2 == 0, p' && git diff --check
  ```
  Output:
  ```text
  26 passed in 0.81s
  ```
- No Azure mutation/load commands were run.
