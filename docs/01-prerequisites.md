# 01. 사전 준비

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요)

---

## 목표

이 모듈에서는 워크숍 전반에 걸쳐 사용할 Azure Cloud Shell 환경을 준비합니다.

- 실습에 사용할 Azure 구독을 확인합니다.
- 실습에 필요한 CLI 확장(`application-insights`, `authV2`, `log-analytics`)을 설치합니다.
- 워크숍 리포지토리를 `git clone`으로 가져옵니다.

---

## 1단계 — Cloud Shell 접속 및 구독 선택

브라우저에서 [https://shell.azure.com](https://shell.azure.com) 을 열어 **Bash** 를 선택합니다.

Cloud Shell은 Azure Portal에 로그인된 계정으로 자동 인증되므로 별도 `az login`은 필요하지 않습니다. 아래 명령으로 현재 구독과 CLI 버전을 확인합니다.

🟢 **실행**

```bash
# 현재 로그인한 구독과 Azure CLI 버전을 확인합니다.
az account show -o table
az version
```

👁️ **확인** — 출력된 `Name` 및 `SubscriptionId` 값이 실습에 사용할 구독인지 확인합니다.

구독이 여러 개이거나 다른 구독으로 전환해야 한다면 아래 명령을 실행합니다.

🟢 **실행** (구독 전환이 필요한 경우에만)

```bash
# 워크숍 리소스를 만들 구독으로 전환한 뒤 선택 결과를 확인합니다.
az account set --subscription "<구독 ID 또는 이름>"
az account show -o table
```

📋 **예상 출력**

```text
Name                  CloudName    SubscriptionId                        State    IsDefault
--------------------  -----------  ------------------------------------  -------  -----------
<구독 이름>            AzureCloud   xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  Enabled  True
```

---

## 2단계 — CLI 확장 설치

이 워크숍은 `application-insights`, `authV2`, `log-analytics` 확장을 사용합니다.
`--upgrade` 플래그로 멱등 설치하므로 이미 설치된 경우 최신 버전으로 업그레이드됩니다.

🟢 **실행**

```bash
# 워크숍에서 사용할 Application Insights, Easy Auth, Log Analytics 확장을 설치합니다.
az extension add --name application-insights --upgrade --only-show-errors
az extension add --name authV2 --upgrade --only-show-errors
az extension add --name log-analytics --upgrade --only-show-errors
```

---

## 3단계 — 워크숍 리포지토리 클론

샘플 애플리케이션 소스 코드와 실습 스크립트를 내려받습니다.

🟢 **실행**

```bash
# 워크숍 리포지토리를 복제하고 작업 디렉터리로 이동합니다.
git clone https://github.com/jungwoonlee_microsoft/ms-appservice-basic-workshop01.git
cd ms-appservice-basic-workshop01
```

---

## 검증

아래 명령으로 구독 설정과 리포 클론 결과를 최종 확인합니다.

🟢 **실행**

```bash
# 구독과 리포지토리 준비 상태를 최종 확인합니다.
az account show -o table
ls app/
```

📋 **예상 출력**

```text
Name                  CloudName    SubscriptionId                        State    IsDefault
--------------------  -----------  ------------------------------------  -------  -----------
<구독 이름>            AzureCloud   xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  Enabled  True

app.py  ...
```

`az account show` 출력에 구독 정보가 표시되고 `ls app/`에 `app.py`가 존재하면 사전 준비가 완료된 것입니다.

---

## 트러블슈팅

### (1) 확장 설치 실패

네트워크 오류나 타임아웃으로 설치가 실패한 경우 동일 명령을 재시도합니다.

```bash
az extension add --name application-insights --upgrade --only-show-errors
az extension add --name authV2 --upgrade --only-show-errors
az extension add --name log-analytics --upgrade --only-show-errors
```

설치가 계속 실패하면 CLI 자체를 업그레이드한 뒤 재시도합니다.

```bash
az upgrade
```

### (2) 구독이 여러 개인 경우

`az account show`에서 잘못된 구독이 표시되면 아래 명령으로 전환합니다.

```bash
az account set --subscription "<구독 ID 또는 이름>"
az account show -o table
```

---

이전 모듈: [00. 소개](../README.md) · 다음 모듈: [02. 환경 준비](02-environment-setup.md)
