# 07. 자동 스케일(Automatic Scaling · 부하 확장/축소)

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

---

## 목표

이 모듈에서는 Azure App Service **Automatic scaling**(탄력 스케일)을 활성화하고, `hey` 부하 도구로 인위적인 HTTP 트래픽을 발생시켜 인스턴스가 수평 확장(scale-out)되는 과정을 관찰한 뒤, 부하를 제거하여 축소(scale-in)까지 확인합니다.

- App Service 플랜을 Elastic scale 모드로 전환하고 최대 5 인스턴스로 설정합니다.
- `hey`로 120초 동안 HTTP 부하를 생성합니다.
- `list-instances` 와 인스턴스별 응답 분포로 확장을 검증합니다.
- 부하 종료 후 인스턴스가 1개로 축소됨을 확인합니다.
- **Automatic scaling** 방식과 **규칙 기반(Azure Monitor autoscale)** 방식의 개념 차이를 이해합니다.
- 모듈 종료 상태: **Automatic scaling 활성(min 1·max 5), prod = v2** (이후 모듈에서 이 상태가 유지됩니다).

## 소요 시간

약 15–20분

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

## 👁️ Automatic scaling vs 규칙 기반 — 개념 비교

Azure App Service에서 수평 스케일(인스턴스 수 조정)을 구현하는 방법은 두 가지입니다.

| 비교 항목 | **Automatic scaling** | **규칙 기반(Azure Monitor autoscale)** |
|---|---|---|
| 플랜 요건 | **Premium v3(Pv3) 전용** | Standard 이상 |
| 스케일 트리거 | **HTTP 요청 부하** — 플랫폼이 자동 판단 | CPU·메모리·큐 길이 등 **메트릭 + 직접 규칙** |
| 설정 복잡도 | 최솟값·최댓값만 지정 | 규칙(임계값·방향·증감량·쿨다운) 직접 작성 |
| 관리 주체 | **플랫폼 완전 관리** | 운영자가 규칙 유지·보수 |
| 콜드스타트 방지 | `prewarmed-instance-count`로 **웜 인스턴스 상시 대기** | 스케일아웃 후 새 인스턴스 워밍 시간 존재 |
| ACA 대응 | ACA **HTTP 스케일링**(KEDA HTTP Add-on) | ACA **사용자 정의 KEDA 스케일러** |

> 👁️ `prewarmed-instance-count`는 플랫폼이 미리 워밍해 두는 대기 인스턴스 수입니다. 확장 요청이 발생하면 이미 준비된 인스턴스가 즉시 투입되므로 콜드스타트 지연 없이 빠르게 처리 용량을 늘릴 수 있습니다.

---

## 1단계 — Automatic scaling 활성화

> 👁️ **진입 상태** — production = v2(초록 `#16a34a`), staging = v1(파랑 `#2563eb`), 라우팅 0%. 이 상태는 06 모듈에서 만들어졌습니다.

🟢 **실행** — App Service 플랜을 Elastic scale 모드로 전환하고 웹앱의 최솟값을 설정합니다.

```bash
az appservice plan update -g $RG -n $PLAN --elastic-scale true --max-elastic-worker-count 5
az webapp update -g $RG -n $APP --prewarmed-instance-count 1 --minimum-elastic-instance-count 1
```

> 👁️ `--elastic-scale true`는 플랜을 Automatic scaling 모드로 전환합니다. `--max-elastic-worker-count 5`는 이 플랜에서 허용할 최대 인스턴스 수입니다. `--minimum-elastic-instance-count 1`은 항상 유지할 최솟값이며, `--prewarmed-instance-count 1`은 추가로 대기시킬 워밍 인스턴스 수입니다.

---

## 2단계 — hey 부하 도구 설치

> 👁️ Cloud Shell은 `sudo`가 차단되어 있으므로 시스템 디렉터리에 바이너리를 설치할 수 없습니다. `$HOME/.local/bin`을 사용합니다.

🟢 **실행**

```bash
mkdir -p $HOME/.local/bin && export PATH=$HOME/.local/bin:$PATH
curl -sL https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -o $HOME/.local/bin/hey
chmod +x $HOME/.local/bin/hey
```

설치가 완료되면 실행 가능한지 확인합니다(`hey`는 `--version` 플래그가 없으므로 도움말 출력으로 확인).

```bash
hey 2>&1 | head -1
```

📋 **예상 출력**

```
Usage: hey [options...] <url>
```

---

## 3단계 — 부하 생성 및 확장(scale-out) 관찰

🟢 **실행** — `hey`를 백그라운드로 실행하여 120초 동안 동시 100 연결로 HTTP 부하를 발생시킵니다.

```bash
hey -z 120s -c 100 -q 10 $APP_URL/api/info &
```

> 👁️ `-z 120s`는 지속 시간, `-c 100`은 동시 연결 수, `-q 10`은 초당 요청 상한, `&`는 백그라운드 실행입니다. 부하가 진행되는 동안 다음 명령으로 인스턴스 상태를 확인합니다.

🟢 **실행** — 부하 시작 후 60–90초가 지난 뒤 인스턴스 목록을 조회합니다.

```bash
# 부하 진행 중(60–90초 후) 인스턴스 확인
az webapp list-instances -g $RG -n $APP -o table
for i in $(seq 1 50); do curl -s $APP_URL/api/info | jq -r .instance; done | sort | uniq -c
```

📋 **예상 출력** (`list-instances` — 2행 이상)

```
Name                                    State    StatusCode
--------------------------------------  -------  ------------
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx    Ready    200
yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy    Ready    200
```

📋 **예상 출력** (인스턴스 분포 — 2종 이상)

```
     28 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
     22 yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy
```

> 👁️ 두 가지 인스턴스 ID가 혼합되어 나타나면 요청이 여러 인스턴스로 분산되고 있음을 의미합니다. 플랫폼이 HTTP 부하를 감지하여 인스턴스를 추가로 투입한 결과입니다.

---

## 4단계 — 부하 제거 및 축소(scale-in) 관찰

> 👁️ **부하가 남아 있으면 플랫폼이 축소를 결정하지 않습니다.** 반드시 `wait`으로 `hey` 프로세스가 종료된 것을 확인한 뒤 대기합니다.

🟢 **실행**

```bash
wait   # hey 종료 대기(-z 120s 경과)
# 수 분 후
az webapp list-instances -g $RG -n $APP -o table   # 1개로 축소
```

📋 **예상 출력** (축소 완료 후)

```
Name                                    State    StatusCode
--------------------------------------  -------  ------------
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx    Ready    200
```

> 👁️ 축소는 확장보다 느립니다. 플랫폼이 트래픽 감소를 일정 시간 관찰한 후 인스턴스를 회수하므로, `wait` 이후 3–5분이 소요될 수 있습니다.

---

## 검증

| 확인 항목 | 기대 결과 |
|---|---|
| `elastic-scale` 설정 후 플랜 상태 | 명령 오류 없이 완료 |
| `hey` 설치 후 `hey --version` | 버전 문자열 출력 |
| 부하 중 `list-instances` 행 수 | 2행 이상 |
| 인스턴스별 응답 분포(50회 curl) | 2종 이상의 인스턴스 ID 혼합 |
| 부하 제거 후 `list-instances` 행 수 | 1행(단일 인스턴스) |

---

## 트러블슈팅

### (1) 확장이 일어나지 않음

`-c` 값을 높여 동시 연결 수를 늘려 보십시오(예: `-c 200`). 또한 플랜에 Elastic scale이 정상 활성화되었는지 확인합니다.

```bash
az appservice plan show -g $RG -n $PLAN --query "properties.elasticScaleEnabled" -o tsv
```

값이 `true`가 아닌 경우 1단계 명령을 재실행합니다.

### (2) 축소가 일어나지 않음

백그라운드에 `hey` 프로세스가 잔존하는 경우 플랫폼이 부하가 지속된다고 판단하여 축소하지 않습니다. `jobs` 명령으로 잔존 프로세스를 확인하고 종료합니다.

```bash
jobs
# 잔존 프로세스가 있으면
kill %1
```

### (3) hey 설치 실패

네트워크 일시 장애일 수 있습니다. 동일한 `curl` 명령을 재시도합니다.

```bash
curl -sL https://hey-release.s3.us-east-2.amazonaws.com/hey_linux_amd64 -o $HOME/.local/bin/hey
chmod +x $HOME/.local/bin/hey
```

---

이전 모듈: [06. 트래픽 분할 · 카나리 배포 · 승격](06-traffic-split-canary.md) | 다음 모듈: [08. 관찰 가능성](08-observability.md)
