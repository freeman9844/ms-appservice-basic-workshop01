# Workshop Command Comments Design

## Goal

Improve the explanatory quality of all workshop modules by adding concise
Korean comments to executable Bash blocks in `docs/01-prerequisites.md`
through `docs/12-cleanup.md`.

## Scope

Apply the enhancement to:

- numbered instructional steps;
- module validation sections.

Do not modify Bash blocks under `## 트러블슈팅`.

The current workshop contains more than one hundred Bash blocks, so
implementation is divided into three independently reviewed groups:

1. Modules 01–04: prerequisites, environment setup, deployment, app settings.
2. Modules 05–08: slots, traffic splitting, automatic scaling, observability.
3. Modules 09–12: Easy Auth, sidecar, Auto-heal, cleanup.

## Comment Style

Add comments at logical operation boundaries, not before every command. A
logical operation is a group of commands with one purpose, such as:

- define or recover workshop variables;
- create or locate Azure resources;
- change an App Service setting;
- prepare and deploy an artifact;
- generate traffic or load;
- query state, logs, or metrics;
- compare observations;
- restore a safe state;
- delete resources and confirm cleanup.

Comments answer **why the operation is performed** and, where useful, **what
state changes or evidence to expect**. They do not merely restate the command
name.

Use short Korean shell comments beginning with `#`. Separate logical groups
with a blank line when that improves scanning. Preserve the copy-and-paste
behavior of every block.

## High-Risk Concepts

Give additional clarity to concepts that are commonly misunderstood:

- App Service Plan versus Web App resource creation;
- Oryx build settings and zip deployment;
- app setting changes causing process restart;
- slot creation, deployment, swap, rollback, and slot-specific settings;
- weighted traffic routing versus forced slot routing;
- automatic scaling, Always-ready, Prewarmed instances, load generation, and
  observation scripts;
- diagnostic settings versus Application Insights automatic instrumentation;
- App Registration, user login, application credentials, and managed identity;
- sidecar creation and the main/sidecar container boundary;
- Auto-heal trigger configuration and process recycling;
- resource group deletion versus separate Entra app registration deletion.

For Azure CLI behavior that is not self-evident, confirm the explanation
against current Microsoft documentation before editing.

## Preservation Rules

- Do not change commands, options, variable names, ordering, expected output,
  screenshots, or learning outcomes.
- Do not move instructions between sections.
- Do not add comments to expected-output blocks, JSON examples, Mermaid
  diagrams, or troubleshooting blocks.
- Reuse existing accurate comments instead of duplicating them.
- Keep comments concise enough that the executable workflow remains easy to
  copy and scan.

## Validation

Create `scripts/tests/test_workshop_command_comments_contract.py`. It parses
each module only up to `## 트러블슈팅`, finds ordinary fenced Bash blocks, and
requires every block to contain at least one shell comment. This structural
contract prevents future uncommented instructional blocks.

Keep all existing module-specific contracts. Each implementation group runs
the new contract plus the relevant existing contracts. The final verification
runs the complete `scripts/tests` and `app/tests` suites and `git diff --check`.

## Completion

Commit each module group separately. After all three groups are integrated into
local `main`, synchronize `main` to GitHub and verify that local and remote
commit SHAs match. Keep the local untracked `out.text` file out of all commits.
