from pathlib import Path


ROOT = Path(__file__).parents[2]
PREREQUISITES = (ROOT / "docs/01-prerequisites.md").read_text(encoding="utf-8")
ENVIRONMENT_SETUP = (ROOT / "docs/02-environment-setup.md").read_text(
    encoding="utf-8"
)
OBSERVABILITY = (ROOT / "docs/08-observability.md").read_text(encoding="utf-8")


def main_content(document):
    return document.split("## 트러블슈팅", 1)[0]


def troubleshooting_content(document):
    return document.split("## 트러블슈팅", 1)[1]


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


def test_step_four_uses_application_insights_live_metrics_image():
    image_reference = (
        "![Application Insights Live Metrics에서 요청 텔레메트리 확인]"
        "(images/08-application-insights-live-metrics.png)"
    )

    assert image_reference in OBSERVABILITY
    assert (
        ROOT / "docs/images/08-application-insights-live-metrics.png"
    ).is_file()


def test_app_insights_requests_use_workspace_query_in_cloud_shell():
    observability_main = main_content(OBSERVABILITY)

    assert "az monitor app-insights query -g" not in observability_main
    assert observability_main.count("AppRequests") >= 2
    assert observability_main.count(
        "az monitor log-analytics query -w $LAW_CID"
    ) >= 4
    assert observability_main.count(
        "APPI_ID=$(az monitor app-insights component show"
    ) >= 2
    assert "_ResourceId =~ '$APPI_ID'" in observability_main
    assert "summarize count=sum(ItemCount) by name=Name" in observability_main


def test_cloud_shell_msi_error_explains_workspace_query_path():
    observability_troubleshooting = troubleshooting_content(OBSERVABILITY)

    assert "api.applicationinsights.io" in observability_troubleshooting
    assert "지원하지 않는 MSI token audience" in observability_troubleshooting
    assert "```bash\naz logout" not in observability_troubleshooting
    assert "AppRequests" in observability_troubleshooting


def test_step_four_waits_for_restart_and_telemetry_ingestion():
    observability_main = main_content(OBSERVABILITY)
    step_four = observability_main.split(
        "## 4단계 — App Insights 커넥션 스트링 주입", 1
    )[1]

    assert "HEALTH_CHECK_STATUS=1" in step_four
    assert "for attempt in $(seq 1 18); do" in step_four
    assert 'curl -fsS --max-time 10 "$APP_URL/health"' in step_four
    assert 'curl -fsS "$APP_URL/api/info" > /dev/null' in step_four
    assert "for attempt in $(seq 1 10); do" in step_four
    assert "APP_REQUEST_COUNT=" in step_four
    assert "sleep 30" in step_four
    assert "AppRequests 적재 확인 실패" in step_four
