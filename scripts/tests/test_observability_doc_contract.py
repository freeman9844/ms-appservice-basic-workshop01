from pathlib import Path


ROOT = Path(__file__).parents[2]
PREREQUISITES = (ROOT / "docs/01-prerequisites.md").read_text(encoding="utf-8")
ENVIRONMENT_SETUP = (ROOT / "docs/02-environment-setup.md").read_text(
    encoding="utf-8"
)
OBSERVABILITY = (ROOT / "docs/08-observability.md").read_text(encoding="utf-8")
APP_SOURCE = (ROOT / "app/app.py").read_text(encoding="utf-8")
APP_REQUIREMENTS = (ROOT / "app/requirements.txt").read_text(encoding="utf-8")


def main_content(document):
    return document.split("## 트러블슈팅", 1)[0]


def troubleshooting_content(document):
    return document.split("## 트러블슈팅", 1)[1]


def test_application_does_not_embed_application_insights_sdk():
    assert "azure-monitor-opentelemetry" not in APP_REQUIREMENTS
    assert "configure_azure_monitor" not in APP_SOURCE
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" not in APP_SOURCE


def test_normal_extension_installation_is_centralized_in_prerequisites():
    prerequisites_main = main_content(PREREQUISITES)
    environment_setup_main = main_content(ENVIRONMENT_SETUP)
    observability_main = main_content(OBSERVABILITY)

    assert "az extension add" not in environment_setup_main
    assert "az extension add" not in observability_main
    assert "az extension add --name application-insights" in prerequisites_main
    assert "az extension add --name authV2" in prerequisites_main
    assert "az extension add --name log-analytics" in prerequisites_main


def test_module_troubleshooting_keeps_extension_recovery_commands():
    environment_setup_troubleshooting = troubleshooting_content(ENVIRONMENT_SETUP)
    observability_troubleshooting = troubleshooting_content(OBSERVABILITY)

    assert (
        "az extension add --name application-insights"
        in environment_setup_troubleshooting
    )
    assert "az extension add --name log-analytics" in observability_troubleshooting
    assert (
        "az extension add --name application-insights"
        in observability_troubleshooting
    )


def test_step_three_uses_log_analytics_results_image():
    image_reference = (
        "![Log Analytics에서 AppServiceHTTPLogs KQL 결과 확인]"
        "(images/08-log-analytics-kql-results.png)"
    )

    assert image_reference in OBSERVABILITY
    assert (ROOT / "docs/images/08-log-analytics-kql-results.png").is_file()


def test_step_four_uses_managed_python_instrumentation():
    observability_main = main_content(OBSERVABILITY)
    step_four = observability_main.split(
        "## 4단계 — App Service 관리형 Application Insights 활성화", 1
    )[1]

    assert "ApplicationInsightsAgent_EXTENSION_VERSION=~3" in step_four
    assert "APPLICATIONINSIGHTS_CONNECTION_STRING" in step_four
    assert "AI_SETTINGS_OK=" in step_four
    assert "App Service Python 자동 계측" in step_four
    assert "Live Metrics를 지원하지 않습니다" in step_four
    assert "08-application-insights-live-metrics.png" not in OBSERVABILITY


def test_app_insights_requests_use_workspace_query_in_cloud_shell():
    observability_main = main_content(OBSERVABILITY)

    assert "az monitor app-insights query -g" not in observability_main
    assert observability_main.count("AppRequests") >= 2
    assert observability_main.count(
        "az monitor log-analytics query -w $LAW_CID"
    ) >= 2
    assert observability_main.count(
        "APPI_ID=$(az monitor app-insights component show"
    ) >= 1
    assert "_ResourceId =~ '$APPI_ID'" in observability_main
    assert "requests=sum(ItemCount)" in observability_main


def test_cloud_shell_msi_error_explains_workspace_query_path():
    observability_troubleshooting = troubleshooting_content(OBSERVABILITY)

    assert "api.applicationinsights.io" in observability_troubleshooting
    assert "지원하지 않는 MSI token audience" in observability_troubleshooting
    assert "```bash\naz logout" not in observability_troubleshooting
    assert "AppRequests" in observability_troubleshooting


def test_step_four_waits_for_restart_and_telemetry_ingestion():
    observability_main = main_content(OBSERVABILITY)
    step_four = observability_main.split(
        "## 4단계 — App Service 관리형 Application Insights 활성화", 1
    )[1]

    assert "HEALTH_CHECK_STATUS=1" in step_four
    assert "for attempt in $(seq 1 18); do" in step_four
    assert 'curl -fsS --max-time 10 "$APP_URL/health"' in step_four
    assert 'curl -fsS "$APP_URL/api/info" > /dev/null' in step_four
    assert "for attempt in $(seq 1 10); do" in step_four
    assert "APP_REQUEST_COUNT=" in step_four
    assert "sleep 30" in step_four
    assert "AppRequests 적재 확인 실패" in step_four


def test_step_four_demonstrates_application_insights_diagnostics():
    observability_main = main_content(OBSERVABILITY)
    step_four = observability_main.split(
        "## 4단계 — App Service 관리형 Application Insights 활성화", 1
    )[1]

    assert 'curl -fsS "$APP_URL/api/info"' in step_four
    assert 'curl -fsS "$APP_URL/slow?sec=3"' in step_four
    assert '"$APP_URL/workshop-not-found"' in step_four
    assert "ResultCode" in step_four
    assert "Success" in step_four
    assert "avg(DurationMs)" in step_four
    assert "percentile(DurationMs, 95)" in step_four
    assert "**Performance**" in step_four
    assert "**Failures**" in step_four
    assert "End-to-end transaction details" in step_four
    assert "Application map" in step_four
    assert "단일 노드" in step_four


def test_managed_instrumentation_portal_guidance_is_explicit():
    observability_main = main_content(OBSERVABILITY)

    assert "App Service → **Application Insights**" in observability_main
    assert "Enabled" in observability_main
    assert "**Performance**" in observability_main
    assert "**Failures**" in observability_main
    assert "**Transaction search**" in observability_main
    assert "**Application map**" in observability_main


def test_step_four_uses_application_insights_investigation_images():
    image_references = {
        "08-application-insights-performance.png": (
            "![Application Insights Performance에서 GET /slow의 "
            "3초 응답 시간 확인]"
        ),
        "08-application-insights-failures.png": (
            "![Application Insights Failures에서 "
            "GET /workshop-not-found 404 확인]"
        ),
        "08-application-insights-transaction-details.png": (
            "![Application Insights End-to-end transaction details에서 "
            "GET /slow 요청 확인]"
        ),
        "08-application-insights-application-map.png": (
            "![Application Insights Application map에서 "
            "App Service 애플리케이션 노드 확인]"
        ),
    }

    for filename, alt_text in image_references.items():
        assert f"{alt_text}(images/{filename})" in OBSERVABILITY
        assert (ROOT / "docs/images" / filename).is_file()


def test_redundant_validation_section_is_removed():
    assert "## 검증" not in OBSERVABILITY
    assert "### HTTP 로그 KQL 확인" not in OBSERVABILITY
    assert "### App Insights 텔레메트리 확인" not in OBSERVABILITY
    assert "## 트러블슈팅" in OBSERVABILITY
