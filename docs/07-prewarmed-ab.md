# 07 심화. Prewarmed A/B 실험

> 🔬 **선택 심화 모듈** — 기본 [07. 자동 스케일](07-autoscale.md)을 완료한 뒤 수행하는 것을 권장합니다. 이 모듈을 건너뛰어도 08 모듈을 진행할 수 있습니다.

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요)

---

## 목표

이 선택 심화 모듈에서는 기본 07에서 활성화한 Azure App Service **Automatic Scaling**과 `hey`, 두 Python observer를 사용하여 새 instance가 **언제 시작되고 언제 실제 응답에 처음 투입되는지**를 관찰합니다. 단일 실행의 승패를 가르기보다 `Prewarmed=0`과 `Prewarmed=1`에서 보이는 외부 증거를 기록하고 해석합니다.

- 기본 07의 Automatic Scaling 상태(Maximum burst 5, Always ready 1, Prewarmed 1)를 확인합니다.
- `STARTUP_DELAY_SECONDS=20`으로 새 프로세스의 시작 준비 시간을 눈에 보이게 만듭니다.
- `/api/info`의 `started_at`과 새 instance의 최초 관찰 시각으로 `first_response_age`를 계산합니다.
- `Prewarmed=0`과 `Prewarmed=1`의 인스턴스별 시작·투입 타임라인을 비교하되, 한 번의 실행에서 어느 쪽이 반드시 더 빠르다고 판정하지 않습니다.
- `InstanceCount` 메트릭으로 시험 전·시험 사이의 단일 인스턴스 기준 상태를 확인합니다.
- 종료 전에 Prewarmed 1과 시작 지연 없음으로 복원하고 전체 Automatic Scaling 상태를 확인합니다.
- 모듈 종료 상태: **Automatic scaling 활성(Always ready 1·Prewarmed 1·Maximum burst 5), prod = v2** (이후 모듈에서 이 상태가 유지됩니다).

## 공통 상태 — 항상 실행

> 🟢 이 줄은 같은 터미널로 이어서 진행하든, 새 Cloud Shell에서 다시 시작하든 먼저 실행합니다.
> `REPO_DIR`는 `scripts/observe_instances.py`의 경로를 고정하기 위해 여기서 항상 정의합니다.

```bash
# 관찰 스크립트를 현재 리포지토리의 절대 경로로 실행할 수 있도록 기준 경로를 저장합니다.
REPO_DIR="$HOME/ms-appservice-basic-workshop01"
```

---

## 0단계 — (선택) 변수 재설정

> ⏭️ **06 모듈에서 이어서 같은 터미널로 진행 중이라면 이 단계는 건너뛰세요.**
> 새 터미널 세션을 열었거나 Cloud Shell이 재시작되어 변수가 사라진 경우에만 실행합니다.
> `SUFFIX` 는 **02 모듈에서 사용한 값과 동일하게** 입력하세요.
> 이후 헬퍼는 기본 클론 경로 `~/ms-appservice-basic-workshop01`를 기준으로 동작합니다. 새 Cloud Shell은 현재 디렉터리를 보장하지 않으므로, 스크립트 경로를 고정해 둡니다.

🟢 **실행**

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App 및 Plan 리소스 ID를 조회합니다.
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

## 선행 조건 확인

> 👁️ Automatic Scaling의 개념과 설정 방법은 [07. 자동 스케일](07-autoscale.md)을 참고하세요. 이 심화 실험은 기본 07의 종료 상태인 **Automatic Scaling 활성, Maximum burst 5, Always ready 1, Prewarmed 1**에서 시작합니다.

🟢 **실행**

```bash
# 리소스 ID와 hey 경로를 복원하고 기본 07의 종료 상태를 확인합니다.
export PATH=$HOME/go/bin:$PATH
PLAN_ID=$(az appservice plan show -g "$RG" -n "$PLAN" --query id -o tsv)
APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)

if ! command -v hey >/dev/null 2>&1; then
  echo "hey가 없습니다. 기본 07의 2단계를 먼저 수행하세요." >&2
  false
fi

az rest --method get \
  --uri "${PLAN_ID}?api-version=2024-11-01" \
  --query "properties.{automaticScaling:elasticScaleEnabled,maximumBurst:maximumElasticWorkerCount}"

az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "automaticScaling": true,
  "maximumBurst": 5
}
{
  "alwaysReady": 1,
  "prewarmed": 1
}
```

> ⚠️ 값이 다르면 심화 실험을 시작하지 말고 기본 07의 1단계를 다시 수행하세요.

---

## 1단계 — Prewarmed A/B 비교 준비

이번 모듈의 관찰 포인트는 “어느 시험이 더 빨랐는가”가 아니라 **새 instance가 시작된 뒤 실제 응답에 처음 보일 때까지 어떤 타임라인이 관찰되는가**입니다. 먼저 `STARTUP_DELAY_SECONDS=20`으로 새 프로세스의 시작 준비 시간을 키우고, 동일한 burst 부하에서 `Prewarmed=0`과 `Prewarmed=1`의 관찰 결과를 같은 형식으로 기록합니다.

`started_at`은 20초 시작 지연 전에 기록됩니다. 따라서 `first_response_age`가 약 20초라면 시작 준비 직후 응답에 투입된 것이고, 그보다 길면 준비를 마친 뒤 실제 응답 전에 대기한 구간이 있었음을 뜻합니다. `first_seen_at`은 클라이언트 observer가 그 instance의 응답을 처음 받은 시각이지, 플랫폼 내부 라우팅이 실제로 시작된 정확한 시각은 아닙니다. 이 값은 플랫폼 내부의 active/prewarmed 라벨을 직접 조회한 것이 아니라 앱이 관찰한 외부 증거입니다.

🟢 **실행 — 시작 지연 설정과 결과 경로 준비**

> 👁️ 두 시험의 결과를 저장할 디렉터리와 JSON 파일 경로를 먼저 준비하고, 새 프로세스의 시작 지연을 관찰할 수 있도록 `STARTUP_DELAY_SECONDS=20`을 앱 설정에 추가합니다.

```bash
# A/B 결과 파일 경로를 준비하고 앱 시작 지연을 적용합니다.
AB_DIR="${AB_DIR:-$HOME/appservice-prewarmed-ab}"
mkdir -p "$AB_DIR"
NO_PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-0-observations.json"
PREWARM_OBSERVATIONS="$AB_DIR/prewarmed-1-observations.json"
NO_PREWARM_METRICS="$AB_DIR/prewarmed-0-instance-count.json"
PREWARM_METRICS="$AB_DIR/prewarmed-1-instance-count.json"

az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings STARTUP_DELAY_SECONDS=20 --output none &&
echo "STARTUP_DELAY_SECONDS=20 설정 완료"
```

> ⚠️ 오류가 출력되거나 완료 메시지가 보이지 않으면 다음 단계로 진행하지 마세요. 설정을 변경한 뒤 중단해야 한다면 4단계의 **모듈 기본 상태로 복원** 명령을 실행합니다.

🟢 **실행 — 앱 준비 상태 확인**

> 👁️ 앱 설정 변경으로 프로세스가 재시작될 수 있으므로 `/health`를 최대 18회 확인합니다. 응답 JSON의 `status`가 `ok`일 때만 다음 명령으로 진행합니다.

```bash
# 앱 재시작 후 /health가 정상화될 때까지 기다립니다.
HEALTH_CHECK_STATUS=1
for attempt in $(seq 1 18); do
  HEALTH_BODY=$(curl -fsS --max-time 10 "$APP_URL/health" 2>/dev/null || true)
  if jq -e '.status == "ok"' >/dev/null 2>&1 <<< "$HEALTH_BODY"; then
    printf '%s\n' "$HEALTH_BODY"
    HEALTH_CHECK_STATUS=0
    break
  fi
  if [ "$attempt" -lt 18 ]; then
    sleep 5
  fi
done
if [ "$HEALTH_CHECK_STATUS" -ne 0 ]; then
  echo "/health 확인 실패: 4단계의 복원 명령을 실행하세요." >&2
  false
fi
```

📋 **예상 출력**

```json
{"status":"ok"}
```

> 👁️ `InstanceCount`는 시험 시작 전·시험 사이의 단일 인스턴스 기준 상태 확인과 각 시험 중의 capacity 변화 관찰에 사용합니다. 시험 중에는 30초마다 조회해 1분 단위 값을 별도 JSON으로 저장하고, `observe_instances.py`는 실제 응답에 나타난 새 instance의 `started_at`, `first_seen_at`, `first_response_age`를 기록합니다.


## 2단계 — 시험 A: Prewarmed=0

먼저 `Prewarmed=0`에서 새 instance가 언제 처음 응답에 투입되는지 관찰합니다.

🟢 **실행 — Prewarmed=0 설정**

> 👁️ 시험 A 조건을 만들기 위해 Always-ready는 1로 유지하고 Prewarmed만 0으로 변경합니다. PATCH 직후 같은 설정을 조회하여 `prewarmed=0`이 반영됐는지 확인합니다.

```bash
# 시험 A를 위해 Prewarmed 인스턴스를 0으로 설정합니다.
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":0}}' \
  --output none &&
az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "alwaysReady": 1,
  "prewarmed": 0
}
```

🟢 **실행 — 단일 인스턴스 기준 상태 확인**

> 👁️ 최근 10분의 `InstanceCount` Average 값을 1분 간격으로 조회합니다. 최신 행이 `count=1`이면 이전 확장이 정리된 단일 인스턴스 기준 상태입니다.

```bash
# 부하 시작 전 요청을 처리하는 기준 인스턴스 하나를 확인합니다.
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Average \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --query "value[0].timeseries[0].data[?average != null].{time:timeStamp,count:average}" \
  -o table
```

> 👁️ 최신 행의 `count`가 `1`인지 확인합니다. 아직 2 이상이면 30초 정도 기다린 뒤 같은 조회 명령을 다시 실행합니다.

🟢 **실행 — 시험 A 관찰**

> 👁️ **시험 A 명령 흐름**
>
> 1. `curl`과 `jq`로 `/api/info` 응답에서 현재 기준 instance ID를 가져옵니다. ID를 얻지 못하면 `if`의 `else`로 이동하므로 부하와 observer는 시작되지 않습니다.
> 2. `observe_scaling_metric.py`는 Web App에서 지원되는 `InstanceCount`를 30초마다 최대 240초 관찰합니다. 180초 부하가 끝난 뒤에도 Azure Monitor 수집 지연을 위해 최대 60초 더 기다리며, 화면과 `$NO_PREWARM_METRICS` JSON에 기록합니다.
> 3. `hey -z 180s -c 100 -q 10`은 180초 동안 최대 100개 동시 worker를 사용하고 worker당 초당 10개 요청으로 `/api/info`에 부하를 보냅니다. `&`로 백그라운드 실행하며 요약 결과는 `$AB_DIR/hey-burst-0.out`에 저장합니다.
> 4. `METRIC_PID=$!`와 `HEY_PID=$!`는 각 백그라운드 프로세스의 PID를 저장합니다. 뒤의 `wait`가 정확한 프로세스의 완료와 종료 상태를 확인할 때 사용합니다.
> 5. `observe_instances.py`는 기준 instance를 제외하고 180초 동안 `--concurrency 30`으로 응답을 관찰하며, 각 요청은 `--request-timeout 5`로 제한합니다. 발견한 새 instance의 타임라인은 `$NO_PREWARM_OBSERVATIONS` JSON에 저장합니다.
> 6. instance observer가 끝나면 `hey`와 metric observer를 차례로 기다리고 `OBSERVER_STATUS`, `HEY_STATUS`, `METRIC_STATUS`를 확인합니다. 세 exit code가 모두 0일 때만 시험 A를 성공으로 보고 시험 B로 진행합니다.

```bash
# 시험 A의 부하, 인스턴스 관찰, InstanceCount 메트릭 수집을 동시에 실행합니다.
if BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
  jq -er 'select((.instance | type) == "string" and (.instance | test("\\S"))) | .instance'); then
  echo "Prewarmed=0 기준 instance: $BASELINE_INSTANCE"

  python3 "$REPO_DIR/scripts/observe_scaling_metric.py" \
    --resource "$APP_ID" \
    --duration 240 \
    --poll-interval 30 \
    --output "$NO_PREWARM_METRICS" &
  METRIC_PID=$!

  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" \
    > "$AB_DIR/hey-burst-0.out" &
  HEY_PID=$!

  if python3 "$REPO_DIR/scripts/observe_instances.py" \
    --url "$APP_URL/api/info" \
    --baseline-instance "$BASELINE_INSTANCE" \
    --duration 180 \
    --concurrency 30 \
    --request-timeout 5 \
    --output "$NO_PREWARM_OBSERVATIONS"
  then
    OBSERVER_STATUS=0
  else
    OBSERVER_STATUS=$?
    kill "$HEY_PID" "$METRIC_PID" 2>/dev/null || true
  fi

  if wait "$HEY_PID"; then HEY_STATUS=0; else HEY_STATUS=$?; fi
  if wait "$METRIC_PID"; then METRIC_STATUS=0; else METRIC_STATUS=$?; fi

  echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS, metric exit=$METRIC_STATUS"
  if [ "$OBSERVER_STATUS" -ne 0 ] || [ "$HEY_STATUS" -ne 0 ] || [ "$METRIC_STATUS" -ne 0 ]; then
    echo "시험 A 실패: 세 결과를 비교하지 말고 4단계의 복원 명령을 실행하세요." >&2
    false
  fi
else
  echo "시험 A 기준 instance 확인 실패: 4단계의 모듈 기본 상태로 복원 명령을 실행한 뒤 1단계부터 다시 시도하세요." >&2
  false
fi
```

> ⚠️ `observer exit=0, hey exit=0, metric exit=0`일 때만 시험 B로 진행합니다. observer가 2로 종료되거나 metric observer가 1 또는 2로 종료되면 4단계의 **모듈 기본 상태로 복원** 명령을 실행한 뒤 1단계부터 다시 시도합니다.

📋 **예상 출력** (2026-07-23 리허설 예시)

```text
metric_timestamp	observed_at	instance_count
instance	started_at	first_seen_at	first_response_age
2026-07-23T03:20:00Z	2026-07-23T03:21:35Z	1
2026-07-23T03:21:00Z	2026-07-23T03:21:35Z	1
a2b002c6	2026-07-23T03:22:05Z	2026-07-23T03:22:33Z	28
2026-07-23T03:22:00Z	2026-07-23T03:22:38Z	1
5bef3ff3	2026-07-23T03:22:22Z	2026-07-23T03:23:03Z	41
bd29045b	2026-07-23T03:22:24Z	2026-07-23T03:23:04Z	40
3122a953	2026-07-23T03:22:16Z	2026-07-23T03:23:04Z	48
[2]+  Done                    hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$AB_DIR/hey-burst-0.out"
2026-07-23T03:24:00Z	2026-07-23T03:24:45Z	5
2026-07-23T03:25:00Z	2026-07-23T03:25:34Z	5
[1]+  Done                    python3 "$REPO_DIR/scripts/observe_scaling_metric.py" --resource "$APP_ID" --duration 240 --poll-interval 30 --output "$NO_PREWARM_METRICS"
observer exit=0, hey exit=0, metric exit=0
```

> 👁️ 세 exit code가 모두 0이므로 유효한 시험 A 결과입니다. 기준 instance를 제외한 새 instance 4개가 기록됐고, `InstanceCount`는 이후 5까지 증가했습니다. metric과 instance 행의 출력 순서는 실행마다 달라질 수 있습니다. `PT1M` Average와 수집 지연 때문에 중간 metric timestamp가 생략되거나, 새 instance의 `first_seen_at`보다 count 증가가 늦게 출력돼도 오류가 아닙니다. `[1]`, `[2]` 작업 번호도 셸 실행마다 달라질 수 있습니다.

---

## 3단계 — scale-in 게이트 후 시험 B: Prewarmed=1

시험 B는 반드시 시험 A의 부하가 끝나고 새 기준 상태가 다시 확보된 뒤 시작합니다. `Prewarmed=1`로 되돌린 뒤에도 별도의 prime 부하나 `InstanceCount>=2` 버퍼 게이트는 두지 않고, 같은 burst에서 새 instance의 최초 응답 나이를 다시 관찰합니다.

🟢 **실행 — 시험 B 시작 전 단일 인스턴스 기준 상태 확인**

> 👁️ 시험 A 부하로 늘어난 인스턴스가 scale-in됐는지 다시 확인합니다. 최신 메트릭이 `count=1`이 된 뒤에만 시험 B를 시작합니다.

```bash
# 시험 B 전에 scale-in되어 기준 인스턴스 하나로 돌아왔는지 확인합니다.
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Average \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --query "value[0].timeseries[0].data[?average != null].{time:timeStamp,count:average}" \
  -o table
```

> 👁️ 최신 행의 `count`가 `1`이 될 때까지 30초 정도 간격으로 같은 명령을 다시 실행합니다. 별도의 prime 부하나 `InstanceCount>=2` 확인은 하지 않습니다.

🟢 **실행 — Prewarmed=1 설정**

> 👁️ 시험 B 조건을 만들기 위해 Prewarmed를 1로 되돌리고 즉시 조회합니다. 출력에서 Always-ready와 Prewarmed가 모두 1인지 확인합니다.

```bash
# 시험 B를 위해 Prewarmed 인스턴스를 1로 설정합니다.
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none &&
az rest --method get \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}"
```

📋 **예상 출력**

```json
{
  "alwaysReady": 1,
  "prewarmed": 1
}
```

🟢 **실행 — 시험 B 관찰**

> 👁️ **시험 B 명령 흐름**
>
> 1. 시험 A와 같은 순서로 `curl`과 `jq`를 사용해 현재 기준 instance ID를 확보합니다. 차이는 앞 단계에서 Prewarmed=1로 설정했다는 점이며, ID 확보 실패 시 부하를 시작하지 않습니다.
> 2. `observe_scaling_metric.py`는 시험 A와 동일하게 `InstanceCount`를 30초마다 최대 240초 관찰하고 `$PREWARM_METRICS` JSON에 저장합니다.
> 3. `hey -z 180s -c 100 -q 10`으로 시험 A와 동일한 180초 부하를 백그라운드 실행합니다. 부하 조건은 동일하게 유지하고 출력 파일만 `$AB_DIR/hey-burst-1.out`을 사용합니다.
> 4. `METRIC_PID=$!`와 `HEY_PID=$!`에 Trial B의 백그라운드 프로세스 PID를 저장하여 뒤의 `wait`가 각 완료와 종료 상태를 정확히 확인하도록 합니다.
> 5. `observe_instances.py`는 기준 instance를 제외하고 `--concurrency 30`, `--request-timeout 5` 조건으로 새 instance를 관찰합니다. 결과는 Trial B 전용 `$PREWARM_OBSERVATIONS` JSON에 저장합니다.
> 6. observer, `hey`, metric observer의 세 exit code가 모두 0인지 확인합니다. 하나라도 0이 아니면 세 결과를 비교하지 않고 4단계 복원 명령을 실행합니다.

```bash
# 시험 B에 시험 A와 동일한 부하와 관찰 조건을 적용합니다.
if BASELINE_INSTANCE=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
  jq -er 'select((.instance | type) == "string" and (.instance | test("\\S"))) | .instance'); then
  echo "Prewarmed=1 기준 instance: $BASELINE_INSTANCE"

  python3 "$REPO_DIR/scripts/observe_scaling_metric.py" \
    --resource "$APP_ID" \
    --duration 240 \
    --poll-interval 30 \
    --output "$PREWARM_METRICS" &
  METRIC_PID=$!

  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" \
    > "$AB_DIR/hey-burst-1.out" &
  HEY_PID=$!

  if python3 "$REPO_DIR/scripts/observe_instances.py" \
    --url "$APP_URL/api/info" \
    --baseline-instance "$BASELINE_INSTANCE" \
    --duration 180 \
    --concurrency 30 \
    --request-timeout 5 \
    --output "$PREWARM_OBSERVATIONS"
  then
    OBSERVER_STATUS=0
  else
    OBSERVER_STATUS=$?
    kill "$HEY_PID" "$METRIC_PID" 2>/dev/null || true
  fi

  if wait "$HEY_PID"; then HEY_STATUS=0; else HEY_STATUS=$?; fi
  if wait "$METRIC_PID"; then METRIC_STATUS=0; else METRIC_STATUS=$?; fi

  echo "observer exit=$OBSERVER_STATUS, hey exit=$HEY_STATUS, metric exit=$METRIC_STATUS"
  if [ "$OBSERVER_STATUS" -ne 0 ] || [ "$HEY_STATUS" -ne 0 ] || [ "$METRIC_STATUS" -ne 0 ]; then
    echo "시험 B 실패: 세 결과를 비교하지 말고 4단계의 복원 명령을 실행하세요." >&2
    false
  fi
else
  echo "시험 B 기준 instance 확인 실패: 4단계의 복원 명령을 실행한 뒤 결과를 해석하지 말고 1단계부터 다시 시도하세요." >&2
  false
fi
```

> ⚠️ `observer exit=0, hey exit=0, metric exit=0`일 때만 결과를 해석합니다.

📋 **예상 출력** (2026-07-23 리허설 예시)

```text
metric_timestamp	observed_at	instance_count
instance	started_at	first_seen_at	first_response_age
2026-07-23T03:28:00Z	2026-07-23T03:29:25Z	1
2026-07-23T03:29:00Z	2026-07-23T03:29:25Z	1
69e069d8	2026-07-23T03:29:35Z	2026-07-23T03:30:00Z	25
9b19c4d6	2026-07-23T03:29:36Z	2026-07-23T03:30:01Z	25
8e0e812d	2026-07-23T03:30:13Z	2026-07-23T03:30:52Z	39
5d90b391	2026-07-23T03:30:21Z	2026-07-23T03:30:52Z	31
2026-07-23T03:31:00Z	2026-07-23T03:31:32Z	3
2026-07-23T03:32:00Z	2026-07-23T03:32:35Z	5
2026-07-23T03:33:00Z	2026-07-23T03:33:23Z	5
observer exit=0, hey exit=0, metric exit=0
```

> 👁️ 세 exit code가 모두 0이므로 유효한 시험 B 결과입니다. 기준 instance를 제외한 새 instance 4개가 기록됐고, `InstanceCount`는 1에서 3을 거쳐 5까지 증가했습니다. `instance_count=3`은 1분 구간의 Average이므로 같은 시점에 정확히 3개만 존재했다는 의미가 아니며, 다음 구간의 5와 모순되지 않습니다. metric과 instance 행의 출력 순서는 실행마다 달라질 수 있습니다. 셸이 출력하는 `[1]`, `[2]` job-control 줄은 환경마다 달라 예상 출력에서 생략했습니다.
>
> 👁️ 두 시험 모두 같은 앱·같은 엔드포인트·같은 burst 부하를 쓰므로, 비교 대상은 `Prewarmed` 설정 차이와 그에 따라 관찰된 instance 타임라인입니다.

---

## 4단계 — 기본 상태 복원 및 결과 해석

두 시험 모두에서 새 instance가 관찰되었다면, 이제 총 scale-out 시간의 승패 대신 **instance별 시작·최초 응답 타임라인**을 나란히 봅니다.

🟢 **실행 — 모듈 기본 상태로 복원**

> ⚠️ 결과 해석보다 먼저 복원합니다. 이후 명령이 실패하더라도 다음 모듈이 동일한 상태에서 시작할 수 있도록 Prewarmed를 1로 되돌리고 인위적인 시작 지연을 삭제합니다.

```bash
# 리소스 ID를 다시 조회하여 새 Cloud Shell에서도 복원할 수 있게 합니다.
RESTORE_STATUS=0
if APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv); then
  if ! az rest --method patch \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
    --output none
  then
    echo "Prewarmed 복원 실패" >&2
    RESTORE_STATUS=1
  fi
else
  echo "Web App 리소스 ID 조회 실패" >&2
  RESTORE_STATUS=1
fi

# Prewarmed PATCH 결과와 관계없이 인위적인 시작 지연 삭제를 시도합니다.
if ! az webapp config appsettings delete -g "$RG" -n "$APP" \
  --setting-names STARTUP_DELAY_SECONDS --output none
then
  echo "STARTUP_DELAY_SECONDS 삭제 실패" >&2
  RESTORE_STATUS=1
fi

if [ "$RESTORE_STATUS" -ne 0 ]; then
  echo "복원 실패: 트러블슈팅의 복구 명령을 실행하세요." >&2
  false
fi

echo "Prewarmed=1, STARTUP_DELAY_SECONDS 삭제 완료"
```

🟢 **실행 — 복원 상태 확인**

```bash
# Automatic Scaling 전체 설정과 시작 지연 삭제를 단언합니다.
VERIFY_STATUS=0
if ! PLAN_ID=$(az appservice plan show -g "$RG" -n "$PLAN" --query id -o tsv); then
  echo "Plan 리소스 ID 조회 실패" >&2
  VERIFY_STATUS=1
fi
if ! APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv); then
  echo "Web App 리소스 ID 조회 실패" >&2
  VERIFY_STATUS=1
fi

if [ "$VERIFY_STATUS" -eq 0 ]; then
  if ! PLAN_STATE=$(az rest --method get \
    --uri "${PLAN_ID}?api-version=2024-11-01" -o json)
  then
    echo "Plan 상태 조회 실패" >&2
    VERIFY_STATUS=1
  fi
  if ! APP_STATE=$(az rest --method get \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" -o json)
  then
    echo "Web App 상태 조회 실패" >&2
    VERIFY_STATUS=1
  fi
fi

if ! STARTUP_DELAY_COUNT=$(az webapp config appsettings list -g "$RG" -n "$APP" \
  --query "length([?name=='STARTUP_DELAY_SECONDS'])" -o tsv)
then
  echo "앱 설정 조회 실패" >&2
  VERIFY_STATUS=1
fi

if [ "$VERIFY_STATUS" -eq 0 ]; then
  jq '{automaticScaling:.properties.elasticScaleEnabled,maximumBurst:.properties.maximumElasticWorkerCount}' <<< "$PLAN_STATE"
  jq '{alwaysReady:.properties.minimumElasticInstanceCount,prewarmed:.properties.preWarmedInstanceCount}' <<< "$APP_STATE"
  echo "STARTUP_DELAY_SECONDS count=$STARTUP_DELAY_COUNT"

  if ! jq -e '.properties.elasticScaleEnabled == true and .properties.maximumElasticWorkerCount == 5' \
    >/dev/null <<< "$PLAN_STATE" ||
    ! jq -e '.properties.minimumElasticInstanceCount == 1 and .properties.preWarmedInstanceCount == 1' \
      >/dev/null <<< "$APP_STATE" ||
    [ "$STARTUP_DELAY_COUNT" != "0" ]
  then
    VERIFY_STATUS=1
  fi
fi

if [ "$VERIFY_STATUS" -ne 0 ]; then
  echo "복원 상태 불일치: 트러블슈팅의 복구 명령을 실행하세요." >&2
  false
fi

for attempt in $(seq 1 18); do
  if curl -fsS --max-time 10 "$APP_URL/health" | jq -e '.status == "ok"'; then
    break
  fi
  if [ "$attempt" -eq 18 ]; then
    echo "복원 후 /health 확인 실패" >&2
    false
  fi
  sleep 5
done
```

📋 **예상 출력**

```text
Prewarmed=1, STARTUP_DELAY_SECONDS 삭제 완료
{
  "automaticScaling": true,
  "maximumBurst": 5
}
{
  "alwaysReady": 1,
  "prewarmed": 1
}
STARTUP_DELAY_SECONDS count=0
{"status":"ok"}
```

🟢 **실행 — InstanceCount 타임라인 출력**

> 👁️ `trial_started_at`은 metric observer를 시작한 시험 orchestration 시각입니다. 각 `metric_timestamp`는 Azure Monitor의 1분 집계 구간이고, `instance_count`는 그 구간의 Average 값이며, `observed_at`은 해당 값을 CLI에서 처음 확인한 시각입니다. 이 시각들을 다음 instance 표의 `first_seen_at`과 나란히 비교합니다.

```bash
# 두 시험의 InstanceCount 타임라인을 같은 형식으로 출력합니다.
printf 'trial\ttrial_started_at\tmetric_timestamp\tobserved_at\tinstance_count\n'
jq -r --arg trial "Prewarmed=0" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$NO_PREWARM_METRICS"
jq -r --arg trial "Prewarmed=1" '
  .trial_started_at as $started |
  .samples[] |
  [$trial, $started, .metric_timestamp, .observed_at, (.instance_count | tostring)] |
  @tsv
' "$PREWARM_METRICS"
```

📋 **예상 출력 형식** (시각과 count는 실행마다 달라지는 예시)

```text
trial	trial_started_at	metric_timestamp	observed_at	instance_count
Prewarmed=0	2026-07-22T01:02:03Z	2026-07-22T01:02:00Z	2026-07-22T01:02:34Z	1
Prewarmed=0	2026-07-22T01:02:03Z	2026-07-22T01:03:00Z	2026-07-22T01:03:35Z	4
Prewarmed=1	2026-07-22T01:12:10Z	2026-07-22T01:12:00Z	2026-07-22T01:12:40Z	2
Prewarmed=1	2026-07-22T01:12:10Z	2026-07-22T01:13:00Z	2026-07-22T01:13:41Z	3
```

🟢 **실행 — 결과 표 출력**

> 👁️ 두 JSON 파일을 읽어 Trial A와 B의 instance별 시작·최초 응답 시각을 하나의 TSV 표로 출력합니다. 이 표는 관찰 타임라인을 비교하기 위한 것이며 단일 실행의 속도 승자를 계산하지 않습니다.

```bash
# 두 시험에서 관찰된 인스턴스별 시작·최초 응답 시각을 출력합니다.
jq -r '
  ["trial","instance","started_at","first_seen_at","first_response_age"],
  (.[] | ["Prewarmed=0", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)])
  | @tsv
' "$NO_PREWARM_OBSERVATIONS"

jq -r '
  .[] | ["Prewarmed=1", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv
' "$PREWARM_OBSERVATIONS"

echo "[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다."
```

📋 **예상 출력** (2026-07-23 리허설 예시)

```text
trial	instance	started_at	first_seen_at	first_response_age
Prewarmed=0	a2b002c6	2026-07-23T03:22:05Z	2026-07-23T03:22:33Z	28
Prewarmed=0	5bef3ff3	2026-07-23T03:22:22Z	2026-07-23T03:23:03Z	41
Prewarmed=0	bd29045b	2026-07-23T03:22:24Z	2026-07-23T03:23:04Z	40
Prewarmed=0	3122a953	2026-07-23T03:22:16Z	2026-07-23T03:23:04Z	48
Prewarmed=1	69e069d8	2026-07-23T03:29:35Z	2026-07-23T03:30:00Z	25
Prewarmed=1	9b19c4d6	2026-07-23T03:29:36Z	2026-07-23T03:30:01Z	25
Prewarmed=1	8e0e812d	2026-07-23T03:30:13Z	2026-07-23T03:30:52Z	39
Prewarmed=1	5d90b391	2026-07-23T03:30:21Z	2026-07-23T03:30:52Z	31
[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다.
```

🟢 **실행 — 관찰 범위 요약**

> 👁️ 두 JSON의 `first_response_age`를 시험별로 정렬하여 표본 수, 최솟값, 최댓값, 범위를 계산합니다. 최솟값은 준비 하한 근접성, 최댓값과 범위는 긴 지연 꼬리와 관찰값의 일관성을 보는 지표입니다.

```bash
# A/B 관찰 범위와 파일 유효성을 요약해 비교 가능한 결과인지 확인합니다.
jq -s -r '
  ["trial","samples","min_age","max_age","range"],
  (to_entries[] |
    .key as $trial_index |
    (.value | map(.first_response_age) | sort) as $ages |
    [
      (if $trial_index == 0 then "Prewarmed=0" else "Prewarmed=1" end),
      ($ages | length),
      $ages[0],
      $ages[-1],
      ($ages[-1] - $ages[0])
    ]
  ) | @tsv
' "$NO_PREWARM_OBSERVATIONS" "$PREWARM_OBSERVATIONS"
```

📋 **예상 출력** (2026-07-23 리허설 예시)

```text
trial	samples	min_age	max_age	range
Prewarmed=0	4	28	48	20
Prewarmed=1	4	25	39	14
```

### 무엇이 Prewarmed의 이점인가

Microsoft Learn의 [Automatic scaling in Azure App Service](https://learn.microsoft.com/azure/app-service/manage-automatic-scaling)는 Prewarmed instance를 HTTP scale·activation 시 사용하는 **warmed capacity buffer**로 설명합니다. 목적은 모든 확장 시간을 일정하게 보장하는 것이 아니라, 새 처리 용량이 필요할 때 처음부터 준비하는 cold-start 부담을 줄여 확장 전환을 더 부드럽게 만드는 것입니다.

### capacity 증가와 새 응답 instance를 함께 보는 법

1. `trial_started_at`으로 시험 orchestration이 시작된 구간을 확인합니다.
2. `InstanceCount`가 이전 값보다 증가한 첫 `metric_timestamp`를 찾습니다.
3. instance 표의 `first_seen_at`과 나란히 보며 capacity 증가 구간 뒤에 새 instance 응답이 언제 관찰됐는지 확인합니다.

Azure Portal의 표시 이름은 **Automatic Scaling Instance Count**이고 REST API 이름은 `InstanceCount`입니다. 이 메트릭은 앱이 실행되는 VM 수를 나타내며 배포된 Prewarmed instance를 포함할 수 있지만, 개별 instance의 active/Prewarmed 상태나 instance ID는 제공하지 않습니다. 또한 `PT1M` Average 집계와 Azure Monitor 수집 지연이 있으므로 `metric_timestamp`를 Azure 내부의 정확한 activation 시각으로 해석할 수 없습니다. 응답에서 관찰된 instance 수가 적다는 사실도 capacity 효율 향상을 의미하지 않습니다. 이 타임라인은 부하 중 전체 capacity 변화 흐름을 이해하기 위한 보조 증거이며 Prewarmed 효과의 인과관계 증명은 아닙니다.

### 이번 실측에서 보인 이점

`started_at`은 인위적인 `STARTUP_DELAY_SECONDS=20` 적용 전에 기록되므로 약 20초의 readiness floor가 있습니다.

- Trial A(Prewarmed=0)는 4개 instance가 28–48초에 처음 관찰됐고, 최댓값 48초·범위 20초였습니다.
- Trial B(Prewarmed=1)는 4개 instance가 25–39초에 처음 관찰됐고, 최댓값 39초·범위 14초였습니다.
- 이번 실행에서 B의 최솟값은 A보다 3초, 최댓값은 9초 낮았고 범위는 6초 좁았습니다. 같은 수의 표본에서 B의 관찰값이 전반적으로 더 낮고 덜 퍼진 **기술 통계**가 나타났습니다.

이 결과는 갑작스러운 HTTP 부하에서 Prewarmed가 새 처리 capacity의 준비 지연을 완화하는 warmed-buffer 메커니즘과 부합합니다. 다만 `InstanceCount`는 두 시험 모두 최종 5까지 증가했고 `PT1M` Average와 수집 지연이 있으므로, 이 메트릭만으로 B의 내부 scale-out 또는 allocation 자체가 더 빨랐다고 판단하지 않습니다.

---

## 트러블슈팅

### (1) 새 instance를 관찰하지 못함

`observe_instances.py`가 2로 종료되거나 JSON 배열이 비어 있으면, 이번 burst에서 새 instance를 끝내지 못한 것입니다. 한 번의 실행만으로 Automatic scaling 실패나 `Prewarmed` 무효를 단정하지 말고 다음을 점검합니다.

- 새 Cloud Shell에서 시작했다면 위 공통 상태에서 `REPO_DIR`가 `~/ms-appservice-basic-workshop01`로 고정되었는지 확인한 뒤, 0단계에서 `SUFFIX`와 Azure 리소스 변수만 다시 맞춥니다.
- `STARTUP_DELAY_SECONDS=20` 적용 후 `/health`가 정상 응답했는지 확인합니다.
- 4단계의 복원 명령을 실행한 뒤, 3단계의 단일 인스턴스 조회 명령으로 최신 행의 `count`가 `1`인지 다시 확인하고 1단계부터 재실행합니다.
- 같은 `hey -z 180s -c 100 -q 10` 부하를 다시 걸어도 결과가 같은지 확인합니다.
- Portal의 **Monitoring > Metrics > Automatic Scaling Instance Count** 또는 아래 메트릭 조회로 시험 시간대 `InstanceCount` 변화를 함께 확인합니다.

```bash
START=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
az monitor metrics list \
  --resource "$APP_ID" \
  --metric InstanceCount \
  --interval PT1M \
  --aggregation Average \
  --start-time "$START" \
  --query "value[0].timeseries[0].data[?average != null].{time:timeStamp,instances:average}" \
  -o table
```

### (2) 단일 인스턴스로 축소되지 않음

시험 A 뒤 3단계의 단일 인스턴스 조회에서 최신 행의 `count`가 계속 2 이상이면 시험 B를 실행하지 말고, 4단계의 복원 명령으로 **Prewarmed=1 + `STARTUP_DELAY_SECONDS` 삭제**를 먼저 적용한 뒤 멈추세요. Cloud Shell은 유지한 채 기다렸다가, 다시 시도할 때는 1단계부터 재실행하세요.

```bash
for attempt in $(seq 1 5); do
  az monitor metrics list \
    --resource "$APP_ID" \
    --metric InstanceCount \
    --interval PT1M \
    --aggregation Average \
    --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
    --query "value[0].timeseries[0].data[?average != null].{time:timeStamp,count:average}" \
    -o table
  sleep 60
done
```

Always-ready 값이 1보다 크면 그 아래로는 줄지 않으며, 같은 Plan의 다른 앱이 추가 인스턴스를 붙잡고 있어도 지표가 늦게 내려갈 수 있습니다. 공식 동작 기준으로 축소 판단은 보통 부하 종료 후 5–10분 이후부터 시작되므로, 충분히 기다린 뒤 다시 측정합니다.

### (3) 새 instance의 `first_response_age`가 두 시험에서 비슷함

이는 오류가 아닙니다. 이번 실행에서는 준비된 instance가 곧바로 활성화되어 응답 전 대기 구간이 짧았을 수 있습니다. 단일 실행의 총 scale-out 시간만으로 Prewarmed 효과를 단정하지 말고, 인스턴스별 `started_at`과 `first_seen_at`을 관찰 결과로 기록합니다.

### (4) 복원 명령이 실패함

4단계의 복원 블록이 실패하면 다음 모듈로 넘어가지 말고, 아래 복구 명령을 다시 실행합니다.

```bash
# 새 Cloud Shell에서도 복구할 수 있도록 변수와 리소스 ID를 다시 조회합니다.
SUFFIX=<이전에_메모한_값>
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
APP_URL="https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)

# 두 복구 명령은 서로 독립적으로 실행합니다.
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none

az webapp config appsettings delete -g "$RG" -n "$APP" \
  --setting-names STARTUP_DELAY_SECONDS --output none

# 복구 후 4단계의 "복원 상태 확인" 블록을 다시 실행합니다.
```

### (5) hey 설치 실패

`go install`은 GitHub에서 소스를 받아 빌드하므로 네트워크 일시 장애일 수 있습니다. 잠시 후 재시도하고, PATH에 `$HOME/go/bin`이 포함되어 있는지 확인합니다.

```bash
go install github.com/rakyll/hey@latest
export PATH=$HOME/go/bin:$PATH
command -v hey
```

### (6) Premium V2/V3 SKU만 지원한다는 오류

```text
--number-of-workers and --elastic-scale can only be used on premium V2/V3 or workflow SKUs.
['--minimum-elastic-instance-count', '--prewarmed-instance-count'] are only supported for elastic premium V2/V3 SKUs
```

P0v4가 지원되지 않는 것이 아니라 Azure CLI의 SKU 검증 로직이 Premium v4를 아직 포함하지 않아 발생하는 오류입니다. 기본 07의 1단계 `az rest` 명령을 사용하고, 기존 `az appservice plan update --elastic-scale` 및 `az webapp update --minimum-elastic-instance-count` 명령은 실행하지 않습니다.

---

이전 코어 모듈: [07. 자동 스케일](07-autoscale.md) · 다음 코어 모듈: [08. 관찰 가능성](08-observability.md)
