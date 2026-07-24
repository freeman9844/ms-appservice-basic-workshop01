# 12. (선택) Auto-heal & 진단

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **예상 화면** = 브라우저/포털 스크린샷 참고

> ⚠️ **(선택) 모듈 — 건너뛰어도 13 정리에 지장 없음.** 이 모듈을 건너뛰려면 [13. 정리](13-cleanup.md)로 직접 이동하십시오.

---

## 목표

이 모듈에서는 App Service **Auto-heal** 기능으로 슬로우 요청 규칙을 설정하고, 규칙이 트리거되면 워커 프로세스가 자동으로 재활용(Recycle)되는 과정을 관찰합니다.

- `/api/info`의 `started_at` 값을 이용해 프로세스 재활용 전후를 비교합니다.
- `/slow` 엔드포인트로 슬로우 요청을 인위적으로 발생시켜 트리거를 재현합니다.
- **App Service 진단**(포털 "문제 진단 및 해결") 화면에서 자동 수집된 이벤트를 확인합니다.
- 모듈 종료 상태: **Auto-heal 규칙 설정 완료·재활용 관찰됨** (모듈 10 수행자는 Easy Auth 비활성 상태)

---

## 0단계 — (선택) 변수 재설정

> ⏭️ **이전 모듈(08·10 또는 11)에서 이어서 같은 터미널로 진행 중이라면 이 단계는 건너뛰세요.**
> 새 터미널 세션을 열었거나 Cloud Shell이 재시작되어 변수가 사라진 경우에만 실행합니다.
> `SUFFIX` 는 **02 모듈에서 사용한 값과 동일하게** 입력하세요.

🟢 **실행**

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.
SUFFIX=<이전에_메모한_값>
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
echo "APP_URL=$APP_URL"
```

📋 **예상 출력**

```
APP_URL=https://app-appsvcworkshop-<SUFFIX>.azurewebsites.net
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

> ⚠️ **Linux 지원 범위** — Linux App Service에서 안정적으로 지원되는 액션은 **Recycle**입니다. `LogEvent`와 `CustomAction`은 Windows App Service 기준 액션으로, Linux에서는 지원이 제한적일 수 있어 이 워크숍에서는 Recycle만 사용합니다.

> 👁️ `minProcessExecutionTime`은 프로세스가 기동된 직후 너무 빨리 재활용되지 않도록 보호하는 안전장치입니다. 설정값(예: `00:01:00`) 이전에는 Auto-heal 액션이 실행되지 않습니다.

> 👁️ **앞선 모듈의 관찰 기법 재사용** — 03 모듈의 로그 스트리밍과 04 모듈의 `started_at` 비교 방식을 함께 활용하여 프로세스 재활용을 확인합니다. 플랫폼 이벤트를 코드 수정 없이 관찰하는 동일한 접근법입니다.

### 👁️ 재시작(Recycle)이 왜 의미가 있는가?

Recycle은 VM이나 인스턴스를 재부팅하는 것이 아니라 **워커 프로세스만** 종료 후 새로 기동하는 것입니다. `az webapp restart`를 사람이 누르는 대신 플랫폼이 자동으로 수행한다고 이해하면 됩니다.

Auto-heal의 전제는 "느린 응답의 원인이 **프로세스 내부에 누적된 불량 상태**"라는 것입니다. 이런 문제는 코드 수정 전까지 근본 해결이 불가능하지만, 프로세스를 교체하면 증상이 즉시 사라집니다.

| 원인 (재시작이 유효한 경우) | 재시작 효과 |
|---|---|
| 메모리 누수 → GC 압박으로 응답 지연 | 힙 초기화로 즉시 해소 |
| 스레드/DB 커넥션 풀 고갈 | 풀 재생성으로 해소 |
| 교착 락·무한 루프 워커 등 런타임 상태 오염 | 프로세스 교체로 해소 |
| 소켓/파일 핸들 누수 | 핸들 반환으로 해소 |

반대로 **재시작이 효과 없는 경우**도 분명합니다.

- **외부 의존성이 원인** (DB 자체가 느림, 외부 API 지연) — 재시작해도 그대로 느리고, 재기동 콜드 스타트로 오히려 일시 악화될 수 있습니다.
- **트래픽 과부하** — 용량 부족은 스케일 아웃(모듈 07)이 답입니다.
- **정상적으로 느린 엔드포인트** — 이 워크숍의 `/slow?sec=5`가 정확히 이 경우입니다. 앱은 건강한데 트리거만 발동합니다. 실습 재현용으로는 적합하지만, **운영에서 임계값을 잘못 잡으면 건강한 앱을 반복적으로 재시작시키는 역효과**가 납니다.

> ⚠️ **Auto-heal은 근본 치료가 아니라 자동화된 응급 처치(mitigation)입니다.** 목적은 원인 규명 전까지 서비스 가용성을 유지해 MTTR을 줄이는 것입니다. 트리거가 발동했다면 반드시 근본 원인 분석을 병행해야 하며 — 이 모듈 마지막에 포털 "문제 진단 및 해결"에서 이벤트를 확인하는 이유가 바로 "재시작으로 덮고 끝내지 말라"는 취지입니다.

---

## 1단계 — Easy Auth 일시 비활성화(모듈 10 수행자만)

> ⏭️ **모듈 10(선택)를 건너뛰었다면 이 단계도 건너뛰고 2단계로 이동하세요.**

모듈 10에서 Easy Auth를 활성화했다면 — 모듈 11(사이드카)을 건너뛴 경우에도 — 활성 상태일 수 있습니다. curl 검증을 위해 멱등으로 비활성화합니다.

🟢 **실행**

```bash
# /slow와 /api/info를 직접 호출할 수 있도록 Easy Auth를 일시 비활성화합니다.
az webapp auth update -g $RG -n $APP --enabled false
```

---

## 2단계 — Auto-heal 규칙 설정

> ⚠️ **인스턴스 수 확인** — 모듈 07에서 여러 인스턴스로 확장한 경우 curl 요청이 다른 인스턴스에 분산되어 트리거가 충족되지 않을 수 있습니다. 아래 명령으로 인스턴스가 1개인지 확인한 후 진행하십시오. 1개가 아니라면 인스턴스가 1개로 줄어들 때까지 기다립니다.

🟢 **실행** — 인스턴스 수 확인

```bash
# Auto-heal 요청 횟수가 한 인스턴스에 모이도록 현재 인스턴스 수를 확인합니다.
az webapp list-instances -g $RG -n $APP -o table
```

🟢 **실행** — Auto-heal 규칙을 설정합니다. 2분 이내에 3초를 초과하는 요청이 5회 이상 발생하면 워커 프로세스를 재활용합니다.

```bash
# 3초 초과 요청이 2분 동안 5회 발생하면 프로세스를 재활용하도록 Auto-heal을 설정합니다.
# autoHealEnabled=true를 켠 뒤 slowRequests 트리거와 Recycle 액션을 한 JSON 객체로 한 번에 써서,
# null 상태의 autoHealRules에도 부분 병합 없이 원하는 기준(count/timeInterval/timeTaken/minProcessExecutionTime)을 그대로 기록합니다.
az resource update -g $RG --resource-type "Microsoft.Web/sites/config" \
  --name "$APP/config/web" \
  --set properties.autoHealEnabled=true \
  "properties.autoHealRules={\"triggers\":{\"slowRequests\":{\"count\":5,\"timeInterval\":\"00:02:00\",\"timeTaken\":\"00:00:03\"}},\"actions\":{\"actionType\":\"Recycle\",\"minProcessExecutionTime\":\"00:01:00\"}}" \
  --query "properties.autoHealRules" -o json
```

📋 **예상 출력 (일부)**

```json
{
  "actions": {
    "actionType": "Recycle",
    "minProcessExecutionTime": "00:01:00"
  },
  "triggers": {
    "slowRequests": {
      "count": 5,
      "timeInterval": "00:02:00",
      "timeTaken": "00:00:03"
    }
  }
}
```

> ⚠️ `az webapp config set --generic-configurations`로 중첩 JSON을 전달하면 `slowRequests` 트리거가 적용되지 않는 문제가 있어(부분 병합), 이 모듈에서는 `az resource update`로 사이트 구성 리소스를 직접 갱신합니다. 또한 `autoHealRules`가 아직 설정된 적 없는(null) 앱에서는 `properties.autoHealRules.triggers...`처럼 중첩 경로로 `--set`하면 `Couldn't find 'triggers' in 'properties.autoHealRules'` 오류가 발생하므로, 위 명령처럼 **`autoHealRules` 객체 전체를 한 번에 설정**합니다.

> 👁️ `minProcessExecutionTime: "00:01:00"`이 설정되어 있으므로, 규칙 적용 후 최소 **90초** 대기 후 기준값을 측정하는 것이 권장됩니다.

---

## 3단계 — 기준 started_at 기록

규칙 적용 후 90초 대기 후 현재 프로세스의 시작 시각을 기록합니다. 이 값이 재활용 후 변경되면 재활용이 성공한 것입니다.

🟢 **실행**

```bash
# 90초 실제 대기(minProcessExecutionTime 창 회피) 후 변경 전 시작 시각 기록
# started_at 기준값은 "규칙 적용 후 다시 시작된 현재 프로세스"의 시각이어야 하므로 먼저 sleep 90으로 보호 창을 넘깁니다.
sleep 90
curl -s $APP_URL/api/info | jq -r .started_at
```

📋 **예상 출력 (예시)**

```
2026-07-08T02:38:14+00:00
```

> 👁️ 이 값을 메모해 두십시오. 5단계에서 이 값이 변경되는지 확인합니다.

---

## 4단계 — 슬로우 요청 트리거

`/slow` 엔드포인트에 5초짜리 요청을 2분 이내에 6회 전송합니다. 설정한 임계값(5회)을 초과하면 Auto-heal 트리거가 발동합니다.

🟢 **실행**

```bash
# 트리거: 3초 초과 요청을 2분 안에 5회 이상 → /slow(5초)를 6회
# 6회를 보내는 이유는 임계값 5회를 여유 있게 넘겨 slowRequests 누락 가능성을 줄이기 위해서입니다.
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

## 5단계 — 프로세스 재활용 확인

Auto-heal이 트리거된 후 워커 프로세스가 재활용되기까지 60–90초 소요됩니다. 기다린 후 `started_at`을 다시 확인합니다.

🟢 **실행**

```bash
# 90초 실제 대기 — 트리거 감지 후 Recycle 실행까지 60–90초 소요
# 여기서 읽는 started_at을 3단계 메모값과 비교해 더 늦은 시각으로 바뀌었는지 판단하면 Recycle 성공 여부를 확인할 수 있습니다.
sleep 90
curl -s $APP_URL/api/info | jq -r .started_at   # 이전 값과 다름 = 프로세스 재활용됨
```

📋 **예상 출력 — 재활용 성공 시 (예시)**

```
2026-07-08T02:41:53+00:00
```

> 👁️ 위 예시는 리허설 실측값입니다 — 슬로우 요청 6회 전송 후 약 90초 뒤 `started_at`이 3단계 기록값(`02:38:14`)에서 새 시각(`02:41:53`)으로 변경되어 워커 프로세스 재활용이 확인되었습니다.

> 👁️ 3단계에서 기록한 값보다 이 값이 더 나중 시각이면 워커 프로세스가 자동으로 재활용된 것입니다. 값이 동일하면 아직 재활용이 완료되지 않았거나 트리거가 충족되지 않은 것입니다.

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
- **`minProcessExecutionTime` 창 안에서 트리거되었을 수 있습니다.** 2단계 규칙 적용은 사이트 구성 변경이라 앱이 재시작되며, 재시작 후 1분 이내에는 트리거가 충족돼도 Recycle이 억제됩니다. 3단계의 `sleep 90` 없이 바로 4단계를 실행했다면 이 경우입니다 — 4단계(slow 요청 6회)부터 다시 실행하고 90초 대기 후 재확인합니다.

### (2) `/api/info` 또는 `/slow` 엔드포인트 403 응답

Easy Auth가 아직 활성 상태입니다(모듈 10 수행자만 해당). 1단계 명령을 재실행합니다.

```bash
# 403은 Auto-heal 실패가 아니라 Easy Auth가 여전히 앞단에서 /api/info·/slow 요청을 막고 있다는 신호입니다.
az webapp auth update -g $RG -n $APP --enabled false
```

### (3) `az resource update` 오류 — 규칙이 적용되지 않음

`--set` 인자의 JSON 이스케이프 오류일 가능성이 있습니다. 적용된 구성을 확인하고, `slowRequests`가 `null`이면 명령을 다시 실행합니다.

```bash
az webapp config show -g $RG -n $APP --query "{enabled:autoHealEnabled}" -o json
az resource show -g $RG --resource-type "Microsoft.Web/sites/config" \
  --name "$APP/config/web" --query "properties.autoHealRules" -o json
```

> ⚠️ `az webapp config set --generic-configurations`로 중첩 JSON을 전달하는 방식은 `slowRequests` 트리거가 무시되는 문제가 있으므로 사용하지 않습니다(2단계 참고).

### (4) `jq: error` 또는 started_at 필드 없음

`/api/info` 응답 구조를 확인합니다.

```bash
curl -s $APP_URL/api/info | jq
```

`started_at` 키가 없으면 앱이 아직 기동 중이거나 엔드포인트 경로가 다를 수 있습니다. 30초 후 재시도합니다.

---

이전 모듈: [11. Redis 사이드카(선택)](11-sidecar-option.md) · 다음 모듈: [13. 정리](13-cleanup.md)
