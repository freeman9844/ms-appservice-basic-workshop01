# 02. 환경 준비

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **예상 화면** = 브라우저/포털 스크린샷 참고

---

## 목표

이 모듈에서는 워크숍 전반에 걸쳐 사용할 Azure 리소스를 생성합니다.

- 환경 변수(`SUFFIX`, `RG`, `PLAN`, `APP`, `LAW`, `APPI`)를 정의합니다.
- **리소스 그룹**, **App Service Plan(P0v3)**, **Web App(Python 3.12)** 을 프로비저닝합니다.
- **Log Analytics Workspace** 와 **Application Insights 컴포넌트** 를 연결합니다.
- 기본 호스트네임(`APP_URL`)을 조회하여 앱 엔드포인트를 확인합니다.

---

## 1단계 — 환경 변수 정의 및 리소스 생성

`SUFFIX`는 여러 참가자의 리소스 이름이 겹치지 않도록 구분하는 값입니다. 원하는 **5자리 숫자**를 직접 입력하고 이후 모듈에서 다시 사용할 수 있도록 메모해 두세요.

예를 들어 `04271`을 사용하려면 `SUFFIX="04271"`로 입력합니다. 앱 이름이 이미 사용 중이라는 오류가 발생하면 다른 숫자로 변경하여 다시 실행하세요.

🟢 **실행**

```bash
SUFFIX="04271"   # 예시: 원하는 5자리 숫자로 변경
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
echo "SUFFIX=$SUFFIX"   # ⚠️ 이후 모듈에서 재사용

# 1. 모든 워크숍 리소스를 담을 리소스 그룹 생성
az group create -n $RG -l $LOC

# 2. Linux 기반 Premium V3 App Service Plan 생성
#    P0V3는 배포 슬롯·자동 스케일·사이드카 실습에 필요한 컴퓨트 환경
az appservice plan create -g $RG -n $PLAN --is-linux --sku P0V3

# 3. 위 Plan에 Python 3.12 런타임을 사용하는 Web App 생성
az webapp create -g $RG -n $APP --plan $PLAN --runtime "PYTHON:3.12"

# 4. App Service 로그와 메트릭을 수집할 Log Analytics Workspace 생성
az monitor log-analytics workspace create -g $RG -n $LAW -l $LOC

# 5. Application Insights 연결에 사용할 Workspace 리소스 ID 조회
#    명령 결과를 LAW_ID 셸 변수에 저장
LAW_ID=$(az monitor log-analytics workspace show -g $RG -n $LAW --query id -o tsv)

# 6. Application Insights 관리 명령을 제공하는 CLI 확장 설치·업그레이드
az extension add --name application-insights --upgrade --only-show-errors

# 7. Log Analytics Workspace와 연결된 Application Insights 컴포넌트 생성
az monitor app-insights component create -g $RG --app $APPI -l $LOC --workspace $LAW_ID

# 8. Web App의 Azure 기본 호스트 이름을 조회해 HTTPS 접속 URL 구성
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"

# 9. 브라우저와 이후 모듈에서 사용할 앱 URL 출력
echo $APP_URL
```

---

> 👁️ **개념 — Plan(컴퓨트) vs Web App(앱) 분리**
>
> **App Service Plan** 은 VM 인스턴스(CPU·메모리·OS)를 정의하는 **컴퓨트 레이어** 입니다.
> **Web App** 은 그 Plan 위에서 실행되는 **논리적 앱 단위** 이며, 하나의 Plan에 여러 Web App을 올릴 수 있습니다.
>
> 이번 워크숍에서 **P0v3** SKU를 선택한 이유:
> - **배포 슬롯**(스테이징/프로덕션 스왑)은 Standard 계층 이상에서만 지원됩니다.
> - **Automatic scaling**(자동 스케일링) 및 **사이드카 컨테이너** 기능은 Premium V3 이상에서 활성화됩니다.
> - P0v3는 Premium V3의 최소 사이즈로 위 기능을 가장 경제적으로 체험할 수 있습니다.
>
> **기본 도메인**(`defaultHostName`)은 Web App 생성 시 Azure가 전역 고유 이름으로 자동 할당합니다.
> 직접 입력하지 않고 반드시 `az webapp show … --query defaultHostName` 조회로 가져오십시오.

---

📋 **예상 출력 — `az appservice plan create`**

```text
{
  "id": "/subscriptions/.../resourceGroups/rg-appsvcworkshop-XXXXX/providers/Microsoft.Web/serverfarms/plan-appsvcworkshop-XXXXX",
  "kind": "linux",
  "name": "plan-appsvcworkshop-XXXXX",
  "provisioningState": "Succeeded",
  "sku": {
    "name": "P0V3",
    "tier": "PremiumV3"
  },
  ...
}
```

📋 **예상 출력 — `az webapp create`**

```text
{
  "defaultHostName": "app-appsvcworkshop-XXXXX.azurewebsites.net",
  "name": "app-appsvcworkshop-XXXXX",
  "provisioningState": "Succeeded",
  "state": "Running",
  ...
}
```

📋 **예상 출력 — `echo $APP_URL`**

```text
https://app-appsvcworkshop-XXXXX.azurewebsites.net
```

---

## 검증

🟢 **실행**

```bash
az webapp show -g $RG -n $APP --query state -o tsv
```

📋 **예상 출력**

```text
Running
```

👁️ **브라우저 확인** — `$APP_URL` 값을 브라우저 주소창에 붙여넣어 Azure App Service 기본 자리표시 페이지가 열리는지 확인합니다. 아직 애플리케이션 코드를 배포하지 않은 상태이므로 기본 페이지가 표시됩니다.

🖼️ **예상 화면** — App Service 기본 자리표시 페이지

---

## 트러블슈팅

### (1) 앱 이름 전역 중복 오류

Web App 이름(`$APP`)은 `azurewebsites.net` 도메인에서 **전 세계적으로 고유** 해야 합니다.
`The app name 'app-appsvcworkshop-XXXXX' is not available` 오류가 발생하면 다른 5자리 숫자를 입력하여 변수 전체를 재정의하고 명령을 재실행합니다.

```bash
SUFFIX="58316"   # 예시: 기존 값과 다른 5자리 숫자
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
echo "SUFFIX=$SUFFIX"
```

### (2) P0v3 SKU 미지원 리전

특정 리전에서 P0v3 SKU를 지원하지 않는 경우 아래 오류가 발생합니다.

```text
The pricing tier 'P0V3' is not allowed in this resource group.
```

이 오류가 발생하면 `--sku P1V3`으로 대체합니다(비용이 다소 높아집니다). 이 워크숍은 `koreacentral`의 P0v3 가용성을 기준으로 검증되었지만, 구독별 할당량과 일시적 용량 상황에 따라 결과가 달라질 수 있습니다.

```bash
az appservice plan create -g $RG -n $PLAN --is-linux --sku P1V3
```

### (3) `application-insights` 확장 명령 없음

`az monitor app-insights` 명령을 찾을 수 없는 경우 확장이 설치되지 않은 것입니다.

```bash
az extension add --name application-insights --upgrade --only-show-errors
```

설치 후 명령을 재실행합니다.

---

이전 모듈: [01. 사전 준비](01-prerequisites.md) · 다음 모듈: [03. 코드 배포](03-deploy-code.md)
