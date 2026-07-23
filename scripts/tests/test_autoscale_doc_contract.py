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
    assert "🟢 **실행 — Automatic scaling 설정 재확인**" not in step_three
    assert "automaticScaling:elasticScaleEnabled" not in step_three
    assert "alwaysReady:minimumElasticInstanceCount" not in step_three

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
        "## 트러블슈팅",
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
        "## 트러블슈팅",
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
    ]

    for block, marker, required_terms in contracts:
        explanation = explanation_before_bash(block, marker)
        for term in required_terms:
            assert term in explanation, (marker, term)

    assert (
        "`REPO_DIR`는 `scripts/observe_instances.py`의 경로를 고정하기 위해 "
        "여기서 항상 정의합니다."
    ) in text


def test_trial_observation_explanations_describe_command_flow():
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

    contracts = [
        (
            "Trial A",
            explanation_before_bash(
                step_four, "🟢 **실행 — 시험 A 관찰**"
            ),
            [
                "`curl`과 `jq`",
                "`hey -z 180s -c 100 -q 10`",
                "`HEY_PID=$!`",
                "`--concurrency 30`",
                "`--request-timeout 5`",
                "`$NO_PREWARM_OBSERVATIONS`",
                "세 exit code가 모두 0",
            ],
        ),
        (
            "Trial B",
            explanation_before_bash(
                step_five, "🟢 **실행 — 시험 B 관찰**"
            ),
            [
                "시험 A와 같은 순서",
                "`curl`과 `jq`",
                "`hey -z 180s -c 100 -q 10`",
                "`HEY_PID=$!`",
                "`--concurrency 30`",
                "`--request-timeout 5`",
                "`$PREWARM_OBSERVATIONS`",
                "세 exit code가 모두 0",
            ],
        ),
    ]

    for label, explanation, required_terms in contracts:
        assert explanation.count("\n> 1. ") == 1, label
        for number in range(2, 6):
            assert f"\n> {number}. " in explanation, (label, number)
        for term in required_terms:
            assert term in explanation, (label, term)


def test_trial_a_expected_output_uses_successful_metric_rehearsal():
    text = DOC.read_text(encoding="utf-8")
    step_four = section(
        text,
        "## 4단계 — 시험 A",
        "## 5단계 — scale-in 게이트 후 시험 B",
    )

    required_lines = [
        "📋 **예상 출력** (2026-07-23 리허설 예시)",
        "metric_timestamp\tobserved_at\tinstance_count",
        "instance\tstarted_at\tfirst_seen_at\tfirst_response_age",
        "2026-07-23T03:20:00Z\t2026-07-23T03:21:35Z\t1",
        "a2b002c6\t2026-07-23T03:22:05Z\t2026-07-23T03:22:33Z\t28",
        "5bef3ff3\t2026-07-23T03:22:22Z\t2026-07-23T03:23:03Z\t41",
        "bd29045b\t2026-07-23T03:22:24Z\t2026-07-23T03:23:04Z\t40",
        "3122a953\t2026-07-23T03:22:16Z\t2026-07-23T03:23:04Z\t48",
        "2026-07-23T03:24:00Z\t2026-07-23T03:24:45Z\t5",
        "observer exit=0, hey exit=0, metric exit=0",
    ]

    for line in required_lines:
        assert line in step_four

    assert "metric과 instance 행의 출력 순서는 실행마다 달라질 수 있습니다" in step_four


def test_trial_b_expected_output_uses_successful_metric_rehearsal():
    text = DOC.read_text(encoding="utf-8")
    step_five = section(
        text,
        "## 5단계 — scale-in 게이트 후 시험 B",
        "## 6단계 — 결과 해석 및 정리",
    )

    required_lines = [
        "📋 **예상 출력** (2026-07-23 리허설 예시)",
        "metric_timestamp\tobserved_at\tinstance_count",
        "instance\tstarted_at\tfirst_seen_at\tfirst_response_age",
        "2026-07-23T03:28:00Z\t2026-07-23T03:29:25Z\t1",
        "69e069d8\t2026-07-23T03:29:35Z\t2026-07-23T03:30:00Z\t25",
        "9b19c4d6\t2026-07-23T03:29:36Z\t2026-07-23T03:30:01Z\t25",
        "8e0e812d\t2026-07-23T03:30:13Z\t2026-07-23T03:30:52Z\t39",
        "5d90b391\t2026-07-23T03:30:21Z\t2026-07-23T03:30:52Z\t31",
        "2026-07-23T03:31:00Z\t2026-07-23T03:31:32Z\t3",
        "2026-07-23T03:32:00Z\t2026-07-23T03:32:35Z\t5",
        "observer exit=0, hey exit=0, metric exit=0",
    ]

    for line in required_lines:
        assert line in step_five

    assert "metric과 instance 행의 출력 순서는 실행마다 달라질 수 있습니다" in step_five
    assert "`instance_count=3`은 1분 구간의 Average" in step_five


def test_step_six_explains_the_observed_prewarmed_benefit():
    text = DOC.read_text(encoding="utf-8")
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 트러블슈팅",
    )

    required_snippets = {
        "summary heading": "🟢 **실행 — 관찰 범위 요약**",
        "dynamic summary": "jq -s -r '",
        "summary columns": (
            '["trial","samples","min_age","max_age","range"]'
        ),
        "minimum": "$ages[0]",
        "maximum": "$ages[-1]",
        "range": "($ages[-1] - $ages[0])",
        "official link": (
            "https://learn.microsoft.com/azure/app-service/"
            "manage-automatic-scaling"
        ),
        "buffer mechanism": "warmed capacity buffer",
        "readiness floor": "약 20초의 readiness floor",
        "Trial A evidence": "28–48초",
        "Trial A range": "범위 20초",
        "Trial B evidence": "25–39초",
        "Trial B range": "범위 14초",
        "equal samples": "Trial B(Prewarmed=1)는 4개 instance",
        "maximum difference": "최댓값은 9초",
        "range difference": "범위는 6초",
        "descriptive statistics": "기술 통계",
        "no internal label": "개별 instance의 active/Prewarmed 상태",
        "no causality": "인과관계 증명은 아닙니다",
    }

    for label, snippet in required_snippets.items():
        assert snippet in step_six, label

    expected_summary = "\n".join(
        [
            "trial\tsamples\tmin_age\tmax_age\trange",
            "Prewarmed=0\t4\t28\t48\t20",
            "Prewarmed=1\t4\t25\t39\t14",
        ]
    )
    assert expected_summary in step_six

    expected_observations = "\n".join(
        [
            "Prewarmed=0\ta2b002c6\t2026-07-23T03:22:05Z\t2026-07-23T03:22:33Z\t28",
            "Prewarmed=0\t5bef3ff3\t2026-07-23T03:22:22Z\t2026-07-23T03:23:03Z\t41",
            "Prewarmed=0\tbd29045b\t2026-07-23T03:22:24Z\t2026-07-23T03:23:04Z\t40",
            "Prewarmed=0\t3122a953\t2026-07-23T03:22:16Z\t2026-07-23T03:23:04Z\t48",
            "Prewarmed=1\t69e069d8\t2026-07-23T03:29:35Z\t2026-07-23T03:30:00Z\t25",
            "Prewarmed=1\t9b19c4d6\t2026-07-23T03:29:36Z\t2026-07-23T03:30:01Z\t25",
            "Prewarmed=1\t8e0e812d\t2026-07-23T03:30:13Z\t2026-07-23T03:30:52Z\t39",
            "Prewarmed=1\t5d90b391\t2026-07-23T03:30:21Z\t2026-07-23T03:30:52Z\t31",
        ]
    )
    assert "📋 **예상 출력** (2026-07-23 리허설 예시)" in step_six
    assert expected_observations in step_six
    assert "4개 대 2개" not in step_six
    assert "모두 23초" not in step_six


def test_step_six_ends_after_observed_benefit_and_has_no_validation_section():
    text = DOC.read_text(encoding="utf-8")
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 트러블슈팅",
    )

    assert "### 이번 실측에서 보인 이점" in step_six
    for removed in [
        "### 이 결과가 증명하지 않는 것",
        "### 다른 결과가 나오면",
        "🟢 **실행 — 모듈 기본 상태로 복원**",
        "🟢 **실행 — 복원 후 앱 준비 확인**",
        "🟢 **실행 — 복원 상태 조회**",
        "## 검증",
        "### A/B 관찰 파일 확인",
    ]:
        assert removed not in text


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

        outer_else = f"else\n  {failure_message}\n"
        then_branch = command_block.split("then", 1)[1].split(outer_else, 1)[0]
        else_branch = command_block.split(outer_else, 1)[1].rsplit("fi", 1)[0]

        assert 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"' in then_branch, label
        assert 'python3 "$REPO_DIR/scripts/observe_instances.py"' in then_branch, label
        assert 'kill "$HEY_PID" "$METRIC_PID" 2>/dev/null || true' in then_branch, label
        assert 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"' not in else_branch, label
        assert 'python3 "$REPO_DIR/scripts/observe_instances.py"' not in else_branch, label


def test_health_polling_blocks_fail_after_final_attempt_without_sleeping():
    text = DOC.read_text(encoding="utf-8")
    step_three = section(
        text,
        "## 3단계 — Prewarmed A/B 비교 준비",
        "## 4단계 — 시험 A",
    )

    health_contracts = [
        (
            "step 3 health check",
            code_block_after(step_three, "🟢 **실행 — 앱 준비 상태 확인**"),
            'echo "/health 확인 실패: 6단계의 복원 명령을 실행하세요." >&2',
        ),
    ]

    for label, command_block, failure_message in health_contracts:
        assert_health_polling_contract(command_block, failure_message), label


def test_trials_record_supported_instance_count_metric():
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

    assert (
        'NO_PREWARM_METRICS="$AB_DIR/prewarmed-0-instance-count.json"'
        in step_three
    )
    assert (
        'PREWARM_METRICS="$AB_DIR/prewarmed-1-instance-count.json"'
        in step_three
    )

    for label, block, marker, output in [
        (
            "Trial A",
            step_four,
            "🟢 **실행 — 시험 A 관찰**",
            "$NO_PREWARM_METRICS",
        ),
        (
            "Trial B",
            step_five,
            "🟢 **실행 — 시험 B 관찰**",
            "$PREWARM_METRICS",
        ),
    ]:
        command = code_block_after(block, marker)
        metric = 'python3 "$REPO_DIR/scripts/observe_scaling_metric.py"'
        load = 'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
        assert metric in command, label
        assert '--resource "$APP_ID"' in command, label
        assert "--duration 240" in command, label
        assert "--poll-interval 30" in command, label
        assert f'--output "{output}"' in command, label
        assert command.index(metric) < command.index(load), label
        assert "METRIC_PID=$!" in command, label
        assert 'wait "$METRIC_PID"' in command, label
        assert "METRIC_STATUS=$?" in command, label
        assert "metric exit=$METRIC_STATUS" in command, label

    combined_steps = step_four + step_five
    assert combined_steps.count("--aggregation Average") == 2
    assert combined_steps.count("{time:timeStamp,count:average}") == 2
    assert "--aggregation Maximum" not in combined_steps
    assert "{time:timeStamp,count:maximum}" not in combined_steps


def test_step_six_prints_and_limits_metric_timeline():
    text = DOC.read_text(encoding="utf-8")
    step_six = section(
        text,
        "## 6단계 — 결과 해석 및 정리",
        "## 트러블슈팅",
    )

    assert "🟢 **실행 — InstanceCount 타임라인 출력**" in step_six
    assert "trial_started_at" in step_six
    assert "metric_timestamp" in step_six
    assert "observed_at" in step_six
    assert "instance_count" in step_six
    assert "`PT1M`" in step_six
    assert "Automatic Scaling Instance Count" in step_six
    assert "REST API 이름은 `InstanceCount`" in step_six
    assert "배포된 Prewarmed instance를 포함할 수" in step_six
    assert "개별 instance의 active/Prewarmed 상태" in step_six
    assert "정확한 activation 시각" in step_six
    assert "capacity 효율" in step_six
    assert "보조 증거" in step_six
    assert "AutomaticScalingInstanceCount" not in step_six
