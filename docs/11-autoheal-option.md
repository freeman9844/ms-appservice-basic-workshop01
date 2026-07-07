# 11. (선택) Auto-heal & 진단

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

> ⚠️ **(선택) 모듈 — 건너뛰어도 12 정리에 지장 없음.** 이 모듈을 건너뛰려면 [12. 정리](12-cleanup.md)로 직접 이동하십시오.

---

## 목표

이 모듈에서는 App Service **Auto-heal** 기능으로 슬로우 요청 규칙을 설정하고, 규칙이 트리거되면 워커 프로세스가 자동으로 재활용(Recycle)되는 과정을 관찰합니다.

- `/api/info`의 `started_at` 값을 이용해 프로세스 재활용 전후를 비교합니다.
- `/slow` 엔드포인트로 슬로우 요청을 인위적으로 발생시켜 트리거를 재현합니다.
- **App Service 진단**(포털 "문제 진단 및 해결") 화면에서 자동 수집된 이벤트를 확인합니다.
- 모듈 종료 상태: **Auto-heal 규칙 설정 완료·재활용 관찰됨, Easy Auth 비활성**

---

## 소요 시간

약 15–25분

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
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
```

---

## 👁️ Auto-heal 개념

Auto-heal은 App Service가 설정된 조건(트리거)을 감지하면 정해진 액션(예: 프로세스 재활용)을 자동으로 수행하는 기능입니다.

| 트리거 종류 | 설명 | 예시 값 |
|---|---|---|
| **slowRequests** | 지정 시간 내 임계 횟수 이상의 느린 요청 | `count: 5, timeTaken: 00:00:03` |
| **statusCodes** | 특정 HTTP 상태코드가 지정 횟수 이상 발생 | `status: 500, count: 10` |
| **memoryUsage** | 프로세스 메모리가 임계값 초과 | `privateBytesInKB: 1048576` |
| **requestCount** | 지정 시간 내 총 요청 수 초과 | `count: 1000` |

| 액션 종류 | 설명 |
|---|---|
| **Recycle** | 워커 프로세스 재활용(재시작) |
| **LogEvent** | 이벤트 로그만 기록 |
| **CustomAction** | 사용자 지정 실행 파일 수행 |

> 👁️ `minProcessExecutionTime`은 프로세스가 기동된 직후 너무 빨리 재활용되지 않도록 보호하는 안전장치입니다. 설정값(예: `00:01:00`) 이전에는 Auto-heal 액션이 실행되지 않습니다.

> 👁️ **04 모듈에서 배운 관찰 기법 재사용** — 이 모듈에서 사용하는 `started_at` 비교 방식은 04 모듈에서 로그 스트리밍과 함께 배운 앱 상태 관찰 기법을 그대로 재사용합니다. 플랫폼 이벤트를 코드 없이 관찰하는 동일한 접근법입니다.

---

## 0단계 — Easy Auth 일시 비활성화

모듈 10(사이드카)을 건너뛴 경우에도 Easy Auth가 활성화되어 있을 수 있습니다. curl 검증을 위해 멱등으로 비활성화합니다.

🟢 **실행**

```bash
az webapp auth update -g $RG -n $APP --enabled false
```

---

## 1단계 — Auto-heal 규칙 설정

> ⚠️ **인스턴스 수 확인** — 모듈 07에서 여러 인스턴스로 확장한 경우 curl 요청이 다른 인스턴스에 분산되어 트리거가 충족되지 않을 수 있습니다. 아래 명령으로 인스턴스가 1개인지 확인한 후 진행하십시오. 1개가 아니라면 인스턴스가 1개로 줄어들 때까지 기다립니다.

🟢 **실행** — 인스턴스 수 확인

```bash
az webapp list-instances -g $RG -n $APP -o table
```

🟢 **실행** — Auto-heal 규칙을 설정합니다. 2분 이내에 3초를 초과하는 요청이 5회 이상 발생하면 워커 프로세스를 재활용합니다.

```bash
az webapp config set -g $RG -n $APP --generic-configurations '{
  "autoHealEnabled": true,
  "autoHealRules": {
    "triggers": {"slowRequests": {"count": 5, "timeInterval": "00:02:00", "timeTaken": "00:00:03"}},
    "actions": {"actionType": "Recycle", "minProcessExecutionTime": "00:01:00"}
  }}'
```

> 👁️ `minProcessExecutionTime: "00:01:00"`이 설정되어 있으므로, 규칙 적용 후 최소 **90초** 대기 후 기준값을 측정하는 것이 권장됩니다.

---

## 2단계 — 기준 started_at 기록

규칙 적용 후 90초 대기 후 현재 프로세스의 시작 시각을 기록합니다. 이 값이 재활용 후 변경되면 재활용이 성공한 것입니다.

🟢 **실행**

```bash
# 90초 대기(minProcessExecutionTime) 후 — 변경 전 시작 시각 기록
curl -s $APP_URL/api/info | jq -r .started_at
```

📋 **예상 출력 (예시)**

```
2025-07-07T08:10:23.456789
```

> 👁️ 이 값을 메모해 두십시오. 4단계에서 이 값이 변경되는지 확인합니다.

---

## 3단계 — 슬로우 요청 트리거

`/slow` 엔드포인트에 5초짜리 요청을 2분 이내에 6회 전송합니다. 설정한 임계값(5회)을 초과하면 Auto-heal 트리거가 발동합니다.

🟢 **실행**

```bash
# 트리거: 3초 초과 요청을 2분 안에 5회 이상 → /slow(5초)를 6회
for i in $(seq 1 6); do curl -s "$APP_URL/slow?sec=5" > /dev/null; echo "slow $i/6"; done
```

📋 **예상 출력**

```
slow 1/6
slow 2/6
slow 3/6
slow 4/6
slow 5/6
slow 6/6
```

> 👁️ 각 요청이 5초씩 걸리므로 6회 전송에 약 30초 소요됩니다. 2분 이내에 완료되므로 트리거 조건이 충족됩니다.

---

## 4단계 — 프로세스 재활용 확인

Auto-heal이 트리거된 후 워커 프로세스가 재활용되기까지 60–90초 소요됩니다. 기다린 후 `started_at`을 다시 확인합니다.

🟢 **실행**

```bash
# 60–90초 후
curl -s $APP_URL/api/info | jq -r .started_at   # 이전 값과 다름 = 프로세스 재활용됨
```

📋 **예상 출력 — 재활용 성공 시 (예시)**

```
2025-07-07T08:12:01.123456
```

> 👁️ 2단계에서 기록한 값보다 이 값이 더 나중 시각이면 워커 프로세스가 자동으로 재활용된 것입니다. 값이 동일하면 아직 재활용이 완료되지 않았거나 트리거가 충족되지 않은 것입니다.

---

## 🖼️ App Service 진단 — 포털에서 이벤트 확인

🖼️ **포털 확인** — 자동 수집된 Auto-heal 이벤트를 App Service 진단 화면에서 확인합니다.

1. Azure Portal → 해당 App Service 리소스로 이동합니다.
2. 왼쪽 메뉴에서 **"문제 진단 및 해결"** 을 클릭합니다.
3. **"가용성 및 성능"** 카테고리를 선택하거나 검색창에 **"Auto heal"** 을 입력합니다.
4. Auto-heal 이벤트 타임라인에서 재활용이 기록되었는지 확인합니다.

> 👁️ "문제 진단 및 해결"은 App Service의 내장 진단 플랫폼으로, Auto-heal, 배포 오류, 성능 이슈 등을 자동으로 분석합니다. 별도 에이전트 설치 없이 플랫폼이 수집한 데이터를 활용합니다.

---

## 검증

| 확인 항목 | 기대 결과 |
|---|---|
| `az webapp auth update --enabled false` | 명령 오류 없이 JSON 출력 |
| `az webapp list-instances` | 인스턴스 1개 확인 |
| `az webapp config set --generic-configurations` | 오류 없이 구성 적용 |
| 2단계 `started_at` 기록 | 타임스탬프 값 메모 완료 |
| 3단계 슬로우 요청 6회 전송 | `slow 1/6` … `slow 6/6` 순서대로 출력 |
| 4단계 `started_at` 재확인 | 2단계 값보다 나중 시각(프로세스 재활용 확인) |
| 포털 "문제 진단 및 해결" | Auto-heal 이벤트 타임라인에서 재활용 이벤트 확인 |

---

## 트러블슈팅

### (1) 재활용 미발생 — started_at이 변하지 않음

임계값이 2분 창 안에 충족되지 않았거나 대기 시간이 부족했을 수 있습니다.

- `sec=5`가 `timeTaken: 00:00:03`(3초)를 실제로 초과하는지 확인합니다.

```bash
time curl -s "$APP_URL/slow?sec=5" > /dev/null
```

- 인스턴스가 여러 개이면 요청이 분산됩니다. `az webapp list-instances`로 인스턴스 수를 확인하고 1개로 줄어들 때까지 기다립니다.
- 60–90초 대기가 부족했을 수 있습니다. 추가로 60초 더 기다린 후 재확인합니다.

### (2) `/api/info` 또는 `/slow` 엔드포인트 403 응답

Easy Auth가 아직 활성 상태입니다. 0단계 명령을 재실행합니다.

```bash
az webapp auth update -g $RG -n $APP --enabled false
```

### (3) `az webapp config set --generic-configurations` 오류

JSON 형식 오류일 가능성이 있습니다. Cloud Shell에서 단일 따옴표 내 이중 따옴표 JSON이 지원되지 않는 경우 파일로 분리합니다.

```bash
cat > autoheal.json << 'EOF'
{
  "autoHealEnabled": true,
  "autoHealRules": {
    "triggers": {"slowRequests": {"count": 5, "timeInterval": "00:02:00", "timeTaken": "00:00:03"}},
    "actions": {"actionType": "Recycle", "minProcessExecutionTime": "00:01:00"}
  }
}
EOF
az webapp config set -g $RG -n $APP --generic-configurations @autoheal.json
```

### (4) `jq: error` 또는 started_at 필드 없음

`/api/info` 응답 구조를 확인합니다.

```bash
curl -s $APP_URL/api/info | jq
```

`started_at` 키가 없으면 앱이 아직 기동 중이거나 엔드포인트 경로가 다를 수 있습니다. 30초 후 재시도합니다.

---

이전 모듈: [10. Redis 사이드카(선택)](10-sidecar-option.md) | 다음 모듈: [12. 정리](12-cleanup.md)
