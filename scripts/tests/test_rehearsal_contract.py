from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REHEARSAL = (ROOT / "scripts/rehearsal.sh").read_text(encoding="utf-8")
DOCS = (ROOT / "docs/07-autoscale.md").read_text(encoding="utf-8")


def test_rehearsal_verifies_plan_and_trial_configuration():
    assert "verify_plan_configuration()" in REHEARSAL
    assert ".elasticScaleEnabled == true" in REHEARSAL
    assert ".maximumElasticWorkerCount == 5" in REHEARSAL
    assert "set_prewarmed_configuration 0" in REHEARSAL
    assert "set_prewarmed_configuration 1" in REHEARSAL
    assert "preWarmedInstanceCount" in REHEARSAL
    assert REHEARSAL.count("api-version=2024-11-01") >= 5


def test_rehearsal_preserves_hey_failures_and_stops_tracked_pid():
    assert "stop_tracked_hey()" in REHEARSAL
    assert 'kill "$pid"' in REHEARSAL
    assert 'process_state=$(ps -o stat= -p "$pid"' in REHEARSAL
    assert '[[ "$process_state" != *Z*' in REHEARSAL
    assert 'if [ "$observer_status" -ne 0 ]; then' in REHEARSAL
    assert 'return "$observer_status"' in REHEARSAL
    assert 'return "$hey_status"' not in REHEARSAL
    assert "HEY_FAILURE=1" in REHEARSAL
    assert "HEY_STATUS=$hey_status" in REHEARSAL
    assert 'if [ "$hey_status" -ne 0 ]; then' in REHEARSAL
    assert 'wait "$HEY_PID" || true' not in REHEARSAL
    assert (
        'echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS, metric exit=$METRIC_STATUS"'
        in DOCS
    )
    assert (
        "시험 A 실패: 세 결과를 비교하지 말고 6단계의 복원 명령을 실행하세요."
        in DOCS
    )
    assert (
        "시험 B 실패: 세 결과를 비교하지 말고 6단계의 복원 명령을 실행하세요."
        in DOCS
    )


def test_baseline_id_acquisition_is_distinct_from_observer_failure():
    assert "baseline ID acquisition failed" in REHEARSAL
    assert "return 3" in REHEARSAL
    assert 'test("\\\\S")' in REHEARSAL
    assert 'BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |' in DOCS
    assert 'test("\\\\S")' in DOCS
    assert "baseline ID acquisition failed" not in DOCS
    assert 'message="baseline ID acquisition failed."' not in DOCS


def test_docs_use_direct_restoration_instead_of_cleanup_helpers():
    assert "trap cleanup_demo EXIT" not in DOCS
    assert "trap 'cleanup_demo 130' INT" not in DOCS
    assert "trap 'cleanup_demo 143' TERM" not in DOCS
    assert "CLEANUP_RUNNING=0" not in DOCS
    assert "trap - EXIT INT TERM" not in DOCS
    assert "handle_trial_observation" not in DOCS
    assert "관찰 도구가 오류로 종료했습니다." not in DOCS
    assert "새 instance를 관찰하지 못했습니다." not in DOCS
    assert 'az webapp config appsettings delete -g "$RG" -n "$APP"' in DOCS
    assert 'echo "Always-ready=1, Prewarmed=1 복원 및 STARTUP_DELAY_SECONDS 삭제 완료"' in DOCS
    assert "for attempt in $(seq 1 18); do" in DOCS
    assert "/health 확인 실패: 다음 모듈로 진행하지 마세요." in DOCS
    assert 'wait "$HEY_PID" || true' not in DOCS
    assert "플랫폼 내부 라우팅이 실제로 시작된 정확한 시각은 아닙니다" in DOCS


def test_rehearsal_tracks_and_stops_metric_observer():
    hey_stop = REHEARSAL.split("stop_tracked_hey() {", 1)[1].split(
        "stop_tracked_metric_observer() {", 1
    )[0]
    metric_stop = REHEARSAL.split("stop_tracked_metric_observer() {", 1)[1].split(
        "cleanup() {", 1
    )[0]
    assert 'METRIC_OBSERVER_PID=""' in REHEARSAL
    assert "stop_tracked_metric_observer()" in REHEARSAL
    assert 'if [ -n "$METRIC_OBSERVER_PID" ]; then' in REHEARSAL
    assert 'kill "$pid"' in metric_stop
    assert 'wait "$pid"' in metric_stop
    assert 'return "$status"' in metric_stop
    assert 'wait "$pid" 2>/dev/null || true' not in metric_stop
    assert 'return "$status"' in hey_stop
    assert 'wait "$pid" 2>/dev/null || true' not in hey_stop
    assert REHEARSAL.index("stop_tracked_metric_observer()") < REHEARSAL.index(
        "cleanup()"
    )


def test_rehearsal_runs_metric_observer_before_load_for_both_trials():
    invocation = 'python3 "$REPO_DIR/scripts/observe_scaling_metric.py"'
    assert REHEARSAL.count(invocation) == 1
    run_trial = REHEARSAL.split("run_instance_age_trial() {", 1)[1].split(
        "handle_trial_observations() {", 1
    )[0]
    assert '--resource "$APP_ID"' in run_trial
    assert "--duration 240" in run_trial
    assert "--poll-interval 30" in run_trial
    assert '--output "$metric_file"' in run_trial
    assert run_trial.index(invocation) < run_trial.index(
        'hey -z 180s -c 100 -q 10 "$APP_URL/api/info"'
    )
    assert "METRIC_STATUS=$metric_status" in run_trial
    assert "METRIC_FAILURE=1" in run_trial
    assert (
        "실패: observer=${observer_status}, hey=${HEY_STATUS}, metric=${METRIC_STATUS}"
        in REHEARSAL
    )


def test_rehearsal_validates_metric_files_and_prints_timeline():
    assert (
        'NO_PREWARM_METRICS="$TMP_DIR/prewarmed-0-instance-count.json"'
        in REHEARSAL
    )
    assert 'PREWARM_METRICS="$TMP_DIR/prewarmed-1-instance-count.json"' in REHEARSAL
    assert '.metric == "InstanceCount"' in REHEARSAL
    assert '(.samples | type == "array" and length > 0)' in REHEARSAL
    assert ".metric_timestamp" in REHEARSAL
    assert ".observed_at" in REHEARSAL
    assert ".instance_count" in REHEARSAL
    assert "trial_started_at" in REHEARSAL
    assert "fromdateiso8601" in REHEARSAL
    assert "AutomaticScalingInstanceCount" not in REHEARSAL
    assert "--aggregation Average" in REHEARSAL
    assert ".average" in REHEARSAL
    assert "--aggregation Maximum" not in REHEARSAL
