# 03. 코드 배포

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **예상 화면** = 브라우저/포털 스크린샷 참고

---

## 목표

이 모듈에서는 Flask 애플리케이션(v1)을 zip 배포 방식으로 Azure App Service에 업로드하고 외부에서 접속합니다.

- Oryx 빌드(`SCM_DO_BUILD_DURING_DEPLOYMENT=true`)를 활성화하여 서버 측 pip install을 수행합니다.
- zip 아카이브를 생성하고 `az webapp deploy`로 프로덕션 슬롯에 배포합니다.
- `/health`·`/api/info` 엔드포인트로 배포 성공 여부를 검증합니다.
- 로그 스트림을 통해 실시간 요청·에러 로그를 확인합니다.

완성 후의 구조는 다음과 같습니다.

```mermaid
flowchart LR
    U(("🌐 사용자")) -->|"HTTPS"| A
    CS["☁️ Cloud Shell<br/>(az webapp deploy)"] -->|"zip 배포<br/>Oryx 빌드"| A
    subgraph PLAN["App Service Plan (plan-appsvcworkshop-SUFFIX)"]
        A["**app-appsvcworkshop-SUFFIX**<br/>production 슬롯<br/>Flask v1 · gunicorn"]
    end
```

---

## 0단계 — (선택) 변수 재설정

> ⏭️ **02 모듈에서 이어서 같은 터미널로 진행 중이라면 이 단계는 건너뛰세요.**
> 새 터미널 세션을 열었거나 Cloud Shell이 재시작되어 변수가 사라진 경우에만 실행합니다.
> `SUFFIX` 는 **02 모듈에서 사용한 값과 동일하게** 입력하세요.

🟢 **실행**

```bash
SUFFIX=<이전에_메모한_값>
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
echo "APP_URL=$APP_URL"
```

📋 **예상 출력**

```
APP_URL=https://app-appsvcworkshop-<SUFFIX>.azurewebsites.net
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

배포할 애플리케이션은 Python **Flask 기반의 v1 웹앱**입니다. 홈 화면과 함께 상태 확인용 `/health`, 앱 버전·슬롯·인스턴스 정보를 반환하는 `/api/info` 엔드포인트를 제공하며, 이후 모듈에서 앱 설정·슬롯 스왑·트래픽 분할·자동 스케일 동작을 관찰하는 데 사용합니다.

`app.py`와 의존성 목록인 `requirements.txt`를 zip 파일로 묶어 App Service에 배포합니다.

🟢 **실행**

```bash
cd ~/ms-appservice-basic-workshop01/app
zip -r /tmp/app-v1.zip . -x "tests/*" -x "__pycache__/*" -x "*.pyc"
az webapp deploy -g $RG -n $APP --src-path /tmp/app-v1.zip --type zip --track-status
```

📋 **예상 출력** (배포 ID와 시각은 실행할 때마다 달라집니다)

```text
  adding: requirements.txt (deflated 1%)
  adding: app.py (deflated 49%)
Note: 'az webapp deploy' does not run build automation (dependency installation,
compilation, etc.) by default for Linux web apps. If your package is not pre-built,
set the app setting SCM_DO_BUILD_DURING_DEPLOYMENT=true to enable builds during deployment.
Initiating deployment
Deploying from local path: /tmp/app-v1.zip
Warming up Kudu before deployment.
Warmed up Kudu instance successfully.
Polling the status of sync deployment. Start Time: <배포 시작 시각> UTC
Status: Build successful. Time: 1(s)
Status: Site started successfully. Time: 16(s)
Deployment has completed successfully
You can visit your app at: http://app-appsvcworkshop-<SUFFIX>.azurewebsites.net
{
  "id": "/subscriptions/<subscription-id>/resourceGroups/rg-appsvcworkshop-<SUFFIX>/providers/Microsoft.Web/sites/app-appsvcworkshop-<SUFFIX>/deploymentStatus/<deployment-id>",
  "location": "Korea Central",
  "name": "<deployment-id>",
  "properties": {
    "deploymentId": "<deployment-id>",
    "errors": null,
    "failedInstancesLogs": null,
    "numberOfInstancesFailed": 0,
    "numberOfInstancesInProgress": 0,
    "numberOfInstancesSuccessful": 1,
    "status": "RuntimeSuccessful"
  },
  "resourceGroup": "rg-appsvcworkshop-<SUFFIX>",
  "type": "Microsoft.Web/sites/deploymentStatus"
}
```

> 👁️ `Build successful`, `Site started successfully`, `Deployment has completed successfully`, `"status": "RuntimeSuccessful"`이 표시되면 배포가 완료된 것입니다. 출력의 Note는 일반 안내이며, 1단계에서 `SCM_DO_BUILD_DURING_DEPLOYMENT=true`를 이미 설정했으므로 Oryx 빌드가 정상 실행됩니다.

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
  "color": "#2563eb",
  "instance": "<instance-id>",
  "message": "App Service 워크숍에 오신 것을 환영합니다",
  "python": "3.12.x",
  "slot": "production",
  "started_at": "<UTC 시작 시각>",
  "version": "v1"
}
```

> 👁️ `instance`는 현재 요청을 처리한 App Service 인스턴스 식별자이며, `started_at`은 앱 프로세스가 시작된 UTC 시각입니다. 두 값과 Python 패치 버전은 실행 환경에 따라 달라집니다.

🖼️ **예상 화면** — 브라우저에서 `$APP_URL`을 열면 파란색 v1 페이지가 표시됩니다.

![브라우저에 표시된 파란색 App Service 워크숍 v1 production 페이지](images/03-app-v1-production.png)

---

## 4단계 — 로그 스트림

App Service의 로그를 파일 시스템에 기록하도록 활성화한 뒤, Cloud Shell에서 실시간으로 스트리밍합니다.

| 로그 종류 | 설정 | 확인 내용 |
|---|---|---|
| **애플리케이션 로그** | `--application-logging filesystem` | Python·Flask·gunicorn이 표준 출력과 표준 오류에 기록한 시작·오류 메시지 |
| **웹 서버 로그** | `--web-server-logging filesystem` | HTTP 요청 경로, 응답 상태 코드 등 웹 요청 처리 정보 |

🟢 **실행**

```bash
# 애플리케이션 로그(verbose 수준)와 웹 서버 로그를 App Service 파일 시스템에 기록
az webapp log config -g $RG -n $APP \
  --application-logging filesystem --level verbose --web-server-logging filesystem

# 활성화된 로그를 현재 터미널에 실시간 출력
az webapp log tail -g $RG -n $APP
```

> 👁️ `--level`을 지정하지 않으면 기본값 `error`가 적용되어 정보성(INFO) 로그가 기록되지 않을 수 있습니다. 또한 파일 시스템 애플리케이션 로그는 디스크 보호를 위해 **활성화 후 12시간이 지나면 자동으로 비활성화**됩니다. 장기 보관이 필요하면 [08. 관찰 가능성](08-observability.md)의 Log Analytics 연동을 사용하십시오.

`az webapp log tail`은 새 로그를 기다리며 계속 실행되는 명령입니다. 이 Cloud Shell 탭은 그대로 두고 **새 Cloud Shell 탭**을 연 다음 요청을 전송합니다.

🟢 **실행** (새 Cloud Shell 탭)

```bash
curl -s $APP_URL/health
curl -s $APP_URL/api/info | jq
```

📋 **예상 출력** (로그 시각·인스턴스·메시지 형식은 달라질 수 있습니다)

```text
Connecting to log stream...
...
GET /health ... 200
GET /api/info ... 200
```

> 👁️ 요청 직후 로그가 보이지 않으면 약 30초 기다린 뒤 `curl`을 다시 실행하세요. 로그 버퍼링으로 애플리케이션 로그와 HTTP 로그의 출력 순서가 실제 요청 순서와 다를 수 있습니다.

로그 확인을 마치면 로그 스트림을 실행한 탭에서 **Ctrl+C**를 눌러 종료합니다. Azure Portal에서는 **App Service → Monitoring → Log stream**에서도 동일한 로그를 확인할 수 있습니다.

---

## 검증

🟢 **실행**

```bash
curl -s $APP_URL/api/info | jq
```

📋 **예상 출력**

```json
{
  "color": "#2563eb",
  "instance": "<instance-id>",
  "message": "App Service 워크숍에 오신 것을 환영합니다",
  "python": "3.12.x",
  "slot": "production",
  "started_at": "<UTC 시작 시각>",
  "version": "v1"
}
```

`version`이 `v1`, `slot`이 `production`으로 확인되면 배포가 완료된 것입니다. `instance` 값은 이후 **슬롯 스왑**, **스케일아웃**, **트래픽 분산** 모듈에서 핵심 관찰 도구로 활용됩니다.

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

이전 모듈: [02. 환경 준비](02-environment-setup.md) · 다음 모듈: [04. 앱 설정](04-app-settings.md)
