# 03. 코드 배포

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

---

## 목표

이 모듈에서는 Flask 애플리케이션(v1)을 zip 배포 방식으로 Azure App Service에 업로드하고 외부에서 접속합니다.

- Oryx 빌드(`SCM_DO_BUILD_DURING_DEPLOYMENT=true`)를 활성화하여 서버 측 pip install을 수행합니다.
- zip 아카이브를 생성하고 `az webapp deploy`로 프로덕션 슬롯에 배포합니다.
- `/health`·`/api/info` 엔드포인트로 배포 성공 여부를 검증합니다.
- 로그 스트림을 통해 실시간 요청·에러 로그를 확인합니다.

## 소요 시간

약 10–15분

---

## 각 모듈 첫머리 변수 재설정 블록

> 👁️ **Cloud Shell 세션이 끊긴 경우** `SUFFIX` 값을 아래에 입력하여 변수를 재구성하십시오.

```bash
# ── 변수 재설정 블록 (SUFFIX를 직접 입력) ──
SUFFIX=<이전에_메모한_값>
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
```

---

## 1단계 — Oryx 빌드 설정

🟢 **실행**

```bash
az webapp config appsettings set -g $RG -n $APP \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

> 👁️ **개념 — Oryx 빌드**
>
> `SCM_DO_BUILD_DURING_DEPLOYMENT=true`를 설정하면 Azure가 zip 안의 `requirements.txt`를 읽어 **서버 측 pip install**을 수행합니다.
> 빌드 완료 후 `app.py`의 `app` 객체를 **gunicorn**으로 자동 기동합니다.
> 첫 빌드는 패키지 다운로드 포함 **1–3분**, 이후 콜드스타트 추가 수십 초가 소요될 수 있습니다.

---

## 2단계 — zip 아카이브 생성 및 배포

🟢 **실행**

```bash
cd ~/ms-appservice-basic-workshop01/app
zip -r /tmp/app-v1.zip . -x "tests/*" -x "__pycache__/*" -x "*.pyc"
az webapp deploy -g $RG -n $APP --src-path /tmp/app-v1.zip --type zip --track-status
```

> 👁️ **참고** — `-x "tests/*" -x "__pycache__/*" -x "*.pyc"` 옵션으로 테스트 파일과 캐시를 제외합니다.
> `tests/` 디렉터리가 포함되더라도 동작에는 영향이 없으나 zip 크기가 늘어납니다.

---

## 3단계 — 외부 접속 검증

🟢 **실행**

```bash
curl -s $APP_URL/health
curl -s $APP_URL/api/info | jq
```

📋 **예상 출력 — `/health`**

```json
{"status":"ok"}
```

📋 **예상 출력 — `/api/info`**

```json
{
  "version": "v1",
  "slot": "production",
  "instance": "..."
}
```

🖼️ **스크린샷** — 브라우저에서 `$APP_URL`을 열면 파란색 v1 페이지가 표시됩니다 *(리허설에서 캡처 예정)*.

---

## 4단계 — 로그 스트림

🟢 **실행**

```bash
az webapp log config -g $RG -n $APP --application-logging filesystem --web-server-logging filesystem
az webapp log tail -g $RG -n $APP
# 다른 탭에서 curl $APP_URL/ 후 로그 확인, Ctrl+C로 종료
```

---

## 검증

`/api/info` 응답에서 다음 세 필드를 확인합니다.

| 필드 | 예상 값 | 역할 |
|------|---------|------|
| `version` | `v1` | 배포된 코드 버전 |
| `slot` | `production` | 현재 슬롯(이후 모듈에서 staging과 비교) |
| `instance` | 임의 문자열 | 인스턴스 식별자(이후 스케일아웃 관찰에 활용) |

> 👁️ 이 세 필드는 이후 **슬롯 스왑**, **스케일아웃**, **트래픽 분산** 모듈에서 핵심 관찰 도구로 활용됩니다.

---

## 트러블슈팅

### (1) 배포 빌드 실패

`--track-status` 출력에서 `Failed` 또는 오류 메시지가 나타나면 배포 로그를 확인합니다.

```bash
az webapp log deployment show -g $RG -n $APP
```

`requirements.txt` 구문 오류 또는 패키지 이름 오타가 가장 흔한 원인입니다.

### (2) 502 게이트웨이 오류 / 콜드스타트

배포 직후 첫 요청에서 502가 발생하면 gunicorn 기동이 완료되지 않은 것입니다.
20–30초 후 재시도합니다. 로그 스트림에서 `Booting worker` 메시지를 확인하면 기동 완료입니다.

### (3) zip에 tests/ 포함

`-x "tests/*"` 옵션을 지정하지 않아도 서비스 동작에는 문제가 없습니다.
zip 크기가 다소 커질 뿐이며, Oryx 빌드는 `tests/`를 무시합니다.

---

이전 모듈: [02. 환경 준비](02-environment-setup.md) | 다음 모듈: [04. 앱 설정](04-app-settings.md)
