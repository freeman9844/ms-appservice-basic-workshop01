# Application Insights Diagnostics Design

## Goal

Expand module 08 so Application Insights demonstrates route-level performance,
failure investigation, and individual transaction diagnostics instead of only
showing aggregate request counts and Live Metrics.

## Scenario

Use existing application behavior without changing the Flask app:

- send 20 successful requests to `GET /api/info`;
- send 5 slow requests to `GET /slow?sec=3`;
- send 5 intentional 404 requests to `GET /workshop-not-found`.

Wait for workspace-based Application Insights telemetry in `AppRequests`, then
summarize operation name, result code, success, request count, average duration,
and P95 duration.

## Portal Investigation

Module 08 Step 4 guides participants through:

1. **Performance** — compare `/slow` with `/api/info` and inspect a slow sample.
2. **Failures** — find the intentional 404 operation and its result code.
3. **End-to-end transaction details** — open one slow request and inspect its
   duration, operation ID, properties, and timeline.
4. **Application Map** — recognize that a single node and no dependency rows are
   expected because this scenario makes no external dependency call.

## Learning Boundary

App Service Metrics remain the source for platform-level aggregates such as
request count, CPU, memory, and response time. Application Insights adds
operation names, success and result-code dimensions, duration distribution,
individual request samples, and correlated transaction context.

## Reliability

Keep the existing application restart health gate and telemetry ingestion
polling. All generated requests use `curl -fsS` except the intentional 404
requests, whose HTTP status is captured explicitly so the expected failure does
not abort the shell workflow.

## Validation

Document contract tests verify the traffic mix, the `AppRequests` summary
fields, the three Portal investigation paths, and the explanation of the
single-node Application Map.
