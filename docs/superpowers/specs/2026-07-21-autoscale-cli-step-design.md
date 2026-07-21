# Automatic Scaling 1단계 CLI 단순화 설계

## 목표

`docs/07-autoscale.md`의 1단계를 Cloud Shell 사용자가 함수 구조를 이해하지 않아도 순서대로 복사해 실행할 수 있는 Azure CLI 명령 형태로 단순화한다.

## 제약

- Premium V4를 지원하지 않는 Azure CLI 2.87.0의 이전 SKU 검증 문제 때문에 `az appservice plan update --elastic-scale`과 `az webapp update --prewarmed-instance-count`를 사용하지 않는다.
- 설정은 기존과 동일하게 ARM API `2024-11-01`을 호출하는 `az rest`로 수행한다.
- Plan PATCH가 실패하면 Web App PATCH를 실행하지 않아야 한다.
- Automatic scaling=true, Maximum burst=5, Always-ready=1, Prewarmed=1 설정값은 변경하지 않는다.
- 자동 리허설의 상세 오류 처리와 read-back 검증은 유지한다.

## 1단계 명령 구조

1. `PLAN_ID`와 `APP_ID`를 `az appservice plan show`, `az webapp show`로 조회한다.
2. Plan PATCH와 Web App PATCH를 `&&`로 연결한다.
3. 두 PATCH가 성공하면 완료 메시지를 출력한다.
4. 별도 조회 블록에서 Plan과 Web App 설정을 즉시 표시한다.
5. 명령 오류가 출력되면 다음 단계로 진행하지 않고 1단계를 다시 확인하도록 안내한다.

```bash
PLAN_ID=$(az appservice plan show -g $RG -n $PLAN --query id -o tsv)
APP_ID=$(az webapp show -g $RG -n $APP --query id -o tsv)

az rest --method patch \
  --uri "${PLAN_ID}?api-version=2024-11-01" \
  --body '{"sku":{"name":"P0v4","tier":"PremiumV4","size":"P0v4","family":"Pv4","capacity":1},"properties":{"elasticScaleEnabled":true,"maximumElasticWorkerCount":5}}' \
  --output none &&
az rest --method patch \
  --uri "${APP_ID}/config/web?api-version=2024-11-01" \
  --body '{"properties":{"minimumElasticInstanceCount":1,"preWarmedInstanceCount":1}}' \
  --output none &&
echo "Automatic scaling 설정 완료"
```

## Helper 이동

현재 1단계에 있는 다음 함수는 A/B 시험에서 재사용되므로 삭제하지 않고 3단계의 helper 정의 영역으로 이동한다.

- `verify_plan_configuration`
- `set_prewarmed_configuration`

1단계는 직접 실행 명령만 보여주고, 3단계는 복원·시험 실패 처리에 필요한 함수형 검증을 계속 사용한다.

## 변경 범위

- 수정: `docs/07-autoscale.md`
- 변경 없음: `scripts/rehearsal.sh`
- 변경 없음: 앱 코드와 테스트

## 검증

- Markdown 코드 fence가 균형을 유지한다.
- 1단계의 Plan PATCH와 Web App PATCH가 `&&`로 연결되어 있다.
- helper 함수는 1단계에는 없고 3단계에서 사용 전에 정의된다.
- `scripts/rehearsal.sh` Bash 구문 검사가 통과한다.
- `git diff --check`가 통과한다.
