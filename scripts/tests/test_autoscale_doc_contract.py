from pathlib import Path


DOC = Path(__file__).parents[2] / "docs" / "07-autoscale.md"


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def test_step_one_is_direct_cli_flow():
    text = DOC.read_text(encoding="utf-8")
    step_one = section(
        text,
        "## 1단계 — Automatic scaling 활성화",
        "## 2단계 — hey 부하 도구 설치",
    )

    assert "verify_plan_configuration()" not in step_one
    assert "set_prewarmed_configuration()" not in step_one
    assert "enable_autoscale()" not in step_one
    assert step_one.count("az rest --method patch") == 2
    assert step_one.count("az rest --method get") == 2
    assert step_one.count("api-version=2024-11-01") == 4

    required_snippets = {
        "plan API version": "--uri \"${PLAN_ID}?api-version=2024-11-01\"",
        "app API version": "--uri \"${APP_ID}/config/web?api-version=2024-11-01\"",
        "plan SKU name": '"name":"P0v4"',
        "plan SKU tier": '"tier":"PremiumV4"',
        "plan SKU size": '"size":"P0v4"',
        "plan SKU family": '"family":"Pv4"',
        "plan SKU capacity": '"capacity":1',
        "automatic scaling enabled": '"elasticScaleEnabled":true',
        "maximum burst": '"maximumElasticWorkerCount":5',
        "minimum elastic instance count": '"minimumElasticInstanceCount":1',
        "prewarmed instance count": '"preWarmedInstanceCount":1',
        "plan read-back query": '--query "properties.{automaticScaling:elasticScaleEnabled,maximumBurst:maximumElasticWorkerCount}"',
        "web read-back query": '--query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"',
        "chained patch flow": "--output none &&",
        "stop-on-error guidance": "오류가 출력되거나 `Automatic scaling 설정 완료`가 보이지 않으면 다음 단계로 진행하지 말고",
        "completion message": 'echo "Automatic scaling 설정 완료"',
    }

    for label, snippet in required_snippets.items():
        assert snippet in step_one, label


def test_reusable_helpers_are_defined_before_step_three_uses_them():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )

    verify_definition = step_three.index("verify_plan_configuration() {")
    set_definition = step_three.index("set_prewarmed_configuration() {")
    prepare_definition = step_three.index("prepare_instance_age_demo() {")
    first_prepare_use = step_three.index("\nprepare_instance_age_demo\n")

    assert prepare_definition < first_prepare_use
    assert verify_definition < first_prepare_use
    assert set_definition < first_prepare_use
