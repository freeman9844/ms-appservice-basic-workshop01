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
TMP_DIR=$(mktemp -d)
CLIENT_ID=""
APP_ID=""
HEY_PID=""
PREWARMED_RESTORE_NEEDED=0

cleanup() {
  if [ -n "$HEY_PID" ]; then
    kill "$HEY_PID" 2>/dev/null || true
    wait "$HEY_PID" 2>/dev/null || true
    HEY_PID=""
  fi
  if [ "$PREWARMED_RESTORE_NEEDED" = "1" ] && [ -n "$APP_ID" ]; then
    restore_prewarmed_demo
  fi
  rm -rf "$TMP_DIR"
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
  local start
  start=$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)
  az monitor metrics list \
    --resource "$APP_ID" --metric InstanceCount --interval PT1M \
    --aggregation Maximum --start-time "$start" -o json |
    jq -er '
      [.value[0].timeseries[0].data[].maximum // empty]
      | if length == 0 then
          error("InstanceCount metric unavailable")
        else
          last | floor
        end
    '
}

wait_for_single_instance() {
  local count
  for attempt in $(seq 1 20); do
    if ! count=$(latest_instance_count 2>/dev/null); then
      echo "InstanceCount=missing"
      sleep 30
      continue
    fi
    echo "InstanceCount=$count"
    [ "$count" -eq 1 ] && return 0
    sleep 30
  done
  return 1
}

restore_prewarmed_demo() {
  [ -n "$APP_ID" ] || return 0
  az rest --method patch \
    --uri "${APP_ID}/config/web?api-version=2024-11-01" \
    --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
    -o none || true
  az webapp config appsettings delete -g "$RG" -n "$APP" \
    --setting-names STARTUP_DELAY_SECONDS -o none || true
  PREWARMED_RESTORE_NEEDED=0
}

measure_scale_out() {
  local label=$1
  local output_file=$2
  local result_var=$3
  local started elapsed unique_instances

  hey -z 180s -c 100 -q 10 "$APP_URL/api/info" > "$output_file" &
  HEY_PID=$!
  started=$(date +%s)
  printf -v "$result_var" '%s' timeout

  for attempt in $(seq 1 36); do
    unique_instances=$(
      for i in $(seq 1 30); do
        curl -s "$APP_URL/api/info" | jq -r .instance
      done | sort -u | wc -l
    )
    elapsed=$(( $(date +%s) - started ))
    echo "$label: ${elapsed}초, 응답 인스턴스 ${unique_instances}개"
    if [ "$unique_instances" -ge 2 ]; then
      printf -v "$result_var" '%s' "$elapsed"
      break
    fi
    sleep 5
  done

  kill "$HEY_PID" 2>/dev/null || true
  wait "$HEY_PID" 2>/dev/null || true
  HEY_PID=""
}

az webapp config appsettings set -g "$RG" -n "$APP" \
  --settings STARTUP_DELAY_SECONDS=20 -o none
PREWARMED_RESTORE_NEEDED=1

for attempt in $(seq 1 18); do
  curl -fsS "$APP_URL/health" >/dev/null && break
  sleep 5
done

if ! curl -fsS "$APP_URL/health" >/dev/null; then
  restore_prewarmed_demo
  echo "[07] 시작 지연 준비 단계의 /health 확인이 실패했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 완료했습니다." >&2
  exit 1
fi

az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":0}}' \
  -o none

if ! wait_for_single_instance; then
  restore_prewarmed_demo
  echo "[07] 시험 A 기준 상태 복원에 실패했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 완료했습니다." >&2
  exit 1
fi

hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > "$TMP_DIR/hey-prime-0.out"
measure_scale_out "Prewarmed=0" "$TMP_DIR/hey-burst-0.out" NO_PREWARM_SECONDS
echo "Prewarmed=0: $NO_PREWARM_SECONDS"

if ! wait_for_single_instance; then
  restore_prewarmed_demo
  echo "[07] 시험 B 시작 전 기준 상태 복원에 실패했습니다. Prewarmed=1 복구와 STARTUP_DELAY_SECONDS 삭제를 완료했습니다." >&2
  exit 1
fi

az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  -o none

hey -z 60s -c 5 -q 2 "$APP_URL/api/info" > "$TMP_DIR/hey-prime-1.out"
measure_scale_out "Prewarmed=1" "$TMP_DIR/hey-burst-1.out" PREWARM_SECONDS
echo "Prewarmed=1: $PREWARM_SECONDS"

if [[ "$NO_PREWARM_SECONDS" =~ ^[0-9]+$ && "$PREWARM_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "Prewarmed=0 : ${NO_PREWARM_SECONDS}초"
  echo "Prewarmed=1 : ${PREWARM_SECONDS}초"
  echo "개선         : $((NO_PREWARM_SECONDS - PREWARM_SECONDS))초"
else
  echo "한 시험이 timeout되어 시간 차이를 계산할 수 없습니다."
fi

restore_prewarmed_demo

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
