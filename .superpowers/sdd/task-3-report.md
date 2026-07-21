# Task 3 Report

## Summary
- Replaced the old burst-timing rehearsal logic in `scripts/rehearsal.sh` with the approved `observe_instances.py`-driven A/B flow.
- Removed the prime loads, `InstanceCount>=2` Prewarmed buffer gate, numeric winner output, and obsolete timing variables.
- Updated `README.md` workshop ranges and module 07 timing/status text to match the new instance-age rehearsal.

## Files changed
- `scripts/rehearsal.sh`
- `README.md`

## Validation

### Full local validation suite
Command:
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
19 passed in 0.17s
```

### Commit
Command:
```bash
cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && git add scripts/rehearsal.sh README.md && git commit -m "test: rehearse prewarmed instance age" -m "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```
Output:
```text
[feature/prewarmed-instance-age 5f533cf] test: rehearse prewarmed instance age
 2 files changed, 108 insertions(+), 92 deletions(-)
```

### Post-commit status
Command:
```bash
cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && git rev-parse --short HEAD && git status --short
```
Output:
```text
5f533cf
```

## Self-review
- Confirmed the rehearsal preserves the observer's real exit codes and treats exit 2 / empty JSON as a restore-and-stop condition.
- Confirmed `HEY_PID` remains the only tracked background PID and the existing EXIT cleanup remains the only broad trap.
- Confirmed the rehearsal now records and prints per-instance `started_at`, `first_seen_at`, and `first_response_age` instead of declaring a speed winner.
- Confirmed the obsolete prime loads, buffer-allocation gate, and numeric improvement output are removed.
- Did not run Azure mutation or load commands.

## Commit
- `5f533cf` — `test: rehearse prewarmed instance age`

## Concerns
- None after the disclaimer alignment fix.

## Follow-up fix validation

Command:
```bash
cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && /home/jungwoonlee/appservice/.venv/bin/pytest -q app/tests scripts/tests
```
Output:
```text
...................                                                      [100%]
19 passed in 0.16s
```

Command:
```bash
cd /home/jungwoonlee/appservice/.worktrees/prewarmed-instance-age && python3 -m py_compile scripts/observe_instances.py && bash -n scripts/rehearsal.sh && python3 - <<'PY'
from pathlib import Path
for path in [Path('README.md'), Path('docs/07-autoscale.md')]:
    assert path.read_text(encoding='utf-8').count('```') % 2 == 0, path
PY
git diff --check
```
Output:
```text
```

- Resolved: the rehearsal TSV header and the docs now use `시험` consistently, and the `[07] first_response_age...` disclaimer is identical in both places.

## Disclaimer alignment fix

- Moved the exact `[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다.` line into `render_instance_age_results()` after both TSV outputs.
- Removed the duplicate explanatory prose outside the function so the runnable example and rehearsal now present the same header/disclaimer behavior.
- Re-ran fence validation, `bash -n scripts/rehearsal.sh`, and `git diff --check`; all passed.

## Exact-contract follow-up fix

- Mapped no-observation trial outcomes in `scripts/rehearsal.sh` to restore + retry guidance and final exit 1.
- Switched the literal TSV header to `trial\tinstance\tstarted_at\tfirst_seen_at\tfirst_response_age` in both rehearsal and the docs renderer.
- Kept the disclaimer line identical and updated the docs note to say the observer may exit 2 while the rehearsal normalizes failures to 1.

## Validation

### Exact validation suite

Command:
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

## Concerns

- None.
