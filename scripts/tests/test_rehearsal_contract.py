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
    assert "동시에 실패했습니다" in REHEARSAL
    assert 'if [ "$hey_status" -ne 0 ]; then' in REHEARSAL
    assert 'wait "$HEY_PID" || true' not in REHEARSAL
    assert 'echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS"' in DOCS
    assert "시험 A 실패: 다음 시험으로 진행하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
    assert "시험 B 실패: 결과를 해석하지 말고 6단계의 복원 명령을 실행하세요." in DOCS
    assert "동시에 실패했습니다" not in DOCS
    assert "HEY_STATUS=$hey_status" not in DOCS
    assert 'return "$observer_status"' not in DOCS
    assert 'return "$hey_status"' not in DOCS


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
