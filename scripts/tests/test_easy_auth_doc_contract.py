from pathlib import Path


ROOT = Path(__file__).parents[2]
EASY_AUTH = (ROOT / "docs/09-easy-auth.md").read_text(encoding="utf-8")


def step_one_content():
    return EASY_AUTH.split(
        "## 1단계 — Entra 앱 등록 및 시크릿 생성", 1
    )[1].split("## 2단계 — Easy Auth 구성 및 활성화", 1)[0]


def test_step_one_explains_each_identity_setup_command():
    step_one = step_one_content()

    assert "Easy Auth v2 명령을 사용하기 위한 CLI 확장" in step_one
    assert "현재 로그인한 Entra 테넌트 ID" in step_one
    assert "App Registration을 생성" in step_one
    assert "Application(Client) ID를 CLIENT_ID에 저장" in step_one
    assert "OpenID Connect ID 토큰 발급" in step_one
    assert "애플리케이션 자신을 증명할 Client Secret" in step_one
    assert "사용자는 이 시크릿이 아니라 자신의 Entra 계정으로 로그인" in step_one
    assert "Managed Identity를 생성하거나 활성화하는 단계가 아닙니다" in step_one
    assert "12 정리에서 App Registration을 삭제" in step_one
