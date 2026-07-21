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
    assert 'if [ "$observer_status" -ne 0 ]; then' in REHEARSAL
    assert 'return "$observer_status"' in REHEARSAL
    assert "HEY_FAILURE=1" in REHEARSAL
    assert 'if [ "$hey_status" -ne 0 ]; then' in REHEARSAL
    assert 'wait "$HEY_PID" || true' not in REHEARSAL


def test_baseline_id_acquisition_is_distinct_from_observer_failure():
    assert "baseline ID acquisition failed" in REHEARSAL
    assert "return 3" in REHEARSAL
    assert "baseline ID acquisition failed" in DOCS
    assert 'message="baseline ID acquisition failed."' in DOCS


def test_docs_include_learner_safe_cleanup_and_matching_status_mapping():
    assert "trap cleanup_demo EXIT" in DOCS
    assert "trap 'cleanup_demo 130' INT" in DOCS
    assert "trap 'cleanup_demo 143' TERM" in DOCS
    assert "CLEANUP_RUNNING=0" in DOCS
    assert "trap - EXIT INT TERM" in DOCS
    assert "handle_trial_observation" in DOCS
    assert "관찰 도구가 오류로 종료했습니다." in DOCS
    assert "새 instance를 관찰하지 못했습니다." in DOCS
    assert 'wait "$HEY_PID" || true' not in DOCS
    assert "플랫폼 내부 라우팅이 실제로 시작된 정확한 시각은 아닙니다" in DOCS
