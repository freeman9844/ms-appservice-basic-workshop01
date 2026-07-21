#!/usr/bin/env bash
set -euo pipefail
export AZURE_CORE_ONLY_SHOW_ERRORS=true

SUFFIX="${SUFFIX:-$(printf "%05d" $(( (RANDOM * 32768 + RANDOM) % 100000 )))}"
LOC="${LOC:-koreacentral}"
RG="rg-appsvcworkshop-$SUFFIX"
PLAN="plan-appsvcworkshop-$SUFFIX"
APP="app-appsvcworkshop-$SUFFIX"
LAW="log-appsvcworkshop-$SUFFIX"
APPI="appi-appsvcworkshop-$SUFFIX"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$REPO_DIR/.rehearsal-tmp-$$"
mkdir -p "$TMP_DIR"
CLIENT_ID=""
APP_ID=""
HEY_PID=""
PREWARMED_RESTORE_NEEDED=0
CLEANUP_RUNNING=0

cleanup() {
  local exit_code=$?
  local cleanup_status=0
  if [ "$CLEANUP_RUNNING" = "1" ]; then
    return "$exit_code"
  fi
  CLEANUP_RUNNING=1
  if [ -n "$HEY_PID" ]; then
    if ! kill "$HEY_PID" 2>/dev/null && kill -0 "$HEY_PID" 2>/dev/null; then
      cleanup_status=1
    fi
    wait "$HEY_PID" 2>/dev/null || true
    HEY_PID=""
  fi
  if [ "$PREWARMED_RESTORE_NEEDED" = "1" ] && [ -n "$APP_ID" ]; then
    restore_prewarmed_demo || cleanup_status=1
  fi
  if ! rm -rf "$TMP_DIR"; then
    cleanup_status=1
  fi
  trap - EXIT
  if [ "$cleanup_status" -ne 0 ] && [ "$exit_code" -eq 0 ]; then
    exit_code=1
  fi
  exit "$exit_code"
}
trap cleanup EXIT

echo "===== [00] SUFFIX=$SUFFIX RG=$RG ($(date +%T)) ====="

echo "===== [01] 확장 설치 ($(date +%T)) ====="
az extension add --name application-insights --upgrade --only-show-errors
az extension add --name authV2 --upgrade --only-show-errors
az extension add --name log-analytics --upgrade --only-show-errors

echo "===== [02] RG + Plan(P0v4) + Web App + LAW + App Insights ($(date +%T)) ====="
az group create -n "$RG" -l "$LOC" -o none
az appservice plan create -g "$RG" -n "$PLAN" --is-linux --sku P0V4 -o none
az webapp create -g "$RG" -n "$APP" --plan "$PLAN" --runtime "PYTHON:3.12" -o none
az monitor log-analytics workspace create -g "$RG" -n "$LAW" -l "$LOC" -o none
LAW_ID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query id -o tsv)
LAW_CID=$(az monitor log-analytics workspace show -g "$RG" -n "$LAW" --query customerId -o tsv)
az monitor app-insights component create -g "$RG" --app "$APPI" -l "$LOC" \
  --workspace "$LAW_ID" -o none
APP_URL="https://$(az webapp show -g "$RG" -n "$APP" --query defaultHostName -o tsv)"
echo "APP_URL=$APP_URL"

echo "===== [03] zip deploy (v1) ($(date +%T)) ====="
az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true -o none
( cd "$REPO_DIR/app" && zip -qr "$TMP_DIR/app-v1.zip" . -x "tests/*" -x "__pycache__/*" -x "*.pyc" )
az webapp deploy -g "$RG" -n "$APP" --src-path "$TMP_DIR/app-v1.zip" --type zip --track-status
for i in $(seq 1 30); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/health" || true)
  [ "$code" = "200" ] && break; sleep 10
done
curl -s "$APP_URL/api/info"; echo
[ "$(curl -s "$APP_URL/api/info" | jq -r .version)" = "v1" ] && echo "[03] OK v1"

echo "===== [04] 앱 설정 → 재시작 관찰 ($(date +%T)) ====="
BEFORE=$(curl -s "$APP_URL/api/info" | jq -r .started_at)
az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings WELCOME_MESSAGE="안녕하세요, App Service 워크숍!" -o none
sleep 40
AFTER=$(curl -s "$APP_URL/api/info" | jq -r .started_at)
[ "$BEFORE" != "$AFTER" ] && echo "[04] OK 재시작 확인 ($BEFORE → $AFTER)"

echo "===== [05] staging 슬롯 + v2 배포 + swap/롤백 ($(date +%T)) ====="
az webapp deployment slot create -g "$RG" -n "$APP" --slot staging \
  --configuration-source "$APP" -o none
cp -a "$REPO_DIR/app" "$TMP_DIR/app-v2"
sed -i 's#^VERSION = "v1"#VERSION = "v2"#' "$TMP_DIR/app-v2/app.py"
( cd "$TMP_DIR/app-v2" && zip -qr "$TMP_DIR/app-v2.zip" . -x "tests/*" -x "__pycache__/*" -x "*.pyc" )
az webapp deploy -g "$RG" -n "$APP" --slot staging --src-path "$TMP_DIR/app-v2.zip" \
  --type zip --track-status
STG_URL="https://$(az webapp deployment slot list -g "$RG" -n "$APP" \
  --query "[?name=='staging'].defaultHostName | [0]" -o tsv)"
for i in $(seq 1 30); do
  [ "$(curl -s -o /dev/null -w "%{http_code}" "$STG_URL/health" || true)" = "200" ] && break
  sleep 10
done
[ "$(curl -s "$STG_URL/api/info" | jq -r .version)" = "v2" ] && echo "[05] staging=v2 OK"
az webapp deployment slot swap -g "$RG" -n "$APP" --slot staging --target-slot production
[ "$(curl -s "$APP_URL/api/info" | jq -r .version)" = "v2" ] && echo "[05] swap OK (prod=v2)"
az webapp deployment slot swap -g "$RG" -n "$APP" --slot staging --target-slot production
[ "$(curl -s "$APP_URL/api/info" | jq -r .version)" = "v1" ] && echo "[05] 롤백 OK (prod=v1)"

echo "===== [06] 트래픽 분할 카나리 (staging 20%) ($(date +%T)) ====="
az webapp traffic-routing set -g "$RG" -n "$APP" --distribution staging=20
sleep 10
count_v2=0
for i in $(seq 1 100); do
  v=$(curl -s "$APP_URL/api/info" | jq -r .version); [ "$v" = "v2" ] && count_v2=$((count_v2+1))
done
echo "[06] v2 비율: $count_v2/100 (기대 20±10)"
az webapp traffic-routing clear -g "$RG" -n "$APP"
az webapp deployment slot swap -g "$RG" -n "$APP" --slot staging --target-slot production
[ "$(curl -s "$APP_URL/api/info" | jq -r .version)" = "v2" ] && echo "[06] 승격 OK (prod=v2)"

echo "===== [07] Automatic scaling + Prewarmed A/B ($(date +%T)) ====="
PLAN_ID=$(az appservice plan show -g "$RG" -n "$PLAN" --query id -o tsv)
APP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)
az rest --method patch --uri "${PLAN_ID}?api-version=2024-11-01" \
  --body '{"sku":{"name":"P0v4","tier":"PremiumV4","size":"P0v4","family":"Pv4","capacity":1},"properties":{"elasticScaleEnabled":true,"maximumElasticWorkerCount":5}}' -o none
az rest --method patch --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' -o none
export PATH="$HOME/go/bin:$HOME/.local/bin:$PATH"
command -v hey >/dev/null || {
  go install github.com/rakyll/hey@latest
  export PATH="$HOME/go/bin:$HOME/.local/bin:$PATH"; }

latest_instance_count() {
  local start=${1:-$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)}
  az monitor metrics list \
    --resource "$APP_ID" --metric InstanceCount --interval PT1M \
    --aggregation Maximum --start-time "$start" -o json |
    jq -er '
      [.value[0].timeseries[0].data[]?
       | select(.maximum != null)
       | [(.timeStamp // .timestamp), (.maximum | floor)]
      ]
      | if length == 0 then
          error("InstanceCount metric unavailable")
        else
          sort_by(.[0])[] | @tsv
        end
    '
}

wait_for_single_instance() {
  local transition_at=$1
  local transition_epoch last_timestamp="" consecutive=0 samples timestamp count sample_epoch
  transition_epoch=$(date -d "$transition_at" +%s)
  for attempt in $(seq 1 20); do
    if ! samples=$(latest_instance_count "$transition_at" 2>/dev/null); then
      echo "InstanceCount=missing"
      sleep 30
      continue
    fi
    while IFS=$'\t' read -r timestamp count; do
      [ -n "$timestamp" ] || continue
      sample_epoch=$(date -d "$timestamp" +%s 2>/dev/null) || continue
      [ "$sample_epoch" -gt "$transition_epoch" ] || continue
      [ "$timestamp" = "$last_timestamp" ] && continue
      last_timestamp=$timestamp
      if [ "$count" -eq 1 ]; then
        consecutive=$((consecutive + 1))
      else
        consecutive=0
      fi
      echo "InstanceCount=$count timestamp=$timestamp (${consecutive}/2)"
      [ "$consecutive" -ge 2 ] && return 0
    done <<< "$samples"
    sleep 30
  done
  return 1
}

wait_for_health() {
  local body
  for attempt in $(seq 1 18); do
    if body=$(curl -fsS --max-time 10 "$APP_URL/health") &&
      jq -e '.status == "ok"' >/dev/null <<< "$body"
    then
      printf '%s\n' "$body"
      return 0
    fi
    sleep 5
  done
  return 1
}

restore_prewarmed_demo() {
  local status=0 settings startup_count
  [ -n "$APP_ID" ] || return 0
  if ! az rest --method patch \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
    -o none; then
    status=1
  fi
  if ! az webapp config appsettings delete -g "$RG" -n "$APP" \
    --setting-names STARTUP_DELAY_SECONDS -o none
  then
    status=1
  fi
  if ! wait_for_health; then
    echo "[07] 복원 후 /health 확인에 실패했습니다." >&2
    status=1
  fi
  if ! settings=$(az rest --method get \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --query "properties.{alwaysReady:minimumElasticInstanceCount,prewarmed:preWarmedInstanceCount}" \
    -o json); then
    status=1
  elif ! jq -e '(.alwaysReady == 1 and .prewarmed == 1)' >/dev/null <<< "$settings"; then
    echo "[07] 복원된 Always-ready/Prewarmed 설정이 예상과 다릅니다: $settings" >&2
    status=1
  fi
  if ! startup_count=$(az webapp config appsettings list -g "$RG" -n "$APP" \
    --query "[?name=='STARTUP_DELAY_SECONDS'] | length(@)" -o tsv); then
    status=1
  elif [ "$startup_count" != "0" ]; then
    echo "[07] STARTUP_DELAY_SECONDS가 삭제되지 않았습니다." >&2
    status=1
  fi
  if [ "$status" -eq 0 ]; then
    PREWARMED_RESTORE_NEEDED=0
    return 0
  fi
  return 1
}

run_instance_age_trial() {
  local label=$1
  local observation_file=$2
  local hey_output=$3
  local baseline_instance observer_status=0

  if ! baseline_instance=$(curl -fsS --max-time 10 "$APP_URL/api/info" |
    jq -er 'select((.instance | type) == "string" and (.instance | length) > 0) | .instance')
  then
    echo "$label 기준 instance를 확보하지 못했습니다. curl/jq 응답을 확인한 뒤 다시 시도하세요." >&2
    return 1
  fi

  echo "$label 기준 instance: $baseline_instance"
  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$hey_output" &
  HEY_PID=$!

  if python3 "$REPO_DIR/scripts/observe_instances.py" \
    --url "$APP_URL/api/info" \
    --baseline-instance "$baseline_instance" \
    --duration 180 \
    --concurrency 30 \
    --request-timeout 5 \
    --output "$observation_file"
  then
    observer_status=0
  else
    observer_status=$?
  fi

  wait "$HEY_PID" || true
  HEY_PID=""
  return "$observer_status"
}

handle_trial_observations() {
  local label=$1
  local observation_file=$2
  local observer_status=$3

  case "$observer_status" in
    0)
      if jq -e 'type == "array" and length > 0' "$observation_file" >/dev/null 2>&1; then
        return 0
      fi
      if ! restore_prewarmed_demo; then
        echo "[07] ${label} 관찰 도구가 유효한 JSON 배열을 남기지 못했고 복원에도 실패했습니다." >&2
      fi
      echo "[07] ${label} 관찰 도구가 유효한 JSON 배열을 남기지 못했습니다. 오류를 확인한 뒤 3단계부터 다시 시도하세요." >&2
      return 1
      ;;
    1)
      if ! restore_prewarmed_demo; then
        echo "[07] ${label} 관찰 도구 실패 후 복원에 실패했습니다." >&2
      fi
      echo "[07] ${label} 관찰 도구가 실패했습니다. 오류를 확인한 뒤 3단계부터 다시 시도하세요." >&2
      return 1
      ;;
    2)
      if ! restore_prewarmed_demo; then
        echo "[07] ${label}에서 새 instance를 관찰하지 못했고 복원에도 실패했습니다." >&2
      fi
      echo "[07] ${label}에서 새 instance를 관찰하지 못했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 시도했습니다. 부하를 다시 걸어 3단계부터 재실행하세요." >&2
      return 2
      ;;
    *)
      if ! restore_prewarmed_demo; then
        echo "[07] ${label} 관찰 도구가 예상하지 못한 상태($observer_status)로 종료했고 복원에도 실패했습니다." >&2
      fi
      echo "[07] ${label} 관찰 도구가 예상하지 못한 상태($observer_status)로 종료했습니다. 오류를 확인한 뒤 3단계부터 다시 시도하세요." >&2
      return 1
      ;;
  esac
}

PREWARMED_RESTORE_NEEDED=1
if ! az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings STARTUP_DELAY_SECONDS=20 -o none
then
  if ! restore_prewarmed_demo; then
    echo "[07] 시작 지연 준비 단계의 복원 및 검증에 실패했습니다." >&2
  else
    echo "[07] 시작 지연 준비 단계의 복원 및 검증을 완료했습니다." >&2
  fi
  echo "[07] 시작 지연 설정에 실패했습니다." >&2
  exit 1
fi

if ! wait_for_health; then
  if ! restore_prewarmed_demo; then
    echo "[07] 시작 지연 준비 단계의 복원 및 검증에 실패했습니다." >&2
  else
    echo "[07] 시작 지연 준비 단계의 복원 및 검증을 완료했습니다." >&2
  fi
  echo "[07] 시작 지연 준비 단계의 /health 확인이 실패했습니다." >&2
  exit 1
fi

NO_PREWARM_OBSERVATIONS="$TMP_DIR/prewarmed-0-observations.json"
PREWARM_OBSERVATIONS="$TMP_DIR/prewarmed-1-observations.json"

if ! az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":0}}' \
  -o none
then
  if ! restore_prewarmed_demo; then
    echo "[07] 시험 A 설정 변경 후 복원에 실패했습니다." >&2
  else
    echo "[07] 시험 A 설정 변경 후 복원 및 검증을 완료했습니다." >&2
  fi
  echo "[07] 시험 A 설정 변경에 실패했습니다." >&2
  exit 1
fi
A_TRANSITION_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if ! wait_for_single_instance "$A_TRANSITION_AT"; then
  if ! restore_prewarmed_demo; then
    echo "[07] 시험 A 기준 상태 복원에 실패했습니다." >&2
  fi
  echo "[07] 시험 A 기준 상태를 확보하지 못했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 시도했습니다." >&2
  exit 1
fi

observer_status=0
if run_instance_age_trial "Prewarmed=0" "$NO_PREWARM_OBSERVATIONS" "$TMP_DIR/hey-burst-0.out"; then
  observer_status=0
else
  observer_status=$?
fi
if handle_trial_observations "시험 A" "$NO_PREWARM_OBSERVATIONS" "$observer_status"; then
  :
else
  trial_exit=$?
  exit "$trial_exit"
fi

SCALE_IN_TRANSITION_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
if ! wait_for_single_instance "$SCALE_IN_TRANSITION_AT"; then
  if ! restore_prewarmed_demo; then
    echo "[07] 시험 A 후 복원 및 검증에 실패했습니다." >&2
  else
    echo "[07] 시험 A 후 복원 및 검증을 완료했습니다." >&2
  fi
  echo "[07] 시험 B 시작 전 기준 상태를 확보하지 못했습니다." >&2
  exit 1
fi

if ! az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  -o none
then
  if ! restore_prewarmed_demo; then
    echo "[07] 시험 B 설정 변경 후 복원에 실패했습니다." >&2
  else
    echo "[07] 시험 B 설정 변경 후 복원 및 검증을 완료했습니다." >&2
  fi
  echo "[07] 시험 B 설정 변경에 실패했습니다." >&2
  exit 1
fi
B_TRANSITION_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)

if ! wait_for_single_instance "$B_TRANSITION_AT"; then
  if ! restore_prewarmed_demo; then
    echo "[07] 시험 B 기준 상태 복원에 실패했습니다." >&2
  fi
  echo "[07] 시험 B 시작 전 기준 상태를 확보하지 못했습니다." >&2
  exit 1
fi
observer_status=0
if run_instance_age_trial "Prewarmed=1" "$PREWARM_OBSERVATIONS" "$TMP_DIR/hey-burst-1.out"; then
  observer_status=0
else
  observer_status=$?
fi
if handle_trial_observations "시험 B" "$PREWARM_OBSERVATIONS" "$observer_status"; then
  :
else
  trial_exit=$?
  exit "$trial_exit"
fi

printf '시험\tinstance\tstarted_at\tfirst_seen_at\tfirst_response_age\n'
jq -r '.[] | ["Prewarmed=0", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv' \
  "$NO_PREWARM_OBSERVATIONS"
jq -r '.[] | ["Prewarmed=1", .instance, .started_at, .first_seen_at, (.first_response_age | tostring)] | @tsv' \
  "$PREWARM_OBSERVATIONS"
echo "[07] first_response_age는 관찰값이며 단일 실행의 속도 승자를 의미하지 않습니다."

if ! restore_prewarmed_demo; then
  echo "[07] 복원에 실패했습니다. 이후 단계로 진행하지 않습니다." >&2
  exit 1
fi

echo "===== [08] 진단 설정 + KQL + App Insights ($(date +%T)) ====="
WEBAPP_ID=$(az webapp show -g "$RG" -n "$APP" --query id -o tsv)
az monitor diagnostic-settings create --name appsvc-diag --resource "$WEBAPP_ID" \
  --workspace "$LAW_ID" \
  --logs '[{"category":"AppServiceHTTPLogs","enabled":true},{"category":"AppServiceConsoleLogs","enabled":true},{"category":"AppServicePlatformLogs","enabled":true}]' \
  --metrics '[{"category":"AllMetrics","enabled":true}]' -o none
AI_CONN=$(az monitor app-insights component show -g "$RG" --app "$APPI" \
  --query connectionString -o tsv)
az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings APPLICATIONINSIGHTS_CONNECTION_STRING="$AI_CONN" -o none
sleep 40
for i in $(seq 1 30); do curl -s "$APP_URL/api/info" > /dev/null; done
echo "[08] 로그 적재 대기(최대 10분) 후 KQL 확인 — 리허설에서는 5분 후 1회 시도"
sleep 300
az monitor log-analytics query -w "$LAW_CID" --analytics-query \
  'AppServiceHTTPLogs | where TimeGenerated > ago(30m) | summarize hits=count() by CsUriStem | order by hits desc' \
  -o table || echo "[08] 적재 지연 — KEEP=1이면 포털에서 재확인"

if [ "${SKIP_OPTIONAL:-0}" != "1" ]; then
  echo "===== [09] Easy Auth (미인증 리디렉션 확인까지) ($(date +%T)) ====="
  TENANT_ID=$(az account show --query tenantId -o tsv)
  CLIENT_ID=$(az ad app create --display-name "auth-appsvcworkshop-$SUFFIX" \
    --web-redirect-uris "$APP_URL/.auth/login/aad/callback" \
    --sign-in-audience AzureADMyOrg --query appId -o tsv)
  az ad app update --id "$CLIENT_ID" --enable-id-token-issuance true
  CLIENT_SECRET=$(az ad app credential reset --id "$CLIENT_ID" --display-name easyauth \
    --query password -o tsv)
  az webapp auth config-version upgrade -g "$RG" -n "$APP" -o none
  az webapp auth microsoft update -g "$RG" -n "$APP" \
    --client-id "$CLIENT_ID" --client-secret "$CLIENT_SECRET" \
    --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" --yes -o none
  az webapp auth update -g "$RG" -n "$APP" --enabled true \
    --action RedirectToLoginPage --redirect-provider azureActiveDirectory -o none
  sleep 40
  code_api=$(curl -s -o /dev/null -w "%{http_code}" "$APP_URL/")
  code_html=$(curl -s -o /dev/null -w "%{http_code}" -H "User-Agent: Mozilla/5.0" "$APP_URL/")
  echo "[09] 미인증 응답: API=$code_api (기대 401) / 브라우저 UA=$code_html (기대 302)"

  echo "===== [10] Redis 사이드카 ($(date +%T)) ====="
  az webapp auth update -g "$RG" -n "$APP" --enabled false -o none
  az webapp sitecontainers create -g "$RG" -n "$APP" --container-name redis \
    --image mcr.microsoft.com/mirror/docker/library/redis:7.2 --is-main false
  az webapp restart -g "$RG" -n "$APP"
  sleep 60
  curl -s "$APP_URL/cache"; echo
  [ "$(curl -s "$APP_URL/cache" | jq -r .cache)" = "ok" ] && echo "[10] 사이드카 OK"

  echo "===== [11] Auto-heal ($(date +%T)) ====="
  az resource update -g "$RG" --resource-type "Microsoft.Web/sites/config" \
    --name "$APP/config/web" \
    --set properties.autoHealEnabled=true \
    "properties.autoHealRules={\"triggers\":{\"slowRequests\":{\"count\":5,\"timeInterval\":\"00:02:00\",\"timeTaken\":\"00:00:03\"}},\"actions\":{\"actionType\":\"Recycle\",\"minProcessExecutionTime\":\"00:01:00\"}}" \
    -o none
  sleep 90   # minProcessExecutionTime 경과 대기
  BEFORE=$(curl -s "$APP_URL/api/info" | jq -r .started_at)
  for i in $(seq 1 6); do curl -s "$APP_URL/slow?sec=5" > /dev/null; echo "slow $i/6"; done
  sleep 90
  AFTER=$(curl -s "$APP_URL/api/info" | jq -r .started_at)
  [ "$BEFORE" != "$AFTER" ] && echo "[11] Auto-heal 재활용 OK ($BEFORE → $AFTER)" \
    || echo "[11] ⚠️ 재활용 미관찰 — 임계값/대기시간 재실측 필요"
fi

echo "===== [12] 정리 ($(date +%T)) ====="
if [ "${KEEP:-0}" = "1" ]; then
  echo "KEEP=1 — RG 삭제 생략. 수동 정리: az group delete -n $RG --yes"
  [ -n "$CLIENT_ID" ] && echo "Entra 앱 삭제: az ad app delete --id $CLIENT_ID"
else
  az group delete -n "$RG" --yes --no-wait
  [ -n "$CLIENT_ID" ] && az ad app delete --id "$CLIENT_ID"
  echo "[12] 삭제 요청 완료 (RG 삭제는 수 분 소요)"
fi
echo "===== 리허설 종료 ====="
