# Autoscale Steps 3-6 Direct CLI Design

## Goal

Rewrite steps 3 through 6 of `docs/07-autoscale.md` so workshop participants
can copy and execute commands directly, as they do in step 1, without first
defining Bash helper functions.

## Scope

The change is limited to the interactive execution guide in
`docs/07-autoscale.md` and its documentation contract tests.

The following remain unchanged:

- Step 1 Automatic scaling configuration
- Step 2 `hey` installation
- `scripts/rehearsal.sh`, which remains the safety-oriented automated rehearsal
- `scripts/observe_instances.py`
- The Prewarmed A/B observation method, load shape, output files, interpretation,
  and final module state

## Execution Model

### Step 3: Prepare the Observation

Remove all helper and trap definitions. Replace them with direct commands that:

1. Set `STARTUP_DELAY_SECONDS=20` with `az webapp config appsettings set`.
2. Poll `/health` with a short inline loop until the application reports
   `{"status":"ok"}`.
3. Read back the Plan and Web App autoscale settings with `az rest`.
4. Create `$HOME/appservice-prewarmed-ab` and assign the two observation file
   paths used by later steps.

The guide must tell the participant to stop and run the step 6 restoration block
if preparation fails.

### Step 4: Trial A, Prewarmed=0

Use a direct sequential command block to:

1. PATCH `minimumElasticInstanceCount=1` and `preWarmedInstanceCount=0`.
2. GET and display the values for confirmation.
3. Display recent `InstanceCount` metric samples and require the latest state to
   be one instance before continuing.
4. Acquire the baseline instance ID from `/api/info`.
5. Start the existing 180-second `hey` load in the background.
6. Run `observe_instances.py` with the existing duration, concurrency, timeout,
   baseline exclusion, and output file.
7. Wait for `hey`, display both exit codes, and require both to be zero.

If either process fails, the participant stops the A/B flow and immediately
runs the step 6 restoration block.

### Step 5: Trial B, Prewarmed=1

Before Trial B, display recent `InstanceCount` samples again. The participant
reruns this read-only command until the latest state is one instance.

Then use the same direct trial structure as step 4, changing only:

- `preWarmedInstanceCount` to `1`
- The label to `Prewarmed=1`
- The observation output to `prewarmed-1-observations.json`
- The load output to `hey-burst-1.out`

No prime load or `InstanceCount>=2` gate is added.

### Step 6: Results and Restoration

Replace result and restoration functions with direct commands:

1. Use the existing two `jq` expressions to print one combined TSV table.
2. PATCH the Web App back to Always-ready 1 and Prewarmed 1.
3. Delete `STARTUP_DELAY_SECONDS`.
4. Poll `/health`.
5. Read back Plan, Web App, and app-setting state.

The final state remains:

- Automatic scaling enabled
- Maximum burst 5
- Always-ready 1
- Prewarmed 1
- No `STARTUP_DELAY_SECONDS`
- Healthy application response

## Error Handling

Interactive readability takes priority over reproducing the existing nested
helper and trap framework. Commands that must succeed before the next mutation
are joined with `&&` where practical. The guide explicitly instructs users not
to continue after a nonzero observer or load-test exit code.

The step 6 restoration block is safe to run early after a failure. Automated
rehearsals that require traps, process cleanup, and strict recovery continue to
use `scripts/rehearsal.sh`.

## Documentation Contract

Update `scripts/tests/test_autoscale_doc_contract.py` to verify:

- Steps 3 through 6 contain no user-defined Bash functions.
- Step 3 directly sets the startup delay and prepares both output paths.
- Steps 4 and 5 directly PATCH and GET the expected Prewarmed values.
- Steps 4 and 5 directly run `hey`, `observe_instances.py`, `wait`, and exit-code
  checks.
- Step 5 retains the single-instance gate and does not introduce a prime or
  `InstanceCount>=2` gate.
- Step 6 directly renders both JSON files and restores all required settings.
- Existing step 1 contracts remain unchanged.

## Success Criteria

- A participant can execute each step by copying its command blocks without
  first loading helper functions.
- The A/B test parameters and interpretation do not change.
- Failure guidance clearly points to the direct restoration block.
- Existing tests and the expanded documentation contract pass.
