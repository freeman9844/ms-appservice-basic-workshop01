import re
from pathlib import Path


DOC = Path(__file__).parents[2] / "docs" / "07-autoscale.md"
IMAGE = DOC.parent / "images" / "07-automatic-scaling-portal.png"


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def normalize(block):
    return "\n".join(line.rstrip() for line in block.strip().splitlines())


def test_step_one_is_direct_cli_flow():
    text = DOC.read_text(encoding="utf-8")
    step_one = section(
        text,
        "## 1단계 — Automatic scaling 활성화",
        "## 2단계 — hey 부하 도구 설치",
    )
    step_one_chain = step_one[
        step_one.index("az rest --method patch") : step_one.index(
            'echo "Automatic scaling 설정 완료"'
        )
        + len('echo "Automatic scaling 설정 완료"')
    ]
    expected_step_one_chain = "\n".join(
        [
            "az rest --method patch \\",
            '  --uri "${PLAN_ID}?api-version=2024-11-01" \\',
            '  --body \'{"sku":{"name":"P0v4","tier":"PremiumV4","size":"P0v4","family":"Pv4","capacity":1},"properties":{"elasticScaleEnabled":true,"maximumElasticWorkerCount":5}}\' \\',
            "  --output none &&",
            "az rest --method patch \\",
            '  --uri "${APP_ID}/config/web?api-version=2024-11-01" \\',
            '  --body \'{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}\' \\',
            "  --output none &&",
            'echo "Automatic scaling 설정 완료"',
        ]
    )

    assert "verify_plan_configuration()" not in step_one
    assert "set_prewarmed_configuration()" not in step_one
    assert "enable_autoscale()" not in step_one
    assert step_one.count("az rest --method patch") == 2
    assert step_one.count("az rest --method get") == 2
    assert step_one.count("api-version=2024-11-01") == 4
    assert normalize(step_one_chain) == normalize(expected_step_one_chain)

    required_snippets = {
        "plan read-back query": '--query "properties.{automaticScaling:elasticScaleEnabled,maximumBurst:maximumElasticWorkerCount}"',
        "web read-back query": '--query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"',
        "stop-on-error guidance": "오류가 출력되거나 `Automatic scaling 설정 완료`가 보이지 않으면 다음 단계로 진행하지 말고",
    }

    for label, snippet in required_snippets.items():
        assert snippet in step_one, label


def test_step_one_shows_portal_confirmation():
    text = DOC.read_text(encoding="utf-8")
    step_one = section(
        text,
        "## 1단계 — Automatic scaling 활성화",
        "## 2단계 — hey 부하 도구 설치",
    )
    portal_note = (
        "> 👁️ CLI로 설정한 Automatic scaling은 "
        "**Azure Portal 관리 콘솔**에서도 확인할 수 있습니다."
    )
    portal_path = (
        "> Web App 리소스에서 **App Service plan > Scale out**로 이동하면 "
        "**Scale out method = Automatic**, **Maximum burst = 5**, "
        "**Always ready instances = 1**을 확인할 수 있습니다."
    )
    portal_disclaimer = (
        "> 이 화면에는 Prewarmed 값이 표시되지 않으므로 "
        "`Prewarmed = 1`은 위 CLI 조회 결과로 확인합니다."
    )
    image_markdown = (
        "![Azure Portal Scale out 화면에서 Automatic, Maximum burst 5, "
        "Always ready instances 1 확인]"
        "(images/07-automatic-scaling-portal.png)"
    )

    assert portal_note in step_one
    assert portal_path in step_one
    assert portal_disclaimer in step_one
    assert "🖼️ **예상 화면 — Azure Portal Automatic scaling 설정**" in step_one
    assert image_markdown in step_one
    assert step_one.index(portal_note) < step_one.index(
        "> 👁️ ARM 속성 `elasticScaleEnabled`"
    )
    assert IMAGE.is_file()
    assert IMAGE.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


FUNCTION_DEFINITION = re.compile(
    r"(?m)^[A-Za-z_][A-Za-z0-9_]*\(\) \{"
)


def test_steps_three_and_four_use_direct_commands():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )

    step_four = section(
        text,
        "## 4단계 — 시험 A",
        "## 5단계 — scale-in 게이트 후 시험 B",
    )

    assert FUNCTION_DEFINITION.search(step_three) is None
    assert FUNCTION_DEFINITION.search(step_four) is None

    preparation_snippets = {
        "startup delay mutation": (
            'az webapp config appsettings set -g "$RG" -n "$APP" \\\n'
            "  --settings STARTUP_DELAY_SECONDS=20 --output none"
        ),
        "health polling": "for attempt in $(seq 1 18); do",
        "plan read-back": (
            '--query "properties.{automaticScaling:elasticScaleEnabled,'
            'maximumBurst:maximumElasticWorkerCount}"'
        ),
        "web app read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "trial A output": (
            'NO_PREWARM_OBSERVATIONS="$AB_DIR/'
            'prewarmed-0-observations.json"'
        ),
        "trial B output": (
            'PREWARM_OBSERVATIONS="$AB_DIR/'
            'prewarmed-1-observations.json"'
        ),
    }
    for label, snippet in preparation_snippets.items():
        assert snippet in step_three, label

    trial_a_snippets = {
        "Prewarmed zero PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":0}}\''
        ),
        "Prewarmed read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "single instance metric": "az monitor metrics list",
        "baseline instance": "BASELINE_INSTANCE=$(curl -fsS --max-time 10",
        "load command": 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"',
        "observer command": (
            'python3 "$REPO_DIR/scripts/observe_instances.py"'
        ),
        "load wait": 'wait "$HEY_PID"',
        "observer exit": "OBSERVER_STATUS=$?",
        "load exit": "HEY_STATUS=$?",
        "restoration guidance": "6단계의 **모듈 기본 상태로 복원**",
    }
    for label, snippet in trial_a_snippets.items():
        assert snippet in step_four, label

    assert "rehearsal helper 계약" not in step_four
    assert "cleanup_demo" not in step_four
    assert "handle_trial_observation" not in step_four


def test_steps_five_and_six_use_direct_commands():
    text = DOC.read_text(encoding="utf-8")
    step_five = section(
        text,
        "## 5단계 — scale-in 게이트 후 시험 B",
        "## 6단계 — 결과 해석 및 정리",
    )
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 검증",
    )

    assert FUNCTION_DEFINITION.search(step_five) is None
    assert FUNCTION_DEFINITION.search(step_six) is None

    trial_b_snippets = {
        "single instance metric": "az monitor metrics list",
        "Prewarmed one PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":1}}\''
        ),
        "baseline instance": "BASELINE_INSTANCE=$(curl -fsS --max-time 10",
        "load output": '"$AB_DIR/hey-burst-1.out"',
        "observer output": '--output "$PREWARM_OBSERVATIONS"',
        "load command": 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"',
        "observer command": (
            'python3 "$REPO_DIR/scripts/observe_instances.py"'
        ),
        "load wait": 'wait "$HEY_PID"',
        "restoration guidance": "6단계의 복원 명령",
    }
    for label, snippet in trial_b_snippets.items():
        assert snippet in step_five, label

    assert step_five.count(
        'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
    ) == 1
    assert "prime_url" not in step_five
    assert "wait_for_prewarmed" not in step_five

    restoration_snippets = {
        "Trial A result": '"$NO_PREWARM_OBSERVATIONS"',
        "Trial B result": '"$PREWARM_OBSERVATIONS"',
        "default PATCH": (
            '\'{"properties":{"minimumElasticInstanceCount":1,'
            '"preWarmedInstanceCount":1}}\''
        ),
        "startup delay deletion": (
            "az webapp config appsettings delete"
        ),
        "health polling": "for attempt in $(seq 1 18); do",
        "plan read-back": (
            '--query "properties.{automaticScaling:elasticScaleEnabled,'
            'maximumBurst:maximumElasticWorkerCount}"'
        ),
        "web read-back": (
            '--query "properties.{alwaysReady:minimumElasticInstanceCount,'
            'prewarmed:preWarmedInstanceCount}"'
        ),
        "startup delay read-back": (
            '--query "[?name==\'STARTUP_DELAY_SECONDS\'] | length(@)"'
        ),
    }
    for label, snippet in restoration_snippets.items():
        assert snippet in step_six, label
