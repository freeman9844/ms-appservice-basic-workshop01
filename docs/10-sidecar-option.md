# 10. (선택) Redis 사이드카 컨테이너

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요)

> ⚠️ **(선택) 모듈 — 건너뛰어도 12 정리에 지장 없음.** 이 모듈을 건너뛰려면 [12. 정리](12-cleanup.md)로 직접 이동하십시오.

---

## 목표

이 모듈에서는 App Service **sitecontainers** 기능을 사용하여 기존 코드 기반(code-based) 앱에 Redis 사이드카 컨테이너를 부착합니다. 앱 코드는 변경하지 않고, 플랫폼이 같은 앱 인스턴스 안에서 Redis 컨테이너를 함께 실행합니다.

- `/cache` 엔드포인트로 사이드카 부착 전후 동작 차이를 확인합니다.
- `az webapp sitecontainers create` 명령으로 Redis 사이드카를 부착합니다.
- 사이드카 개념(localhost 공유, 활용 예)과 Azure Container Apps(ACA) 대응 패턴을 이해합니다.
- 모듈 종료 상태: **Redis 사이드카 부착·`/cache` 동작 중, Easy Auth 비활성**

---

## 소요 시간

약 8–12분

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

## 👁️ 사이드카 컨테이너 개념

사이드카(sidecar)는 주 앱 컨테이너와 **같은 앱 인스턴스 안**에서 실행되는 보조 컨테이너입니다. 주 앱과 네트워크 네임스페이스를 공유하므로 앱 코드에서 `localhost:<포트>`로 직접 접근합니다.

| 항목 | 설명 |
|---|---|
| **네트워크 공유** | 주 앱과 사이드카는 `localhost`를 공유 — 앱 코드는 `localhost:6379`만 알면 됨 |
| **코드 수정** | 앱 코드에 Redis 주소가 이미 `localhost:6379`로 설정되어 있으면 변경 불필요 |
| **주요 활용 예** | 캐시(Redis), 리버스 프록시(Nginx), AI 에이전트 사이드카 |
| **ACA 대응** | Azure Container Apps도 동일 패턴의 사이드카 지원 — 패턴이 이식 가능 |

> 👁️ 이 워크숍 앱의 `/cache` 엔드포인트는 `REDIS_HOST` 앱 설정 값을 사용하며 기본값은 `localhost`입니다. Redis가 없으면 `{"cache":"unavailable"}`을 반환하고, Redis가 정상 동작하면 방문 횟수(`visits`)를 증가시켜 반환합니다.

---

## 0단계 — Easy Auth 일시 비활성화

모듈 09에서 Easy Auth가 활성화된 상태입니다. curl로 `/cache` 엔드포인트를 테스트하려면 인증 게이트를 일시적으로 해제해야 합니다.

🟢 **실행**

```bash
# curl 검증을 위해 Easy Auth 일시 비활성화
az webapp auth update -g $RG -n $APP --enabled false
```

---

## 1단계 — 사이드카 부착 전 `/cache` 동작 확인

🟢 **실행** — Redis가 없는 상태에서 `/cache` 응답을 확인합니다.

```bash
# 사이드카 부착 전: /cache는 우아하게 실패
curl -s $APP_URL/cache | jq
```

📋 **예상 출력**

```json
{
  "cache": "unavailable",
  "hint": "Redis 사이드카가 없습니다. 모듈 10을 참고하세요.",
  "redis_host": "localhost"
}
```

> 👁️ Redis가 없으면 앱이 오류를 발생시키지 않고 `"cache": "unavailable"` JSON을 반환합니다. 이것이 **우아한 실패(graceful degradation)** 패턴입니다.

---

## 2단계 — Redis 사이드카 부착

🟢 **실행** — `az webapp sitecontainers create` 명령으로 MCR 미러 Redis 이미지를 사이드카로 부착하고 앱을 재시작합니다.

```bash
az webapp sitecontainers create -g $RG -n $APP --container-name redis \
  --image mcr.microsoft.com/mirror/docker/library/redis:7.2 --is-main false
az webapp restart -g $RG -n $APP
```

> 👁️ `--is-main false`는 이 컨테이너가 보조(사이드카) 컨테이너임을 지정합니다. `az webapp restart` 후 Redis 컨테이너와 앱 컨테이너가 함께 기동되기까지 **60초 내외** 소요됩니다.

> ⚠️ **`az webapp sitecontainers` 명령이 없는 경우** — `az version`을 확인하고 최신 버전으로 업그레이드하십시오. 업그레이드 후에도 명령이 없으면 트러블슈팅 섹션의 `az rest` 대체 경로를 참고하십시오.

🟢 **실행** — 사이드카 목록을 확인합니다.

```bash
az webapp sitecontainers list -g $RG -n $APP -o table
```

📋 **예상 출력**

```
Name    Image                                                      IsMain
------  ---------------------------------------------------------  --------
redis   mcr.microsoft.com/mirror/docker/library/redis:7.2         False
```

---

## 3단계 — 사이드카 동작 검증

🟢 **실행** — 60초 대기 후 `/cache`를 두 번 호출하여 `visits` 값이 단조 증가하는지 확인합니다.

```bash
# 60초 후
curl -s $APP_URL/cache | jq
curl -s $APP_URL/cache | jq   # visits 증가 확인
```

📋 **예상 출력 — 첫 번째 호출**

```json
{
  "cache": "ok",
  "redis_host": "localhost",
  "visits": 1
}
```

📋 **예상 출력 — 두 번째 호출**

```json
{
  "cache": "ok",
  "redis_host": "localhost",
  "visits": 2
}
```

> 👁️ `"cache": "ok"`는 Redis가 정상 동작 중임을 의미합니다. `visits` 값이 호출마다 증가하면 사이드카가 앱과 정상 통신하고 있는 것입니다.

---

## 4단계 — Easy Auth 재활성화 안내

> 👁️ Easy Auth를 다시 활성화하려면 아래 명령을 실행하십시오. **다음 모듈 11(선택)로 진행하는 경우 11 첫머리에서 다시 비활성화하므로 지금 재활성화를 생략해도 됩니다.**

```bash
az webapp auth update -g $RG -n $APP --enabled true
```

---

## 검증

| 확인 항목 | 기대 결과 |
|---|---|
| 부착 전 `curl $APP_URL/cache` | `"cache": "unavailable"` 반환 |
| `az webapp sitecontainers create` 완료 | 명령 오류 없이 JSON 출력 |
| `az webapp sitecontainers list` | `redis` 컨테이너 `IsMain=False`로 목록에 표시 |
| `az webapp restart` 후 60초 대기 | 앱 정상 응답 |
| 첫 번째 `curl $APP_URL/cache` | `"cache": "ok", "visits": 1` |
| 두 번째 `curl $APP_URL/cache` | `"cache": "ok", "visits": 2` (visits 단조 증가) |

---

## 트러블슈팅

### (1) 사이드카 부착 후 `/cache`가 계속 `unavailable` 반환

Redis 컨테이너가 아직 기동 중이거나 앱이 재시작 중입니다.

- `az webapp sitecontainers list`로 컨테이너 상태를 확인합니다.
- 60초를 더 기다린 뒤 재시도합니다.
- 계속 실패하면 `az webapp restart`를 다시 실행하고 대기합니다.

### (2) 이미지 pull 실패 또는 컨테이너 기동 오류

MCR 미러 이미지 경로 또는 태그가 잘못되었을 수 있습니다.

```bash
# 태그 목록 확인
curl -s https://mcr.microsoft.com/v2/mirror/docker/library/redis/tags/list | jq '.tags | .[-5:]'
```

태그를 확인한 뒤 올바른 태그로 사이드카를 다시 생성합니다.

### (3) `az webapp sitecontainers` 명령 없음

`az version`을 확인하고 Azure CLI를 최신 버전으로 업그레이드합니다.

```bash
az upgrade --only-show-errors
```

업그레이드 후에도 명령이 없으면 REST API로 직접 생성합니다.

```bash
az rest --method put \
  --url "https://management.azure.com/subscriptions/$(az account show --query id -o tsv)/resourceGroups/$RG/providers/Microsoft.Web/sites/$APP/sitecontainers/redis?api-version=2024-04-01" \
  --body '{"properties":{"image":"mcr.microsoft.com/mirror/docker/library/redis:7.2","isMain":false}}'
```

---

이전 모듈: [09. Easy Auth](09-easy-auth.md) | 다음 모듈: [11. Auto Heal(선택)](11-autoheal-option.md) 또는 [12. 정리](12-cleanup.md)
