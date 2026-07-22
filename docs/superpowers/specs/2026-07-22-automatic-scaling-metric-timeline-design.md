# Automatic Scaling Metric Timeline Design

## Goal

Extend the Prewarmed A/B scenario in `docs/07-autoscale.md` and
`scripts/rehearsal.sh` so each trial records how
`AutomaticScalingInstanceCount` changes during the burst. Correlate that
capacity timeline with the existing new-instance response observations without
claiming access to Azure's internal activation state.

## Approach

Add one shared Python observer, `scripts/observe_scaling_metric.py`, and use it
from both the copy-and-run workshop commands and the automated rehearsal.

The observer is preferable to duplicated Bash loops because it centralizes:

- Azure CLI invocation and JSON parsing;
- polling and metric timestamp de-duplication;
- live tabular output;
- persisted result validation;
- exit-code behavior.

The existing `InstanceCount` queries remain the gate for obtaining a
single-instance baseline. The new observer uses the official
`AutomaticScalingInstanceCount` metric only for the trial timeline.

## Metric Observer Interface

The command accepts:

```text
--resource <App Service resource ID>
--duration 240
--poll-interval 30
--output <JSON path>
```

The fixed workshop settings are:

- metric: `AutomaticScalingInstanceCount`;
- aggregation: `Maximum`;
- interval: `PT1M`;
- polling interval: 30 seconds;
- total observation duration: 240 seconds.

The 240-second duration covers the 180-second load and instance observation,
then allows up to 60 additional seconds for Azure Monitor ingestion delay.

At startup, the observer records `trial_started_at`. Each poll queries a window
that includes the minute immediately before the trial start so the first
one-minute bucket can provide baseline context. The observer retains the latest
value for each metric timestamp and prints a row when a timestamp or its value
is first observed or changes.

## Output Contract

The observer writes a JSON object instead of a bare array:

```json
{
  "metric": "AutomaticScalingInstanceCount",
  "aggregation": "Maximum",
  "interval": "PT1M",
  "trial_started_at": "2026-07-22T01:02:03Z",
  "poll_interval_seconds": 30,
  "duration_seconds": 240,
  "samples": [
    {
      "metric_timestamp": "2026-07-22T01:02:00Z",
      "observed_at": "2026-07-22T01:02:34Z",
      "instance_count": 1
    }
  ]
}
```

`metric_timestamp` is Azure Monitor's one-minute bucket timestamp.
`observed_at` is when the observer first received the current value for that
bucket. They must remain separate because Azure Monitor data can arrive after
the represented interval.

The live table uses these columns:

```text
metric_timestamp  observed_at  instance_count
```

Trial-specific files are:

- `prewarmed-0-instance-count.json`;
- `prewarmed-1-instance-count.json`.

The existing files remain unchanged:

- `prewarmed-0-observations.json`;
- `prewarmed-1-observations.json`;
- `hey-burst-0.out`;
- `hey-burst-1.out`.

## Trial Data Flow

After the baseline instance ID is acquired successfully, each trial executes
the following sequence:

1. Start `observe_scaling_metric.py` in the background and save its PID.
2. Start the 180-second `hey` burst in the background and save its PID.
3. Run `observe_instances.py` for 180 seconds in the foreground.
4. Wait for `hey`.
5. Wait for the metric observer, including its possible 60-second ingestion
   allowance.
6. Require all three exit codes to be zero before continuing.

Starting the metric observer before `hey` gives it a chance to record the
baseline bucket before load begins. The stored `trial_started_at` is the start
of trial orchestration, not an exact `hey` request timestamp. Its small
process-launch skew is insignificant relative to the metric's one-minute
resolution but must not be described as an Azure activation timestamp.

Trial A and Trial B use identical duration, concurrency, request timeout,
metric polling, and load settings. Only `preWarmedInstanceCount` and result file
names differ.

## Rehearsal Integration and Cleanup

`scripts/rehearsal.sh` tracks a metric-observer PID independently from
`HEY_PID`. Its cleanup path stops and waits for either tracked process before
restoring Prewarmed settings and removing `STARTUP_DELAY_SECONDS`.

`run_instance_age_trial` receives both the instance-observation path and the
metric-observation path. It starts the metric observer first, preserves the
three process statuses, and does not report success until all processes and
output validations succeed.

The trial handler validates:

- the instance observation file is a non-empty JSON array;
- the metric file is a JSON object for
  `AutomaticScalingInstanceCount`;
- `samples` is a non-empty array;
- every sample has valid timestamps and a numeric `instance_count`.

If either observer or the load fails, the rehearsal reports each failed
component, restores the module state, and stops before the next trial.

## Error Handling

The metric observer uses these exit codes:

- `0`: at least one valid metric sample was persisted;
- `1`: unrecoverable Azure CLI, JSON parsing, argument, or file-write failure;
- `2`: the observation window completed without a valid metric sample.

A transient query failure is reported and retried while time remains. The
observer succeeds only if it ultimately persists at least one valid sample.
If no data is available after 240 seconds, the trial fails rather than
continuing with incomplete evidence.

The workshop commands display the metric observer, instance observer, and
`hey` exit codes together. Any non-zero value instructs the participant to run
the step 6 restoration commands and restart from step 3.

The observer writes its final JSON atomically so an interrupted process does
not leave a success-shaped partial file.

## Result Presentation and Interpretation

Step 6 adds a metric timeline before the existing instance timeline and range
summary. It prints, for both trials:

- `trial_started_at`;
- each `metric_timestamp`;
- each `observed_at`;
- each `instance_count`.

Participants compare:

1. when trial orchestration started immediately before the load;
2. when the one-minute metric bucket first shows count growth;
3. when each new instance first responds through `first_seen_at`.

This comparison shows the externally observable sequence of load, capacity
growth, and response participation. It does not identify which response came
from a Prewarmed instance.

The documentation must state:

- `AutomaticScalingInstanceCount` can include a deployed Prewarmed instance;
- it does not distinguish active from Prewarmed capacity;
- it does not expose instance IDs;
- `PT1M` aggregation and ingestion delay prevent treating
  `metric_timestamp` as an exact activation time;
- the number of response instances observed is not a capacity-efficiency
  metric;
- the metric timeline is supporting evidence for the warmed-buffer
  interpretation, not proof of causality.

## Testing

Add focused tests for `observe_scaling_metric.py` covering:

- Azure Monitor payload parsing;
- null and malformed data rejection;
- timestamp de-duplication and value replacement;
- atomic output shape;
- successful completion with samples;
- exit code 2 when no valid samples arrive;
- exit code 1 for unrecoverable CLI, parse, or write failures.

Extend `scripts/tests/test_autoscale_doc_contract.py` to require:

- both metric output paths;
- the metric observer before `hey` in Trial A and Trial B;
- 240-second duration and 30-second polling;
- all three exit-code checks;
- the step 6 metric timeline and interpretation limitations.

Extend `scripts/tests/test_rehearsal_contract.py` to require:

- independent metric PID tracking and cleanup;
- shared observer invocation in both trials;
- all three statuses being preserved;
- metric JSON validation;
- restore-and-stop behavior for metric failures.

Run the focused observer and contract tests, then the existing full test suite.

## Scope

Modify:

- `scripts/observe_scaling_metric.py`;
- `scripts/rehearsal.sh`;
- `docs/07-autoscale.md`;
- relevant tests under `scripts/tests/`.

Do not change the application API, load profile, artificial startup delay,
baseline `InstanceCount` gate, App Service scaling configuration, or the
existing statistical limitations of a single A/B run.
