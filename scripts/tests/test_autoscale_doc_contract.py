import re
from pathlib import Path


DOC = Path(__file__).parents[2] / "docs" / "07-autoscale.md"
IMAGE = DOC.parent / "images" / "07-automatic-scaling-portal.png"


def section(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def normalize(block):
    return "\n".join(line.rstrip() for line in block.strip().splitlines())


def code_block_after(text, marker):
    after_marker = text.split(marker, 1)[1]
    return after_marker.split("```bash", 1)[1].split("```", 1)[0]


def explanation_before_bash(text, marker):
    between = text.split(marker, 1)[1].split("```bash", 1)[0]
    assert "> 👁️" in between, marker
    return between


def assert_health_polling_contract(command_block, failure_message):
    assert "HEALTH_CHECK_STATUS=1" in command_block
    assert "for attempt in $(seq 1 18); do" in command_block
    assert 'HEALTH_BODY=$(curl -fsS --max-time 10 "$APP_URL/health" 2>/dev/null || true)' in command_block
    assert 'if jq -e \'.status == "ok"\' >/dev/null 2>&1 <<< "$HEALTH_BODY"; then' in command_block
    assert "printf '%s\\n' \"$HEALTH_BODY\"" in command_block
    assert "HEALTH_CHECK_STATUS=0" in command_block
    assert 'if [ "$attempt" -lt 18 ]; then' in command_block
    assert "sleep 5" in command_block
    assert 'if [ "$HEALTH_CHECK_STATUS" -ne 0 ]; then' in command_block
    assert failure_message in command_block
    assert "false" in command_block
    assert 'if [ "$attempt" -eq 18 ]; then' not in command_block

    sleep_guard = """if [ "$attempt" -lt 18 ]; then
    sleep 5
  fi"""
    assert sleep_guard in command_block
    assert command_block.index("HEALTH_CHECK_STATUS=1") < command_block.index(
        "for attempt in $(seq 1 18); do"
    )
    assert command_block.index("HEALTH_CHECK_STATUS=0") < command_block.index("break")
    assert command_block.index("done") < command_block.index(
        'if [ "$HEALTH_CHECK_STATUS" -ne 0 ]; then'
    )


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


def test_steps_three_through_six_explain_each_execution_block():
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

    contracts = [
        (
            step_three,
            "🟢 **실행 — 시작 지연 설정과 결과 경로 준비**",
            ["STARTUP_DELAY_SECONDS=20", "JSON"],
        ),
        (
            step_three,
            "🟢 **실행 — 앱 준비 상태 확인**",
            ["최대 18회", "status", "ok"],
        ),
        (
            step_three,
            "🟢 **실행 — Automatic scaling 설정 재확인**",
            ["Maximum burst", "Always-ready", "Prewarmed"],
        ),
        (
            step_four,
            "🟢 **실행 — Prewarmed=0 설정**",
            ["Prewarmed", "0", "조회"],
        ),
        (
            step_four,
            "🟢 **실행 — 단일 인스턴스 기준 상태 확인**",
            ["최근 10분", "1분", "count=1"],
        ),
        (
            step_four,
            "🟢 **실행 — 시험 A 관찰**",
            ["기준 instance", "180초", "새 instance", "exit code"],
        ),
        (
            step_five,
            "🟢 **실행 — 시험 B 시작 전 단일 인스턴스 기준 상태 확인**",
            ["시험 A", "scale-in", "count=1"],
        ),
        (
            step_five,
            "🟢 **실행 — Prewarmed=1 설정**",
            ["Prewarmed", "1", "조회"],
        ),
        (
            step_five,
            "🟢 **실행 — 시험 B 관찰**",
            ["기준 instance", "180초", "새 instance", "exit code"],
        ),
        (
            step_six,
            "🟢 **실행 — 결과 표 출력**",
            ["두 JSON", "TSV", "승자"],
        ),
        (
            step_six,
            "🟢 **실행 — 모듈 기본 상태로 복원**",
            ["Always-ready=1", "Prewarmed=1", "STARTUP_DELAY_SECONDS"],
        ),
        (
            step_six,
            "🟢 **실행 — 복원 후 앱 준비 확인**",
            ["최대 18회", "status", "ok"],
        ),
        (
            step_six,
            "🟢 **실행 — 복원 상태 조회**",
            ["Plan", "Web App", "STARTUP_DELAY_SECONDS"],
        ),
    ]

    for block, marker, required_terms in contracts:
        explanation = explanation_before_bash(block, marker)
        for term in required_terms:
            assert term in explanation, (marker, term)

    assert (
        "`REPO_DIR`는 `scripts/observe_instances.py`의 경로를 고정하기 위해 "
        "여기서 항상 정의합니다."
    ) in text


def test_trial_observation_runs_only_after_baseline_capture_succeeds():
    text = DOC.read_text(encoding="utf-8")
    step_four = section(
        text,
        "## 4단계 — 시험 A",
        "## 5단계 — scale-in 게이트 후 시험 B",
    )
    step_five = section(
        text,
        "## 5단계 — scale-in 게이트 후 시험 B",
        "## 6단계 — 결과 해석 및 정리",
    )

    trial_contracts = [
        (
            "trial A",
            code_block_after(step_four, "🟢 **실행 — 시험 A 관찰**"),
            'echo "시험 A 기준 instance 확인 실패: 6단계의 모듈 기본 상태로 복원 명령을 실행한 뒤 3단계부터 다시 시도하세요." >&2',
        ),
        (
            "trial B",
            code_block_after(step_five, "🟢 **실행 — 시험 B 관찰**"),
            'echo "시험 B 기준 instance 확인 실패: 6단계의 복원 명령을 실행한 뒤 결과를 해석하지 말고 3단계부터 다시 시도하세요." >&2',
        ),
    ]

    for label, command_block, failure_message in trial_contracts:
        assert 'if BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |' in command_block, label
        assert "then" in command_block, label
        assert 'echo "Prewarmed=' in command_block, label
        assert 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"' in command_block, label
        assert 'python3 "$REPO_DIR/scripts/observe_instances.py"' in command_block, label
        assert "else" in command_block, label
        assert failure_message in command_block, label
        assert "false" in command_block, label

        then_branch = command_block.split("then", 1)[1].split("else", 1)[0]
        else_branch = command_block.split("else", 1)[1].split("fi", 1)[0]

        assert 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"' in then_branch, label
        assert 'python3 "$REPO_DIR/scripts/observe_instances.py"' in then_branch, label
        assert 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"' not in else_branch, label
        assert 'python3 "$REPO_DIR/scripts/observe_instances.py"' not in else_branch, label


def test_health_polling_blocks_fail_after_final_attempt_without_sleeping():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 검증",
    )

    health_contracts = [
        (
            "step 3 health check",
            code_block_after(step_three, "🟢 **실행 — 앱 준비 상태 확인**"),
            'echo "/health 확인 실패: 6단계의 복원 명령을 실행하세요." >&2',
        ),
        (
            "step 6 health check",
            code_block_after(step_six, "🟢 **실행 — 복원 후 앱 준비 확인**"),
            'echo "/health 확인 실패: 다음 모듈로 진행하지 마세요." >&2',
        ),
    ]

    for label, command_block, failure_message in health_contracts:
        assert_health_polling_contract(command_block, failure_message), label
