# CLI Extension Placement Design

## Goal

Install Azure CLI extensions once during workshop prerequisites and remove redundant installation commands from later modules.

## Design

- `docs/01-prerequisites.md` remains the single normal installation location for:
  - `application-insights`
  - `authV2`
  - `log-analytics`
- `docs/02-environment-setup.md` removes the repeated `application-insights` installation and proceeds directly from the Log Analytics workspace ID lookup to Application Insights resource creation.
- `docs/08-observability.md` removes the repeated `log-analytics` and `application-insights` installation commands. Step descriptions state that the extensions were installed in module 01.
- Troubleshooting sections keep their extension installation commands because they are recovery procedures for missing or damaged local CLI state.

## Validation

Document contract tests verify that:

- module 01 contains all three normal installation commands;
- modules 02 and 08 do not contain extension installation commands outside troubleshooting;
- the resource creation and observability query commands remain unchanged.

## Scope

The supplied Log Analytics query screenshot is stored as
`docs/images/08-log-analytics-kql-results.png` and referenced from the module
08 Step 3 expected-screen section.

This change only reorganizes workshop documentation, adds the supplied
documentation image, and updates contract tests. It does not change Azure
resources, application code, or rehearsal behavior.
