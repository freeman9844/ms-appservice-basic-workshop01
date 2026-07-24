# Application Insights Investigation Screenshots Design

## Goal

Add the four supplied Azure Portal screenshots as sample outputs for the four
items under module 08 Step 4, **Application Insights에서 추가로 확인할 내용**.

## Image Mapping

Store the screenshots under `docs/images/` with stable descriptive names:

1. Performance:
   `08-application-insights-performance.png`
2. Failures:
   `08-application-insights-failures.png`
3. End-to-end transaction details:
   `08-application-insights-transaction-details.png`
4. Application map:
   `08-application-insights-application-map.png`

The attachment order is authoritative and matches this mapping.

## Document Layout

Keep the existing four numbered explanations. Place each full-width Markdown
image immediately after its corresponding numbered item so the expected Portal
result remains adjacent to the instruction that produces it.

Each image uses Korean alternative text that identifies both the Application
Insights view and the result participants should notice:

- Performance shows `GET /slow` at about 3 seconds.
- Failures shows the intentional `GET /workshop-not-found` 404.
- Transaction details shows one `GET /slow` request with response code 200 and
  duration 3 seconds.
- Application map shows the App Service application node without an external
  dependency connection.

## Validation

Extend the observability document contract test to require all four exact image
references and verify that all four files exist. Existing tests for the
investigation labels and managed instrumentation remain unchanged.

## Scope

Do not crop, resize, annotate, or otherwise modify the supplied screenshots.
Do not change the module commands or Application Insights workflow.
