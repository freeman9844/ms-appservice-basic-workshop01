# Autoscale Trial Command Details Design

## Goal

Expand only the explanations for `실행 — 시험 A 관찰` and
`실행 — 시험 B 관찰` in `docs/07-autoscale.md`.

## Presentation

Replace each existing one-paragraph explanation with five concise numbered
items placed before the unchanged Bash block.

Each list explains:

1. Baseline instance acquisition with `curl` and `jq`, including fail-fast
   behavior.
2. The `hey` load parameters, background execution, and output file.
3. Why `$!` is stored in `HEY_PID`.
4. The observer's baseline exclusion, concurrency, request timeout, and JSON
   output.
5. Waiting for `hey` and requiring both process exit codes to be zero.

Trial B must state that its execution shape is the same as Trial A and that the
differences are the Prewarmed setting and Trial B output files.

## Command Semantics

Describe `hey -z 180s -c 100 -q 10` accurately:

- run for 180 seconds;
- allow up to 100 concurrent workers;
- limit each worker to 10 queries per second.

Describe `observe_instances.py` accurately:

- exclude the captured baseline instance;
- observe for 180 seconds;
- use concurrency 30;
- use a five-second timeout per request;
- store observations in the trial-specific JSON file.

## Scope and Validation

Do not change commands, arguments, output paths, expected output, or failure
behavior. Extend the documentation contract to require five numbered items and
the key command concepts for both trial explanations. Existing contracts must
remain green.
