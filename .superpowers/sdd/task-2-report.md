# Task 2 Report

## Implementation summary
- Rewrote docs/07-autoscale.md steps 5-6 to remove the remaining user-defined Bash helpers and replace them with direct CLI/curl/jq/hey/python commands.
- Removed temporary rehearsal-helper compatibility prose from step 4 and deleted the duplicate verification subsection that still depended on removed helper-based flow.
- Updated autoscale documentation contract tests for the new direct Trial B, results, and restoration flow.
- Updated the legacy rehearsal contract test so the docs are validated against the new direct learner flow instead of obsolete helper/trap wording.

## Files changed
- docs/07-autoscale.md
- scripts/tests/test_autoscale_doc_contract.py
- scripts/tests/test_rehearsal_contract.py

## RED / GREEN evidence
### RED
1. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q`
   - Failed: `test_steps_five_and_six_use_direct_commands`
   - Cause: step 5 still contained `run_trial_b() {`.
2. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q`
   - Failed: `test_steps_three_and_four_use_direct_commands`
   - Cause: step 4 still contained the obsolete `rehearsal helper 계약` prose.
   - Failed: `test_steps_five_and_six_use_direct_commands`
   - Cause: step 5 still contained helper definitions.

### GREEN
1. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q`
   - Result: `4 passed in 0.01s`
2. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py scripts/tests/test_rehearsal_contract.py -q`
   - Result: `8 passed in 0.02s`
3. `python3 -m pytest scripts/tests -q`
   - Result: `17 passed in 0.61s`

## Full-suite output
```text
.................                                                        [100%]
17 passed in 0.61s
```

## Commit
- `47e15133f55a07a9261a24512b0488fe78259521` — `docs: simplify autoscale trial B and cleanup`

## Self-review
- Confirmed no user-defined Bash function definitions remain in steps 3-6.
- Confirmed step 5/6 direct flow includes the required Trial B metric check, Prewarmed=1 patch, direct observation run, direct result rendering, restoration, health polling, and state read-back.
- Confirmed obsolete helper/trap wording was removed from learner-facing docs and full tests were updated to enforce the new direct flow.
- Confirmed `git diff --check` passed before commit.

## Concerns
- The original brief expected only two modified files, but the full suite still encoded removed helper-contract wording in `scripts/tests/test_rehearsal_contract.py`; I updated that affected test so the suite validates the new direct documentation flow.

## Review Fix
### RED
1. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q`
   - Failed: `test_trial_observation_runs_only_after_baseline_capture_succeeds`
   - Cause: Trial A/B baseline capture used `&& echo ...` followed by separate `hey` and observer commands, so the contract could not prove those commands only run after successful baseline acquisition.

### GREEN
1. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py -q`
   - Result: `5 passed in 0.02s`
2. `python3 -m pytest scripts/tests/test_autoscale_doc_contract.py scripts/tests/test_rehearsal_contract.py -q`
   - Result: `9 passed in 0.01s`

### Full suite
1. `python3 -m pytest scripts/tests -q`
   - Result: `18 passed in 0.63s`
