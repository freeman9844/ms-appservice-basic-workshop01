# 01. 사전 준비

> 🟢 **실행 명령** = 직접 입력·수행 · 👁️ **확인·관찰** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **스크린샷** = 화면 확인

---

## 목표

이 모듈에서는 워크숍 전반에 걸쳐 사용할 Azure Cloud Shell 환경을 준비합니다.

- Azure Cloud Shell에서 **영구 스토리지를 마운트**합니다.
- 실습에 사용할 Azure 구독을 확인합니다.
- 실습에 필요한 CLI 확장(`application-insights`, `authV2`)을 설치합니다.
- 워크숍 리포지토리를 `git clone`으로 가져옵니다.

## 소요 시간

약 10분

---

## 1단계 — Cloud Shell 영구 스토리지 마운트

브라우저에서 [https://shell.azure.com](https://shell.azure.com) 을 열어 **Bash** 를 선택합니다.

최초 접속 시 스토리지 선택 화면이 표시됩니다. **반드시 `Mount storage account` 라디오 버튼을 선택**하고 구독을 지정한 뒤 **Apply** 를 클릭합니다.

> ⚠️ **경고 — 임시 스토리지 선택 금지**
>
> `No storage account required` 옵션을 선택하면 Cloud Shell이 임시 디스크로 동작합니다.
> 세션 종료 시 설치한 확장·클론한 리포·작성한 스크립트가 **모두 삭제**됩니다.
> 반드시 `Mount storage account` → 구독 선택 → **Apply** 순서로 진행하십시오.

🖼️ **스크린샷** — Cloud Shell 영구 스토리지 마운트 선택 화면 *(T16에서 캡처 예정)*

---

## 2단계 — 구독 확인

Cloud Shell은 Azure Portal에 로그인된 계정으로 자동 인증됩니다. 아래 명령으로 현재 구독과 CLI 버전을 확인합니다.

🟢 **실행**

```bash
az account show -o table
az version
```

👁️ **확인** — 출력된 `Name` 및 `SubscriptionId` 값이 실습에 사용할 구독인지 확인합니다.

---

## 3단계 — CLI 확장 설치

이 워크숍은 `application-insights` 및 `authV2` 확장을 사용합니다.
`--upgrade` 플래그로 멱등 설치하므로 이미 설치된 경우 최신 버전으로 업그레이드됩니다.

🟢 **실행**

```bash
az extension add --name application-insights --upgrade --only-show-errors
az extension add --name authV2 --upgrade --only-show-errors
```

---

## 4단계 — 워크숍 리포지토리 클론

샘플 애플리케이션 소스 코드와 실습 스크립트를 내려받습니다.

🟢 **실행**

```bash
git clone https://github.com/jungwoonlee_microsoft/ms-appservice-basic-workshop01.git
cd ms-appservice-basic-workshop01
```

---

## 검증

아래 명령으로 구독 설정과 리포 클론 결과를 최종 확인합니다.

🟢 **실행**

```bash
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

### (1) Cloud Shell 세션 유실 — 확장·클론 파일 사라짐

Cloud Shell을 임시 스토리지(`No storage account required`)로 시작한 경우, 세션 종료 시 모든 파일이 삭제됩니다.
Cloud Shell을 완전히 종료한 뒤 다시 접속하여 **1단계**부터 `Mount storage account`를 선택해 재시작하십시오.

### (2) 확장 설치 실패

네트워크 오류나 타임아웃으로 설치가 실패한 경우 동일 명령을 재시도합니다.

```bash
az extension add --name application-insights --upgrade --only-show-errors
az extension add --name authV2 --upgrade --only-show-errors
```

설치가 계속 실패하면 CLI 자체를 업그레이드한 뒤 재시도합니다.

```bash
az upgrade
```

### (3) 구독이 여러 개인 경우

`az account show`에서 잘못된 구독이 표시되면 아래 명령으로 전환합니다.

```bash
az account set --subscription "<구독 ID 또는 이름>"
az account show -o table
```

---

이전 모듈: [00. 소개](../README.md) | 다음 모듈: [02. 환경 준비](02-environment-setup.md)
