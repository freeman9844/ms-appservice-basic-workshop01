# Prewarmed 인스턴스 나이 관찰 설계

## 배경

기존 07 모듈은 `Prewarmed=0`과 `Prewarmed=1`에서 두 번째 응답 인스턴스가 나타날 때까지 걸린 시간을 한 번씩 비교했다. 실제 P0v4 리허설에서는 다음 결과가 나왔다.

- `Prewarmed=0`: 46초
- `Prewarmed=1`: 73초

또한 `Prewarmed=1` 시험 전에 버퍼 할당을 확인하려던 `InstanceCount >= 2` 게이트는 10분 동안 충족되지 않았다. 빠른 `/api/info` 요청을 20 RPS로 2분간 보낸 경우에도 `InstanceCount=1`이 유지됐다. 반대로 느린 요청을 동시성 2 이상으로 보내면 `InstanceCount`가 1에서 5로 바로 증가했다.

이 결과는 단일 scale-out 시간의 우열이 플랫폼의 부하 판단, 용량 할당, 메트릭 지연에 크게 좌우되며, 낮은 부하와 실제 scale-out 사이에 안정적인 “버퍼만 할당된 상태”를 만들기 어렵다는 점을 보여준다. 따라서 워크숍의 성공 기준을 “Prewarmed=1이 한 번의 시험에서 반드시 더 빠름”에서 “인스턴스가 시작된 뒤 실제 응답에 투입되는 과정을 직접 관찰”로 변경한다.

## 목표

- Prewarmed 동작을 단일 지연 수치가 아니라 인스턴스별 시작·투입 타임라인으로 보여준다.
- 플랫폼 변동 때문에 B가 A보다 느려도 실습 자체가 실패하지 않게 한다.
- 관찰 결과로 확인할 수 있는 사실과 추론할 수 없는 사실을 명확히 구분한다.
- 시험이 성공하거나 중단되더라도 `Prewarmed=1`, `Always-ready=1`, 시작 지연 설정 삭제 상태로 복원한다.

## 비목표

- 단일 실행에서 `Prewarmed=1`이 반드시 더 빠르다고 증명하지 않는다.
- 특정 RPS가 모든 구독·리전·시점에서 같은 instance 수를 만든다고 가정하지 않는다.
- `InstanceCount`만으로 active와 prewarmed 상태를 구분하지 않는다.
- 여러 회 반복 결과의 평균·중앙값으로 통계적 우위를 주장하지 않는다.

## 핵심 관찰값

앱의 `/api/info`는 다음 값을 반환한다.

- `instance`: 응답한 App Service instance ID
- `started_at`: Python 프로세스가 시작된 시각

`STARTED_AT`은 `STARTUP_DELAY_SECONDS`가 적용되기 전에 기록된다. 따라서 새 instance를 처음 관찰한 시각을 `first_seen_at`이라고 하면 다음 값을 계산할 수 있다.

```text
first_response_age = first_seen_at - started_at
```

`STARTUP_DELAY_SECONDS=20`인 시험에서:

- 약 20초에 가까운 나이는 instance가 시작 지연을 마친 직후 트래픽에 투입됐음을 뜻한다.
- 20초보다 의미 있게 긴 나이는 instance가 시작 준비를 마친 뒤 실제 응답에 투입되기 전까지 대기했음을 뜻한다.
- 이 추가 대기 시간은 Prewarmed 버퍼 체류와 일치하는 관찰 증거가 될 수 있지만, 플랫폼 내부 상태를 직접 노출하는 값은 아니므로 확정적인 내부 상태 라벨로 표현하지 않는다.

## 시험 흐름

### 공통 준비

1. Automatic scaling, Maximum burst 5, Always-ready 1을 확인한다.
2. `STARTUP_DELAY_SECONDS=20`을 설정하고 `/health`가 정상화될 때까지 기다린다.
3. `InstanceCount`의 전환 시각 이후 값이 2회 연속 1인지 확인한다.
4. 기준 instance ID를 한 개 기록한다.

### 시험 A: Prewarmed=0

1. `preWarmedInstanceCount=0`으로 변경한다.
2. 변경 시각 이후 `InstanceCount=1`이 2회 연속 확인될 때까지 기다린다.
3. 기존 burst 부하를 시작한다.
4. `/api/info`를 제한 시간 안에서 반복 호출한다.
5. 기준 ID를 제외한 각 새 ID에 대해 다음 값을 최초 한 번 기록한다.
   - instance ID
   - `started_at`
   - `first_seen_at`
   - `first_response_age`
6. 최소 한 개의 새 instance를 관찰하거나 180초가 지나면 시험을 종료한다.

### 시험 사이

1. 부하 프로세스가 종료됐는지 확인한다.
2. 새 전환 시각 이후 `InstanceCount=1`이 2회 연속 확인될 때까지 기다린다.
3. 시작 지연 설정은 유지한다.

### 시험 B: Prewarmed=1

1. `preWarmedInstanceCount=1`로 변경한다.
2. 변경 시각 이후 `InstanceCount=1`이 2회 연속 확인될 때까지 기다린다.
3. 별도의 prime 부하나 `InstanceCount>=2` 사전 게이트 없이 A와 같은 burst를 시작한다.
4. A와 같은 방식으로 모든 새 instance의 최초 응답 나이를 기록한다.
5. 최소 한 개의 새 instance를 관찰하거나 180초가 지나면 시험을 종료한다.

## 결과 표시와 해석

결과는 승패가 아니라 다음 표로 표시한다.

| 시험 | instance | started_at | first_seen_at | first_response_age |
|---|---|---|---|---:|
| Prewarmed=0 | `<id>` | `<UTC>` | `<UTC>` | `<seconds>` |
| Prewarmed=1 | `<id>` | `<UTC>` | `<UTC>` | `<seconds>` |

해석 규칙:

- B에서 20초보다 추가로 오래 대기한 새 instance가 관찰되면 “시작 준비 후 실제 응답 투입 전 대기 구간이 관찰됐다”고 설명한다.
- A와 B의 나이가 비슷하면 “이번 실행에서는 버퍼 체류 차이가 관찰되지 않았고 플랫폼이 준비된 instance를 곧바로 활성화했을 수 있다”고 설명한다.
- B가 A보다 빠르거나 느린지만으로 Prewarmed 효과를 단정하지 않는다.
- 새 instance가 하나도 관찰되지 않으면 부하가 scale-out을 유도하지 못한 것으로 보고 결과를 계산하지 않는다. 설정을 복원한 뒤 재시도 안내를 표시한다.

## 오류 처리와 복원

- Azure PATCH, 앱 설정 변경, health 확인, 기준 상태 확인 중 하나라도 실패하면 이후 시험을 실행하지 않는다.
- sampler는 실패한 HTTP 응답, 빈 값, 문자열이 아닌 instance ID를 무시한다.
- 각 curl은 남은 전체 제한 시간보다 긴 timeout을 사용하지 않는다.
- burst 프로세스는 추적하고 정상·비정상 종료 모두에서 정리한다.
- 종료 시 다음을 모두 수행하고 검증한다.
  - `minimumElasticInstanceCount=1`
  - `preWarmedInstanceCount=1`
  - `STARTUP_DELAY_SECONDS` 삭제
  - `/health` 정상
- 복원 검증이 실패하면 성공 메시지를 출력하지 않고 nonzero로 종료한다.

## 문서 변경

`docs/07-autoscale.md`에서 다음을 교체한다.

- 두 번째 ID까지 걸린 시간의 A/B 우열 비교
- B 시험 전 `InstanceCount>=2` 버퍼 게이트
- `Prewarmed=1`이 더 빨라야 한다는 예상 결과

대신 다음을 추가한다.

- `started_at`, `first_seen_at`, `first_response_age`의 의미
- 인스턴스별 결과 표
- 관찰됨·관찰되지 않음 양쪽 모두에 대한 해석
- 플랫폼 내부 상태를 직접 측정하는 것이 아니라는 제한

`scripts/rehearsal.sh`도 동일한 데이터 수집·표시·복원 흐름을 사용한다.

## 검증

- 앱 단위 테스트는 기존 시작 지연 기본값, 설정값, 상한 동작을 계속 검증한다.
- shell 정적 검증:
  - `bash -n scripts/rehearsal.sh`
  - `git diff --check`
  - Markdown fence 검사
- sampler의 시간 계산과 유효 ID 필터는 로컬 fixture 입력으로 검증한다.
- 실제 Azure 리허설에서는 다음을 확인한다.
  - 두 시험 모두 기준 상태 이후 시작
  - 새 instance별 타임라인 출력
  - A/B 우열과 무관하게 해석 문구 출력
  - 종료 후 설정과 health 복원

## 완료 기준

- 실습이 단일 지연 수치의 승패를 요구하지 않는다.
- A와 B의 새 instance별 시작·최초 응답 나이가 표시된다.
- 결과가 기대와 다를 때도 사실에 맞는 설명을 제공한다.
- 실제 Azure 리허설이 끝난 뒤 원래 설정이 검증된 상태로 복원된다.
