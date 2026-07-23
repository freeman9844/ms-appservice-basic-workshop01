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
