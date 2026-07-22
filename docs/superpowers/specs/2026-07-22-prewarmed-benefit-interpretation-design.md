# Prewarmed Benefit Interpretation Design

## Goal

Strengthen step 6 of `docs/07-autoscale.md` so the workshop clearly explains
which Prewarmed benefit the current A/B scenario can demonstrate and which
claims the evidence cannot support.

## Official Product Mechanism

Link to the Microsoft Learn article
[`Automatic scaling in Azure App Service`](https://learn.microsoft.com/azure/app-service/manage-automatic-scaling).
Use its product framing:

- Prewarmed instances act as warmed capacity buffers during HTTP scale and
  activation events.
- The buffer is intended to improve performance, reduce cold-start delay, and
  make scaling transitions smoother.
- The default is one Prewarmed instance for most scenarios.

The workshop must not reinterpret this as a guarantee that every scale-out
event or every individual instance is faster.

## How the Scenario Shows the Benefit

`STARTUP_DELAY_SECONDS=20` creates an approximate readiness floor because
`started_at` is recorded before the artificial delay. Compare each trial using:

- distance from the approximately 20-second readiness floor;
- maximum observed `first_response_age`, representing the longest observed
  tail in that trial;
- range between minimum and maximum age, representing observed spread or
  consistency.

For the recorded rehearsal:

| Trial | Samples | Minimum | Maximum | Range |
|---|---:|---:|---:|---:|
| Prewarmed=0 | 4 | 22s | 46s | 24s |
| Prewarmed=1 | 2 | 23s | 23s | 0s |

The valid interpretation is:

- The fastest observation did not improve: 22 seconds without Prewarmed versus
  23 seconds with Prewarmed.
- Trial A included a 46-second tail and a 24-second spread.
- Trial B's two observations were both 23 seconds, close to the artificial
  readiness floor, with no long tail observed.
- In this rehearsal, the visible benefit is therefore **more consistent
  readiness near the startup floor and lower observed tail risk**, not a faster
  single best instance or guaranteed total scale-out time.

## Summary Command

After the raw timeline, add a `jq -s` command that reads both JSON arrays and
prints:

```text
trial  samples  min_age  max_age  range
```

The command must calculate values from the participant's files instead of
hard-coding the rehearsal result.

## Interpretation Structure

Add four short subsections after the summary output:

1. **What the numbers show** — explain minimum, maximum, and range.
2. **Where Prewarmed helps** — connect reduced tail/spread to smoother capacity
   activation during sudden HTTP load.
3. **What this run does not prove** — no guarantee, percentage improvement, or
   direct internal-state proof.
4. **How to interpret a different result** — similar or worse Trial B results
   mean the benefit was not visible in that run; restore, wait for scale-in, and
   repeat rather than declaring Prewarmed ineffective.

## Evidence Limitations

State all of the following:

- This is one run with unequal sample counts: four observations versus two.
- `first_seen_at` is the first response observed by the client, not the exact
  Azure routing or activation timestamp.
- `AutomaticScalingInstanceCount` includes a Prewarmed instance when deployed
  but does not label individual app responses as active or Prewarmed.
- The scenario does not collect end-user request latency, error rate, or Azure
  internal allocation events.
- The result is consistent with the official buffer mechanism but does not
  prove causality.

## Scope

Modify only the result interpretation portion of step 6 and its documentation
contract tests. Preserve the Trial A/B execution commands, raw timeline command,
restoration commands, and final module state.

## Validation

Extend `scripts/tests/test_autoscale_doc_contract.py` to require:

- the dynamic summary command and its five columns;
- the recorded expected summary values;
- the official Microsoft Learn link and warmed-buffer description;
- the readiness-floor, maximum-tail, range, and consistency interpretation;
- all evidence limitations and alternate-result guidance.

Run the existing full test suite.
