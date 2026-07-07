# 02. 환경 준비

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

---

## 목표

이 모듈에서는 워크숍 전반에 걸쳐 사용할 Azure 리소스를 생성합니다.

- 환경 변수(`SUFFIX`, `RG`, `PLAN`, `APP`, `LAW`, `APPI`)를 정의합니다.
- **리소스 그룹**, **App Service Plan(P0V3)**, **Web App(Python 3.12)** 을 프로비저닝합니다.
- **Log Analytics Workspace** 와 **Application Insights 컴포넌트** 를 연결합니다.
- 기본 호스트네임(`APP_URL`)을 조회하여 앱 엔드포인트를 확인합니다.

## 소요 시간

약 10분

---

## 각 모듈 첫머리 변수 재설정 블록 규약

> 👁️ **중요 — SUFFIX 메모 필수**
>
> 아래 1단계에서 `SUFFIX`를 출력한 뒤 **반드시 메모**해 두십시오.
> 이후 모든 모듈의 첫머리에는 아래와 같은 **변수 재설정 블록**이 제공됩니다.
> Cloud Shell 세션이 끊기더라도 `SUFFIX` 값만 알고 있으면 전체 변수를 재구성할 수 있습니다.

```bash
# ── 이후 모듈 첫머리 변수 재설정 블록 예시 (SUFFIX를 직접 입력) ──
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

## 1단계 — 환경 변수 정의 및 리소스 생성

🟢 **실행**

```bash
SUFFIX=$RANDOM$RANDOM; SUFFIX=${SUFFIX:0:5}
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
echo "SUFFIX=$SUFFIX"   # ⚠️ 이후 모듈에서 재사용 — 메모해 두세요

az group create -n $RG -l $LOC
az appservice plan create -g $RG -n $PLAN --is-linux --sku P0V3
az webapp create -g $RG -n $APP --plan $PLAN --runtime "PYTHON:3.12"
az monitor log-analytics workspace create -g $RG -n $LAW -l $LOC
LAW_ID=$(az monitor log-analytics workspace show -g $RG -n $LAW --query id -o tsv)
az extension add --name application-insights --upgrade --only-show-errors
az monitor app-insights component create -g $RG --app $APPI -l $LOC --workspace $LAW_ID

APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
echo $APP_URL
```

---

> 👁️ **개념 — Plan(컴퓨트) vs Web App(앱) 분리**
>
> **App Service Plan** 은 VM 인스턴스(CPU·메모리·OS)를 정의하는 **컴퓨트 레이어** 입니다.
> **Web App** 은 그 Plan 위에서 실행되는 **논리적 앱 단위** 이며, 하나의 Plan에 여러 Web App을 올릴 수 있습니다.
>
> 이번 워크숍에서 **P0V3** SKU를 선택한 이유:
> - **배포 슬롯**(스테이징/프로덕션 스왑)은 Standard 계층 이상에서만 지원됩니다.
> - **Automatic scaling**(자동 스케일링) 및 **사이드카 컨테이너** 기능은 Premium V3 이상에서 활성화됩니다.
> - P0V3는 Premium V3의 최소 사이즈로 위 기능을 가장 경제적으로 체험할 수 있습니다.
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

🖼️ **스크린샷** — App Service 기본 자리표시 페이지 *(리허설에서 캡처 예정)*

---

## 트러블슈팅

### (1) 앱 이름 전역 중복 오류

Web App 이름(`$APP`)은 `azurewebsites.net` 도메인에서 **전 세계적으로 고유** 해야 합니다.
`The app name 'app-appsvcworkshop-XXXXX' is not available` 오류가 발생하면 `SUFFIX`를 새로 생성하여 변수 전체를 재정의하고 명령을 재실행합니다.

```bash
SUFFIX=$RANDOM$RANDOM; SUFFIX=${SUFFIX:0:5}
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
LAW=log-appsvcworkshop-$SUFFIX
APPI=appi-appsvcworkshop-$SUFFIX
echo "SUFFIX=$SUFFIX"
```

### (2) P0V3 SKU 미지원 리전

특정 리전에서 P0V3 SKU를 지원하지 않는 경우 아래 오류가 발생합니다.

```text
The pricing tier 'P0V3' is not allowed in this resource group.
```

이 경우 `--sku P1V3`으로 대체합니다(비용이 다소 높아집니다). 리허설 시 koreacentral 가용성을 실측하여 본 문서를 갱신합니다.

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

이전 모듈: [01. 사전 준비](01-prerequisites.md) | 다음 모듈: [03. 코드 배포](03-deploy-code.md)
