# 08. 관찰 가능성(진단 설정 → KQL · App Insights 연결)

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

---

## 목표

이 모듈에서는 Azure App Service의 **진단 설정**을 구성하여 플랫폼 로그를 Log Analytics 워크스페이스(LAW)로 전송하고, KQL 쿼리로 HTTP 액세스 패턴을 분석합니다. 이어서 **App Insights 커넥션 스트링**을 앱 설정으로 주입하여 Flask 앱에 내장된 OpenTelemetry SDK 기반 텔레메트리를 활성화합니다.

- App Service 진단 설정을 구성하여 HTTP 로그·콘솔 로그·플랫폼 로그를 LAW로 전송합니다.
- 인위적인 HTTP 트래픽을 발생시키고 KQL로 액세스 패턴을 분석합니다.
- `APPLICATIONINSIGHTS_CONNECTION_STRING` 앱 설정을 주입하여 Flask 앱의 OpenTelemetry SDK를 활성화합니다.
- `requests` 테이블 KQL로 애플리케이션 텔레메트리를 확인합니다.
- 진단 설정(플랫폼 로그)과 App Insights(앱 텔레메트리)의 역할 차이를 이해합니다.
- 모듈 종료 상태: **진단 설정 활성, APPLICATIONINSIGHTS_CONNECTION_STRING 주입 완료**.

## 소요 시간

약 20–30분

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

## 👁️ 진단 설정 vs App Insights — 역할 구분

Azure에서 웹앱 가시성을 확보하는 경로는 두 가지입니다.

| 비교 항목 | **진단 설정(플랫폼 로그)** | **App Insights(앱 텔레메트리)** |
|---|---|---|
| 수집 주체 | **Azure 플랫폼** | **앱 내 SDK(OpenTelemetry)** |
| 주요 데이터 | HTTP 액세스·콘솔·플랫폼 이벤트 | 요청·의존성·예외·트레이스·커스텀 메트릭 |
| 저장 위치 | Log Analytics 워크스페이스 | Application Insights 리소스 |
| 활성화 방법 | 진단 설정 구성 | 앱 설정 `APPLICATIONINSIGHTS_CONNECTION_STRING` 주입 |
| Linux Python 제약 | 없음 | **codeless 자동 계측 미지원 → SDK 내장 필수** |

> 👁️ 이 워크숍의 Flask 앱에는 `azure-monitor-opentelemetry` SDK가 이미 내장되어 있습니다. 커넥션 스트링을 환경 변수로 전달하면 텔레메트리가 즉시 활성화됩니다. 외부 의존성이 없으므로 **Application map은 단일 노드가 정상**입니다.

---

## 1단계 — 진단 설정 구성

🟢 **실행** — 웹앱 및 LAW 리소스 ID를 조회한 뒤 진단 설정을 생성합니다.

```bash
WEBAPP_ID=$(az webapp show -g $RG -n $APP --query id -o tsv)
LAW_ID=$(az monitor log-analytics workspace show -g $RG -n $LAW --query id -o tsv)
az monitor diagnostic-settings create --name appsvc-diag --resource $WEBAPP_ID \
  --workspace $LAW_ID \
  --logs '[{"category":"AppServiceHTTPLogs","enabled":true},{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServicePlatformLogs","enabled":true}]' \
  --metrics '[{"category":"AllMetrics","enabled":true}]'
```

> 👁️ `AppServiceHTTPLogs`는 HTTP 액세스 로그, `AppServiceConsoleLogs`는 앱 표준 출력, `AppServicePlatformLogs`는 배포·스케일 이벤트를 수집합니다. **설정을 켰다 ≠ 데이터가 흐른다** — 진단 설정 활성화 후 첫 요청이 도달해야 로그가 생성되며, LAW 적재까지 5–10분의 지연이 있습니다.

---

## 2단계 — 트래픽 생성 및 적재 대기

🟢 **실행** — 30회 요청을 전송하여 HTTP 로그를 생성합니다.

```bash
# 트래픽 생성 후 적재 대기(5–10분 — "설정을 켰다 ≠ 데이터가 흐른다")
for i in $(seq 1 30); do curl -s $APP_URL/api/info > /dev/null; done
```

> 👁️ 명령 실행 직후 KQL 결과가 0건이더라도 정상입니다. LAW 적재 지연이 원인이므로 **5분 이상 대기** 후 다음 단계를 진행하십시오.

---

## 3단계 — KQL로 HTTP 로그 조회

🟢 **실행** — LAW 워크스페이스 ID를 조회하고 KQL 쿼리를 실행합니다.

```bash
LAW_CID=$(az monitor log-analytics workspace show -g $RG -n $LAW --query customerId -o tsv)
az monitor log-analytics query -w $LAW_CID --analytics-query \
  'AppServiceHTTPLogs | where TimeGenerated > ago(30m)
   | summarize hits=count() by CsUriStem, ScStatus | order by hits desc' -o table
```

📋 **예상 출력** (예시 — 실제 값은 다를 수 있음)

```
CsUriStem      ScStatus    hits
-------------  ----------  ----
/api/info      200         30
/              200          5
```

> 👁️ `CsUriStem`은 요청 경로, `ScStatus`는 HTTP 상태 코드입니다. `az monitor log-analytics query` 명령은 `log-analytics` 확장이 필요합니다. 확장이 없으면 아래 트러블슈팅 §(3)을 참조하십시오.

🖼️ **포털에서 동일 쿼리 실행** — Azure Portal → Log Analytics 워크스페이스(`log-appsvcworkshop-$SUFFIX`) → **Logs** 블레이드에 아래 쿼리를 붙여 넣고 **Run**을 클릭합니다. 결과가 0건이면 **Time range**를 60분 또는 24시간으로 늘려 재시도하십시오.

```
AppServiceHTTPLogs
| where TimeGenerated > ago(30m)
| summarize hits=count() by CsUriStem, ScStatus
| order by hits desc
```

---

## 4단계 — App Insights 커넥션 스트링 주입

🟢 **실행** — `application-insights` 확장을 설치하고 커넥션 스트링을 앱 설정으로 주입합니다.

```bash
az extension add --name application-insights --upgrade --only-show-errors
AI_CONN=$(az monitor app-insights component show -g $RG --app $APPI --query connectionString -o tsv)
az webapp config appsettings set -g $RG -n $APP \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN"
```

> 👁️ 앱 설정 변경은 앱을 자동 재시작합니다. 재시작이 완료된 뒤 트래픽을 추가로 발생시켜야 SDK가 텔레메트리를 전송합니다.

🟢 **실행** — 재시작 후 트래픽을 추가 생성합니다.

```bash
for i in $(seq 1 20); do curl -s $APP_URL/api/info > /dev/null; done
```

🟢 **실행** — 수 분 뒤 App Insights `requests` 테이블을 조회합니다.

```bash
az monitor app-insights query -g $RG --apps $APPI --analytics-query \
  'requests | where timestamp > ago(15m) | summarize count() by name' -o table
```

📋 **예상 출력** (예시)

```
name                count_
------------------  -------
GET /api/info       20
```

🖼️ **Live Metrics** — Azure Portal → Application Insights(`appi-appsvcworkshop-$SUFFIX`) → **Live Metrics** 블레이드에서 실시간 요청률·응답 시간·실패율을 확인합니다. 트래픽을 전송하는 동안 차트가 실시간으로 갱신됩니다.

---

## 검증

| 확인 항목 | 기대 결과 |
|---|---|
| `az monitor diagnostic-settings create` 완료 | 명령 오류 없이 JSON 출력 |
| 트래픽 생성 후 5–10분 대기 KQL 조회 | `AppServiceHTTPLogs` 테이블에 1건 이상의 행 |
| `az monitor app-insights component show` | `connectionString` 값 정상 출력 |
| `az webapp config appsettings set` 완료 | `APPLICATIONINSIGHTS_CONNECTION_STRING` 포함 설정 목록 반환 |
| `requests` KQL 조회(트래픽 발생 후 수 분 대기) | `name` 열에 `/api/info` 항목 1건 이상 |

---

## 트러블슈팅

### (1) KQL 결과가 0건

진단 설정 활성화 후 LAW로 데이터가 적재되기까지 **5–10분**이 소요됩니다. `ago(30m)` 범위를 `ago(1h)` 또는 `ago(24h)`로 늘려 재시도하십시오.

```bash
az monitor log-analytics query -w $LAW_CID --analytics-query \
  'AppServiceHTTPLogs | where TimeGenerated > ago(1h) | take 10' -o table
```

### (2) `requests` 테이블이 0건

다음 순서로 확인합니다.

1. `az webapp config appsettings list -g $RG -n $APP -o table | grep APPLICATIONINSIGHTS` 로 설정이 주입되었는지 확인합니다.
2. `az webapp restart -g $RG -n $APP` 으로 앱을 재시작합니다.
3. 트래픽을 추가로 발생시킨 뒤 최소 2–3분 대기 후 재조회합니다.

### (3) `az monitor log-analytics query` 명령 없음

`log-analytics` 확장이 설치되지 않은 경우입니다.

```bash
az extension add --name log-analytics --upgrade --only-show-errors
```

설치 후 3단계 명령을 재실행합니다.

### (4) `az monitor app-insights query` 명령 없음

4단계 첫 번째 명령(`az extension add --name application-insights`)이 실행되지 않은 경우입니다. 아래 명령으로 재설치합니다.

```bash
az extension add --name application-insights --upgrade --only-show-errors
```

---

이전 모듈: [07. 자동 스케일](07-autoscale.md) | 다음 모듈: [09. Easy Auth](09-easy-auth.md)
