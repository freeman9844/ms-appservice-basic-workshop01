# Observability Validation Removal Design

## Goal

Remove the redundant validation section from `docs/08-observability.md` while
preserving the module's troubleshooting guidance.

## Removal Boundary

Delete everything from the `## 검증` heading through the content immediately
before `## 트러블슈팅`. This removes:

- `### HTTP 로그 KQL 확인`
- the repeated `AppServiceHTTPLogs` query and expected output
- `### App Insights 텔레메트리 확인`
- the repeated `AppRequests` query and expected output
- the module completion sentence

Keep the separator and the complete `## 트러블슈팅` section.

## Rationale

Step 3 already executes and explains the HTTP log query. Step 4 already polls
for `AppRequests`, prints the route-level Application Insights summary, and
shows the Portal investigation results. Repeating simpler forms of both queries
in a separate validation section adds length without introducing a distinct
learning outcome.

## Validation

Extend the observability document contract to assert that the validation
heading and its two subsection headings are absent while `## 트러블슈팅`
remains present.

## Completion

After implementation and tests, merge the change into local `main` and push
`main` to GitHub according to the recorded synchronization preference.
