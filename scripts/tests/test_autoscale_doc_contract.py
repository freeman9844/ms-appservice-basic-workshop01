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
    assert "maximumElasticWorkerCount\":5" in step_one
    assert "preWarmedInstanceCount\":1" in step_one
    assert "--output none &&" in step_one
    assert 'echo "Automatic scaling 설정 완료"' in step_one


def test_reusable_helpers_are_defined_before_step_three_uses_them():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )

    verify_definition = step_three.index("verify_plan_configuration()")
    set_definition = step_three.index("set_prewarmed_configuration()")
    first_prepare_use = step_three.index("prepare_instance_age_demo()")

    assert verify_definition < first_prepare_use
    assert set_definition < first_prepare_use
