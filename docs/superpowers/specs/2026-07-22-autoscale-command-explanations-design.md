# Autoscale Command Explanations Design

## Goal

Add short explanations to every execution block in steps 3 through 6 of
`docs/07-autoscale.md` so workshop participants understand what each command
does before running it.

## Scope

Add explanations to these 13 execution blocks:

### Step 3

1. Startup-delay configuration and result-path preparation
2. Application health polling
3. Automatic scaling setting read-back

### Step 4

1. Prewarmed=0 configuration
2. Single-instance metric check
3. Trial A load and observation

### Step 5

1. Trial B single-instance metric check
2. Prewarmed=1 configuration
3. Trial B load and observation

### Step 6

1. Combined result-table rendering
2. Module-default restoration
3. Post-restoration health polling
4. Restored-state read-back

Steps 0 through 2 and the later validation/troubleshooting sections are outside
this change.

## Presentation

Place a `> 👁️` explanation between each `🟢 **실행 ...**` heading and its Bash
code block. Each explanation is one or two sentences and covers:

- what resource, setting, file, metric, or process the command acts on;
- why the action is needed in the A/B workflow;
- what value or status the participant should confirm when that is not already
  obvious from the expected output.

The explanation is block-level, not a line-by-line option reference. Existing
expected outputs, warning notes, and conceptual explanations remain in place.

## Content Requirements

- Explain that `STARTUP_DELAY_SECONDS=20` makes new-process startup observable
  and that the two JSON paths store Trial A/B observations.
- Explain that health polling retries up to 18 times and only succeeds when
  `/health` returns `status=ok`.
- Map Plan and Web App read-back fields to Automatic scaling, Maximum burst,
  Always-ready, and Prewarmed.
- Explain that the metric commands query recent one-minute `InstanceCount`
  maximum samples and require the latest count to be one before each trial.
- Explain that Prewarmed PATCH blocks both change and immediately read back the
  setting.
- Explain that each trial captures a baseline instance, runs `hey` for 180
  seconds, observes only new instances, stores JSON, and checks both process
  exit codes.
- Explain that the result commands combine both JSON files into a TSV timeline,
  not a winner calculation.
- Explain that restoration resets Always-ready and Prewarmed, removes the
  artificial startup delay, waits for health, and reads back the final state.

Do not alter command syntax, parameters, output paths, expected outputs, or
error-handling behavior.

## Related Wording Correction

Update the common-state note that currently says `REPO_DIR` is used by
"helpers." The direct workflow now uses it to locate
`scripts/observe_instances.py`, so the note must describe that current purpose.

## Documentation Contract

Extend `scripts/tests/test_autoscale_doc_contract.py` to verify that every
in-scope execution heading has a `> 👁️` explanation before its Bash block.
Check representative required terms for each category so future edits cannot
silently remove the purpose, retry behavior, metric interpretation, trial
process, or restoration explanation.

Existing direct-command and control-flow contracts must remain unchanged.

## Success Criteria

- Every execution block in steps 3 through 6 has a concise adjacent
  explanation.
- A participant can understand the intent and confirmation point without
  reading shell syntax line by line.
- The module does not become substantially longer or repeat existing expected
  output.
- All documentation contract tests pass.
