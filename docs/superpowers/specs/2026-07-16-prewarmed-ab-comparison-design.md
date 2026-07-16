# 07 모듈 Prewarmed A/B 비교 설계

## 목적

현재 `InstanceCount` 관찰만으로는 추가 인스턴스가 Prewarmed 버퍼인지 활성 인스턴스인지 직접 구분하기 어렵다. 같은 앱과 같은 부하에서 Prewarmed를 0과 1로 바꾸어 두 번째 활성 인스턴스가 실제 응답하기까지 걸린 시간을 비교한다.

## 핵심 원리

App Service는 앱이 유휴 상태이고 Always-ready 인스턴스가 사용되지 않을 때 Prewarmed 인스턴스를 할당하지 않는다. 따라서 Prewarmed=1 시험도 유휴 상태에서 바로 순간 부하를 주면 버퍼의 장점을 안정적으로 보여주기 어렵다.

두 시험 모두 먼저 60초간 낮은 트래픽을 보낸다.

- Prewarmed=0: Always-ready 인스턴스만 활성화되고 버퍼는 준비되지 않는다.
- Prewarmed=1: Always-ready 인스턴스가 활성화되면서 Prewarmed 버퍼가 할당되고 워밍된다.

이후 동일한 순간 부하를 보내 두 번째 고유 instance ID가 처음 응답할 때까지 시간을 측정한다.

## 시작 지연 시뮬레이션

`app/app.py`에 `STARTUP_DELAY_SECONDS` 환경변수를 추가한다. 앱 프로세스 시작 시 0–30초 범위로 제한한 지연을 한 번 적용한다.

워크숍에서는 값을 `20`으로 설정한다.

- Prewarmed=0: 새 인스턴스가 scale-out 결정 후 시작되므로 20초 지연이 관찰 시간에 포함된다.
- Prewarmed=1: 낮은 트래픽 단계에서 버퍼가 이미 시작되어 지연을 통과하므로 활성 전환 시간이 짧아진다.

설정이 없거나 0이면 기존 동작과 성능을 유지한다. 숫자가 아니거나 범위를 벗어난 값은 기존 `_clamp` 규칙으로 안전하게 0–30초로 제한한다.

## 실습 흐름

### 준비

1. Automatic scaling, Maximum burst=5, Always-ready=1을 설정한다.
2. `STARTUP_DELAY_SECONDS=20` 앱 설정을 추가한다.
3. 앱 재시작과 `/health` 정상 응답을 기다린다.

### 시험 A: Prewarmed=0

1. `preWarmedInstanceCount=0`으로 설정한다.
2. `InstanceCount=1`이 될 때까지 최대 10분 기다린다.
3. 60초간 낮은 트래픽을 보낸다.
4. 180초간 높은 부하를 백그라운드에서 시작한다.
5. 5초 간격으로 `/api/info`를 30회 요청해 고유 instance ID 수를 구한다.
6. 두 개 이상의 ID가 처음 나타난 시간을 `NO_PREWARM_SECONDS`로 기록한다.
7. 제한 시간 안에 나타나지 않으면 `timeout`으로 기록한다.
8. 높은 부하 프로세스를 종료한다.

### 중간 복원

`InstanceCount=1`이 될 때까지 최대 10분 기다린다. 제한 시간 안에 축소되지 않으면 시험 B를 진행하지 않고 원인을 안내한다. 이전 활성 인스턴스가 남아 있으면 비교가 무효이기 때문이다.

### 시험 B: Prewarmed=1

1. `preWarmedInstanceCount=1`로 설정한다.
2. 60초간 동일한 낮은 트래픽을 보낸다.
3. `InstanceCount>=2`를 확인해 버퍼 할당을 보조 검증한다.
4. 시험 A와 동일한 높은 부하와 instance ID 샘플링을 수행한다.
5. 두 번째 ID가 처음 나타난 시간을 `PREWARM_SECONDS`로 기록한다.

### 결과와 정리

두 값이 모두 측정되면 다음 형태로 출력한다.

```text
Prewarmed=0 : 35초
Prewarmed=1 : 10초
개선         : 25초
```

결과는 플랫폼 부하 판단과 요청 샘플링에 따라 달라질 수 있으며 Prewarmed=1이 항상 특정 초만큼 빠르다고 보장하지 않는다. 한 시험이 timeout이면 결과를 성공으로 해석하지 않는다.

마지막에는:

1. Prewarmed를 1로 복원한다.
2. `STARTUP_DELAY_SECONDS` 앱 설정을 삭제한다.
3. 앱 정상 응답을 확인한다.

## 측정 함수

문서와 리허설 스크립트는 같은 논리를 사용한다.

- 입력: 결과 변수명, 출력 파일 경로
- 부하: `hey -z 180s -c 100 -q 10`
- 샘플링: 5초마다 `/api/info` 30회
- 성공 조건: 고유 instance ID 2개 이상
- 제한 시간: 180초
- 프로세스 정리: 해당 시험에서 시작한 PID만 `kill` 후 `wait`

리허설 스크립트에서는 중복을 줄이기 위해 Bash 함수로 구현한다. 문서에는 학습자가 흐름을 이해할 수 있도록 동일 함수와 호출 방법을 제시한다.

## 테스트

### 앱 테스트

- 설정이 없으면 `time.sleep`을 호출하지 않는다.
- `STARTUP_DELAY_SECONDS=20`이면 `time.sleep(20)`을 한 번 호출한다.
- 음수, 30 초과, 숫자가 아닌 값이 0–30 범위로 처리되는 기존 `_clamp` 동작을 검증한다.

테스트가 import 시 실제로 대기하지 않도록 지연 계산과 실행을 작은 함수로 분리하고 `time.sleep`을 monkeypatch한다.

### 문서·스크립트 검증

- Markdown 코드 펜스 균형
- `bash -n scripts/rehearsal.sh`
- A/B 결과 변수와 정리 명령 존재 여부
- 기존 애플리케이션 테스트 전체 통과

Azure 리소스에 실제 A/B 부하를 실행하는 것은 구현 검증 범위에서 제외하고 워크숍 리허설에서 수행한다.

## 시간과 비용

- 두 번의 낮은 트래픽: 2분
- 두 번의 높은 부하: 최대 6분
- 시험 사이 scale-in: 보통 5–10분
- 설정 변경과 재시작: 약 1–2분

07 모듈 예상 시간은 약 25–35분으로 조정한다. 추가 인스턴스가 실행되는 동안 초 단위 비용이 발생한다.

## 변경 파일

- `app/app.py`
- `app/tests/test_app.py`
- `docs/07-autoscale.md`
- `scripts/rehearsal.sh`
- `README.md`

## 범위 제외

- 비교용 Web App 추가 생성
- 배포 슬롯 트래픽 사용
- Portal 스크린샷 추가
- 통계적으로 유의한 반복 실험
- 특정 개선 시간 보장
