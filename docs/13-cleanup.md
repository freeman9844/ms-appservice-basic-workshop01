# 13. 정리

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **예상 화면** = 브라우저/포털 스크린샷 참고

---

## 목표

이 모듈에서는 워크숍에서 생성한 모든 Azure 리소스를 삭제하여 불필요한 과금이 발생하지 않도록 정리합니다.

- 리소스 그룹(`$RG`)을 삭제하여 그룹 안의 모든 리소스(App Service Plan, Web App, 배포 슬롯, Log Analytics Workspace, Application Insights)를 한 번에 제거합니다.
- 리소스 그룹 밖에 존재하는 **Entra ID 앱 등록**은 별도 명령으로 삭제합니다(모듈 10을 수행한 경우에만 해당).
- 삭제 완료 여부를 CLI와 포털에서 확인합니다.

> 👁️ RG 삭제만으로 지워지지 않는 것: **Entra 앱 등록**(디렉터리 리소스). 모듈 10을 건너뛴 참가자는 Entra 앱 등록 삭제 단계를 생략해도 됩니다.

---

## 0단계 — 변수 재설정

> 정리 모듈은 세션이 끊긴 후 수행하는 경우가 많습니다. `SUFFIX` 는 **02 모듈에서 사용한 값과 동일하게** 입력하세요.

🟢 **실행**

```bash
# 정리할 워크숍 리소스 그룹 이름을 이전 SUFFIX로 복원합니다.
SUFFIX=<이전에_메모한_값>
RG=rg-appsvcworkshop-$SUFFIX
echo "RG=$RG"
```

📋 **예상 출력**

```
RG=rg-appsvcworkshop-<SUFFIX>
```

---

## 1단계 — 리소스 그룹 삭제

리소스 그룹을 삭제하면 그룹 안의 모든 리소스가 함께 삭제됩니다. `--no-wait` 옵션을 사용하므로 명령은 즉시 반환되고 삭제는 백그라운드에서 진행됩니다.

🟢 **실행**

```bash
# App Service, Plan, Log Analytics, Application Insights를 포함한 리소스 그룹 삭제를 시작합니다.
az group delete -n $RG --yes --no-wait
```

> 👁️ `--no-wait`를 사용했으므로 명령이 즉시 반환되는 것은 정상입니다. 실제 삭제는 수 분이 소요됩니다.

---

## 2단계 — Entra 앱 등록 삭제(모듈 10 수행자만)

> 👁️ 모듈 10(Easy Auth)를 건너뛴 경우 이 단계를 생략하고 3단계로 넘어가십시오.

Entra 앱 등록은 리소스 그룹 밖의 디렉터리 리소스이므로 별도로 삭제해야 합니다. 모듈 10에서 메모한 `CLIENT_ID`가 없어도 앱 등록 이름으로 조회하여 삭제할 수 있습니다.

🟢 **실행**

```bash
# Entra 앱 등록은 RG 밖 — 별도 삭제(10을 수행한 경우)
CLIENT_ID=$(az ad app list --display-name "auth-appsvcworkshop-$SUFFIX" --query "[0].appId" -o tsv)
az ad app delete --id $CLIENT_ID
```

> 👁️ 앱 등록 삭제에는 해당 앱의 소유자이거나 Application Administrator 이상의 권한이 필요합니다. 권한 오류가 발생하면 아래 트러블슈팅을 참고하십시오.

---

## 3단계 — 삭제 완료 확인

RG 삭제는 수 분이 소요됩니다. 아래 명령으로 삭제 완료 여부를 확인합니다.

🟢 **실행** — 수 분 후 확인

```bash
# 리소스 그룹과 선택적 Entra 앱 등록이 삭제되었는지 확인합니다.
az group exists -n $RG            # false
az ad app list --display-name "auth-appsvcworkshop-$SUFFIX" -o table   # 빈 목록
```

📋 **예상 출력 — RG 삭제 완료 시**

```
false
```

📋 **예상 출력 — Entra 앱 등록 삭제 완료 시**

```
DisplayName    Id    AppId
-----------    --    -----
```

> 👁️ `az group exists`가 아직 `true`를 반환하면 삭제가 진행 중인 것입니다. 1–2분 후 재실행하십시오.

---

## 🖼️ 포털에서 RG 부재 확인

🖼️ **예상 화면** — Azure Portal에서 리소스 그룹이 삭제되었는지 확인합니다.

1. [portal.azure.com](https://portal.azure.com)에 접속합니다.
2. **"리소스 그룹"** 메뉴로 이동하여 `rg-appsvcworkshop-<SUFFIX>` 이름의 그룹이 목록에 없는지 확인합니다.

---

## 로컬 임시 파일 정리(선택)

워크숍 중 Cloud Shell 홈 디렉터리에 생성된 파일은 무해합니다. 필요하면 아래 명령으로 제거할 수 있습니다.

> 👁️ `$HOME/go/bin/hey`와 워크숍 중 생성된 zip 파일은 남겨도 과금이 발생하지 않습니다. 원하는 경우에만 삭제하십시오.

🟢 **실행 (선택)**

```bash
# 리허설과 관찰 과정에서 생성한 로컬 임시 파일만 삭제합니다.
rm -f $HOME/go/bin/hey
```

---

## 트러블슈팅

### (1) RG 삭제 지연 — `az group exists`가 계속 `true` 반환

`--no-wait`로 삭제를 시작했으므로 수 분이 소요되는 것은 정상입니다. 1–2분 간격으로 재확인합니다.

```bash
az group exists -n $RG
```

### (2) Entra 앱 등록 삭제 권한 오류

앱 등록 소유자 확인 후 재시도합니다.

```bash
az ad app owner list --id $CLIENT_ID --query "[].userPrincipalName" -o tsv
```

본인이 소유자가 아니라면 테넌트 관리자에게 문의하십시오.

### (3) SUFFIX 분실

SUFFIX를 기억하지 못하는 경우 아래 명령으로 RG 이름을 조회합니다.

```bash
az group list --query "[?starts_with(name,'rg-appsvcworkshop')]"
```

---

수고하셨습니다! 워크숍의 모든 모듈을 완료하셨습니다. 추가 학습 자료와 참고 링크는 [README](../README.md)를 참고하십시오.

---

이전 모듈: [12. (선택) Auto-heal & 진단](12-autoheal-option.md) · [처음으로](../README.md)
