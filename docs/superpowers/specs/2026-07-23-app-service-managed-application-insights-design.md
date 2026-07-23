# App Service Managed Application Insights Design

## Goal

Update module 08 to enable Application Insights through the App Service-managed
Python agent instead of instrumenting the Flask application with the Azure
Monitor OpenTelemetry SDK.

## Supported Environment

The workshop deploys Python 3.12 as code on Linux App Service. This is within
the supported Python 3.9 through 3.13 range for App Service automatic
instrumentation. Custom containers are outside this design.

## Instrumentation Architecture

Remove `azure-monitor-opentelemetry` from `app/requirements.txt` and remove the
conditional `configure_azure_monitor()` startup code from `app/app.py`. The
application remains unaware of Application Insights.

Module 08 obtains the existing Application Insights connection string and sets
both required App Service settings:

- `APPLICATIONINSIGHTS_CONNECTION_STRING=<resource connection string>`
- `ApplicationInsightsAgent_EXTENSION_VERSION=~3`

The second setting enables the App Service-managed Python agent. App Service
restarts the application after the settings change and manages future agent
updates.

## Workshop Flow

Step 4 uses Azure CLI rather than the portal to enable monitoring. After setting
the two values, the module verifies their names and nonempty state without
printing the connection string. It then waits for `/health`, generates the
existing successful, slow, and intentional 404 traffic, and polls the
workspace-based `AppRequests` table.

The existing Log Analytics query path remains because Cloud Shell managed
identity might not support the `api.applicationinsights.io` audience required
by `az monitor app-insights query`.

## Portal Experience

Participants open the App Service **Application Insights** blade and confirm
that integration is enabled. They then open the linked Application Insights
resource to inspect:

1. **Performance** for the slow `GET /slow` operation.
2. **Failures** for the intentional `GET /workshop-not-found` 404 operation.
3. **Transaction search** or a request sample for duration, result code, and
   operation context.
4. **Application map**, where a single application node and no external
   dependency connection are expected.

App Service Python automatic instrumentation does not support Live Metrics.
The module removes the Live Metrics instructions and image reference and
replaces them with Performance and Failures guidance. No unsupported Live
Metrics expectation remains.

## Rehearsal and Tests

`scripts/rehearsal.sh` sets both required App Service settings so automated
rehearsals exercise the same managed-agent path as the participant guide.

Contract tests require the managed-agent setting, reject application-level
OpenTelemetry setup, and verify the updated portal guidance and Live Metrics
limitation. Application tests continue to cover application behavior without
requiring telemetry packages.

## Error Handling

- If either required App Service setting is absent, the module stops before
  generating diagnostic traffic.
- If the application does not become healthy after restart, the module stops.
- If `AppRequests` is not populated within the existing polling window, the
  module directs participants to managed-agent troubleshooting.
- Troubleshooting distinguishes a missing connection string from a missing
  `ApplicationInsightsAgent_EXTENSION_VERSION=~3` setting.

## Scope

This change does not add custom telemetry, browser instrumentation, custom
OpenTelemetry instrumentations, or container support. It preserves the
existing Application Insights resource, workspace linkage, KQL queries, and
diagnostic traffic scenario.
