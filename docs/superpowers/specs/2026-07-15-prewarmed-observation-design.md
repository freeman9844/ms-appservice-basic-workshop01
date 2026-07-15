# 07 모듈 Prewarmed 관찰 시나리오 설계

## 목적

`docs/07-autoscale.md`에서 Prewarmed 인스턴스가 단순 설정값이 아니라 HTTP 부하 증가 전에 준비되는 워밍 버퍼임을 짧고 반복 가능한 실습으로 보여준다.

## 시나리오

1. Automatic scaling을 활성화한 뒤 Azure Monitor의 `InstanceCount` 메트릭으로 유휴 기준값 `1`을 기록한다.
2. 60초간 낮은 HTTP 트래픽을 발생시켜 Always-ready 인스턴스를 활성화한다.
3. 메트릭 수집을 기다린 뒤 `InstanceCount=2`를 확인한다. 이 값은 활성 인스턴스와 할당된 Prewarmed 인스턴스를 포함한다.
4. 기존의 높은 부하를 발생시키고 여러 instance ID가 응답하는지 확인한다. 워밍 버퍼가 활성 인스턴스로 전환되고 다음 버퍼가 준비되는 흐름으로 설명한다.
5. 부하 종료 후 기존 scale-in 관찰을 수행한다.

## 명령과 관찰 기준

- 메트릭 리소스: production Web App의 `$APP_ID`
- 메트릭 이름: `InstanceCount`
- 표시 이름: `Automatic Scaling Instance Count`
- 집계: `Maximum`
- 간격: `PT1M`
- 기준 상태: 유휴 시 `1`
- Prewarmed 할당 상태: 낮은 트래픽 이후 `2` 이상
- 활성화 상태: 높은 부하 중 응답에서 두 개 이상의 instance ID 관찰

메트릭 적재에는 지연이 있을 수 있으므로 고정된 즉시 조회 대신 최대 3분 동안 30초 간격으로 재조회한다. 제한 시간 안에 값이 나타나지 않으면 설정 조회와 Portal 메트릭 확인 경로를 안내하고, 성공으로 가장하지 않는다.

## 문서 구조 변경

- 2단계의 `hey` 설치는 유지한다.
- 새 3단계에 유휴 기준값과 낮은 트래픽 기반 Prewarmed 할당 관찰을 추가한다.
- 기존 scale-out 관찰은 4단계로 이동하여 Prewarmed 활성화 의미를 연결한다.
- 기존 scale-in 관찰은 5단계로 이동한다.
- 검증 및 트러블슈팅에 `InstanceCount` 메트릭 지연과 미표시 대응을 추가한다.

## 리허설 변경

`scripts/rehearsal.sh`에서도 낮은 트래픽을 먼저 발생시키고 `InstanceCount`를 조회한다. 리허설은 메트릭 적재 지연 때문에 실패로 중단하지 않고 실제 값을 출력하되, 높은 부하에서 두 개 이상의 인스턴스를 확인하는 기존 검증은 유지한다.

## 시간과 비용

낮은 트래픽 60초와 메트릭 적재 대기 최대 3분이 추가된다. Prewarmed 인스턴스가 할당되는 동안 추가 인스턴스 비용이 초 단위로 발생하지만 워크숍 전체 비용 영향은 미미하다.

## 범위 제외

- Prewarmed 0과 1의 응답시간 A/B 비교
- Portal 스크린샷 추가
- 애플리케이션 코드 또는 테스트 변경
- Maximum scale limit 변경
