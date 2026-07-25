# 10. (선택) Easy Auth(Entra ID 로그인 게이트)

> 🟢 **실행** = 직접 입력·수행 · 👁️ **예시** = 눈으로만(개념/발췌) · 📋 **예상 출력** = 비교용(입력 불필요) · 🖼️ **예상 화면** = 브라우저/포털 스크린샷 참고

---

## 목표

이 모듈은 **선택 모듈**입니다. Azure App Service의 **Easy Auth** 기능을 구성하여 코드 수정 없이 Entra ID(구 Azure AD) 로그인 게이트를 활성화합니다. Entra 앱 등록을 생성하고 OAuth 2.0 / OpenID Connect 설정을 App Service에 연결한 뒤, 브라우저에서 인증 흐름을 확인합니다. 건너뛰어도 이후 모듈(11·12·13) 진행에 지장이 없습니다.

- Entra 앱 등록(`CLIENT_ID`)을 생성하고 리디렉션 URI를 구성합니다.
- `authV2` 확장으로 Easy Auth를 활성화하여 미인증 요청을 로그인 페이지로 리디렉션합니다.
- **코드 수정 없이** 플랫폼이 앞단에서 인증을 처리하는 Easy Auth 구조를 이해합니다.
- 모듈 종료 상태: **Entra 로그인 게이트 활성**.

완성 후의 구조는 다음과 같습니다.

```mermaid
flowchart LR
    U(("🌐 사용자")) -->|"HTTPS"| EA
    EA["🔒 Easy Auth<br/>(플랫폼 인증 레이어)<br/>미인증 → 302 → Entra 로그인"] -->|"인증 통과"| APP["Flask 앱"]
    EA -.->|"OAuth 2.0 / OIDC"| EID["Entra ID<br/>(앱 등록: auth-appsvcworkshop-SUFFIX)"]
```

> ⚠️ **이후 선택 모듈(11·12)은 curl 검증을 위해 첫머리에서 Easy Auth를 일시 비활성화합니다.** 해당 모듈 안내에 따라 auth를 껐다 켜십시오. 이 모듈을 마친 뒤에는 [13. 정리](13-cleanup.md)에서 **Entra 앱 등록 삭제 단계(모듈 10 수행자만)**를 잊지 마세요.

---

## 0단계 — (선택) 변수 재설정

> ⏭️ **08 모듈에서 이어서 같은 터미널로 진행 중이라면 이 단계는 건너뛰세요.**
> 새 터미널 세션을 열었거나 Cloud Shell이 재시작되어 변수가 사라진 경우에만 실행합니다.
> `SUFFIX` 는 **02 모듈에서 사용한 값과 동일하게** 입력하세요.

🟢 **실행**

```bash
# 이전 모듈의 리소스 변수를 복원하고 Web App URL을 다시 계산합니다.
SUFFIX=<이전에_메모한_값>
LOC=koreacentral
RG=rg-appsvcworkshop-$SUFFIX
PLAN=plan-appsvcworkshop-$SUFFIX
APP=app-appsvcworkshop-$SUFFIX
APP_URL="https://$(az webapp show -g $RG -n $APP --query defaultHostName -o tsv)"
echo "APP_URL=$APP_URL"
```

📋 **예상 출력**

```
APP_URL=https://app-appsvcworkshop-<SUFFIX>.azurewebsites.net
```

> 👁️ **1단계 완료 후 세션이 끊긴 경우 — `CLIENT_SECRET` 재발급**: `CLIENT_SECRET`은 생성 시점 이후 재조회가 불가능합니다. 세션이 끊겼다면 아래 명령으로 앱을 다시 찾고 시크릿을 재발급하여 진행하십시오.
> ```bash
> CLIENT_ID=$(az ad app list --display-name "auth-appsvcworkshop-$SUFFIX" --query "[0].appId" -o tsv)
> CLIENT_SECRET=$(az ad app credential reset --id $CLIENT_ID --query password -o tsv)
> ```

---

## 👁️ Easy Auth 구조 이해

Easy Auth는 App Service 플랫폼이 앱 앞단에서 인증을 처리하는 기능입니다.

| 항목 | 설명 |
|---|---|
| **코드 수정** | **0** — 앱 코드는 그대로, 플랫폼이 인증 레이어를 추가 |
| **내장 엔드포인트** | `/.auth/login/aad`, `/.auth/logout`, `/.auth/me` |
| **시크릿 저장** | `MICROSOFT_PROVIDER_AUTHENTICATION_SECRET` 앱 설정에 자동 주입 |
| **인증 흐름** | 미인증 요청 → 302 리디렉션 → Entra 로그인 → 콜백 → 원래 경로 |

> 👁️ `/.auth/me` 엔드포인트는 로그인 후 사용자 클레임(이름, 이메일, 그룹 등)을 JSON으로 반환합니다. 앱 코드에서는 `X-MS-CLIENT-PRINCIPAL-*` 헤더를 통해 클레임에 접근할 수 있습니다.

---

## 1단계 — Entra 앱 등록 및 시크릿 생성

🟢 **실행** — `authV2` 확장이 최신 버전인지 확인한 뒤, 테넌트 ID를 조회하고 앱 등록을 생성합니다.

```bash
# 2단계에서 Easy Auth v2 명령을 사용하기 위한 CLI 확장을 준비합니다.
az extension add --name authV2 --upgrade --only-show-errors

# 현재 로그인한 Entra 테넌트 ID를 조회합니다.
TENANT_ID=$(az account show --query tenantId -o tsv)

# 사용자 로그인을 받을 웹앱의 App Registration을 생성합니다.
# display-name은 13 정리에서 같은 이름으로 다시 조회·삭제할 App Registration 식별자입니다.
# redirect URI는 현재 Web App 기본 호스트 이름(APP_URL)에 Easy Auth 콜백 경로를 붙인 값이어야 하며,
# 이후 브라우저가 로그인 후 되돌아올 주소와 한 글자라도 다르면 AADSTS 리디렉션 불일치가 발생합니다.
# Easy Auth 콜백 URI와 단일 테넌트 범위를 지정하고,
# Application(Client) ID를 CLIENT_ID에 저장합니다.
CLIENT_ID=$(az ad app create --display-name "auth-appsvcworkshop-$SUFFIX" \
  --web-redirect-uris "$APP_URL/.auth/login/aad/callback" \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)

# Easy Auth가 로그인 사용자 클레임을 받을 수 있도록
# OpenID Connect ID 토큰 발급을 허용합니다.
az ad app update --id $CLIENT_ID --enable-id-token-issuance true

# Easy Auth가 Entra ID에 애플리케이션 자신을 증명할 Client Secret을 생성합니다.
# 사용자는 이 시크릿이 아니라 자신의 Entra 계정으로 로그인합니다.
# Managed Identity를 생성하거나 활성화하는 단계가 아닙니다.
# 이 워크숍 흐름은 별도 service principal 생성 명령(예: az ad sp create)을 실행하지 않습니다.
# 다른 가이드에서 보이는 "already exists" 메시지는 기존 앱 등록에 연결된 service principal 재생성 흐름에서만
# 흔히 허용되는 것이며, 여기서는 CLIENT_ID와 secret만 있으면 이후 Easy Auth 구성이 완료됩니다.
CLIENT_SECRET=$(az ad app credential reset --id $CLIENT_ID --display-name easyauth \
  --query password -o tsv)

# 13 정리에서 App Registration을 삭제할 수 있도록 Client ID를 출력합니다.
echo "CLIENT_ID=$CLIENT_ID"   # ⚠️ 13 정리에서 필요 — 메모
```

> ⚠️ **`CLIENT_ID` 값을 반드시 메모하십시오.** 모듈 13(정리)에서 Entra 앱 등록을 삭제할 때 이 값이 필요합니다.

> 👁️ `--sign-in-audience AzureADMyOrg`는 이 테넌트 계정만 로그인을 허용합니다. `--enable-id-token-issuance true`는 **필수 설정**입니다 — client secret이 구성된 Easy Auth는 하이브리드 플로(`response_type=code id_token`)를 사용하므로([공식 문서](https://learn.microsoft.com/azure/app-service/overview-authentication-authorization#client-type-and-oauth-flow-behavior)), 앱 등록에서 ID 토큰 발급이 꺼져 있으면 로그인 시 `AADSTS700054` 오류가 발생합니다.

> 👁️ 운영 환경에서는 **배포 슬롯마다 별도의 Entra 앱 등록**을 사용하는 것이 권장됩니다(환경 간 권한 공유 방지). 이 워크숍에서는 production 슬롯에만 Easy Auth를 구성합니다.

---

## 2단계 — Easy Auth 구성 및 활성화

🟢 **실행** — Microsoft 공급자를 구성한 뒤 Easy Auth를 활성화합니다.

```bash
# 인증 설정을 auth v2 스키마로 올리고 Microsoft Entra 공급자를 연결합니다.
# 방금 만든 App Registration의 CLIENT_ID/CLIENT_SECRET과 현재 테넌트 issuer를 Web App auth 설정에 묶습니다.
az webapp auth config-version upgrade -g $RG -n $APP
az webapp auth microsoft update -g $RG -n $APP \
  --client-id $CLIENT_ID --client-secret "$CLIENT_SECRET" \
  --issuer "https://login.microsoftonline.com/$TENANT_ID/v2.0" --yes
# 미인증 브라우저 요청을 Entra 로그인 페이지로 보내도록 Easy Auth를 활성화합니다.
az webapp auth update -g $RG -n $APP --enabled true \
  --action RedirectToLoginPage --redirect-provider azureActiveDirectory
```

> 👁️ `az webapp auth config-version upgrade`는 새 Web App의 기본 인증 설정(v1)을 authV2 스키마로 업그레이드합니다. 이 명령 없이 `az webapp auth microsoft update`를 실행하면 `Cannot use auth v2 commands when the app is using auth v1` 오류가 발생합니다. `--action RedirectToLoginPage`는 미인증 요청을 자동으로 로그인 페이지로 리디렉션합니다. `--redirect-provider azureActiveDirectory`는 여러 공급자 중 기본 공급자를 Entra ID로 지정합니다. 설정이 App Service에 전파되기까지 수십 초가 소요될 수 있습니다.

🟢 **실행** — 설정 전파 후 HTTP 상태 코드를 확인합니다(전파가 완료되지 않았으면 30초 대기 후 재시도).

```bash
# API 클라이언트와 브라우저 요청이 각각 401과 302를 반환하는지 확인합니다.
# 첫 curl은 비브라우저 기본 동작(401), 두 번째 curl은 브라우저 User-Agent를 흉내 낸 리디렉션(302) 확인용입니다.
curl -s -o /dev/null -w "%{http_code}\n" $APP_URL/
curl -s -o /dev/null -w "%{http_code}\n" -H "User-Agent: Mozilla/5.0" $APP_URL/
```

📋 **예상 출력**

```
401
302
```

> 👁️ Easy Auth는 요청의 `User-Agent`를 보고 응답을 구분합니다 — 브라우저(예: `Mozilla/5.0`)에는 `302`(Entra 로그인 페이지로 리디렉션)를, curl 같은 API 클라이언트에는 `401`을 반환합니다. 전파 직후에는 둘 다 `200`이 반환될 수 있으므로, 30초–1분 대기 후 재시도하십시오.

---

## 3단계 — 브라우저 검증

🟢 **브라우저에서 `$APP_URL`에 접속**합니다(변수 값으로 치환하여 입력).

🖼️ **예상 화면** — 브라우저가 `login.microsoftonline.com` 로그인 페이지로 리디렉션됩니다. 워크숍 계정으로 로그인하고 권한 동의 화면에서 **수락**을 클릭합니다.

![Entra 로그인 후 표시되는 권한 동의 화면 — auth-appsvcworkshop 앱이 기본 프로필 조회 권한을 요청](images/10-entra-consent.png)

> 👁️ 동의 화면의 "View your basic profile" 권한은 Easy Auth가 로그인 사용자의 기본 프로필 클레임을 받기 위해 필요한 최소 권한입니다. "이 애플리케이션은 Microsoft에서 게시하지 않았습니다" 문구는 방금 생성한 워크숍용 앱 등록이므로 정상입니다.

🖼️ **예상 화면** — 로그인 후 `$APP_URL`의 Flask 앱 페이지가 정상 표시됩니다.

![로그인 성공 후 Flask 앱 화면이 정상 표시됨 — slot: production, 인스턴스 ID 확인 가능](images/10-app-after-login.png)

> 👁️ 화면의 버전(v1/v2)과 배경색은 모듈 진행 상태에 따라 다를 수 있습니다. 로그인 게이트를 통과해 앱 페이지가 표시되는 것이 검증 포인트입니다.

---

## 트러블슈팅

| 증상 | 원인 | 해결 방법 |
|------|------|-----------|
| 브라우저 접속 시 로그인 리디렉션 없이 앱이 바로 표시됨 | Easy Auth 설정 전파가 아직 완료되지 않았거나 인증 플랫폼이 활성화되지 않았습니다. | 30초–1분 기다린 뒤 `az webapp auth show -g $RG -n $APP --query "{enabled:properties.platform.enabled,action:properties.globalValidation.unauthenticatedClientAction}" -o table`로 `enabled=true`, `action=RedirectToLoginPage`인지 확인하고 재시도합니다. |
| AADSTS 리디렉션 URI 불일치 오류가 발생함 | Entra 앱 등록의 URI와 실제 App Service 콜백 URL이 다릅니다. | `echo $APP_URL`로 URL을 확인하고 `az ad app update --id $CLIENT_ID --web-redirect-uris "$APP_URL/.auth/login/aad/callback"`으로 수정합니다.<br>브라우저 캐시를 지운 뒤 다시 접속합니다. |
| Entra 앱 등록 생성이 권한 부족으로 실패함 | 테넌트 정책에서 일반 사용자의 앱 등록을 제한하고 있습니다. | Portal의 **Microsoft Entra ID → 사용자 설정 → 앱 등록**을 확인합니다.<br>제한되어 있으면 테넌트 관리자에게 권한 부여 또는 앱 등록 생성을 요청합니다. |
| `az webapp auth microsoft update` 명령을 찾을 수 없음 | `authV2` 확장이 설치되지 않았거나 Cloud Shell 세션 초기화 후 누락되었습니다. | `az extension add --name authV2 --upgrade --only-show-errors`로 설치한 뒤 2단계를 다시 실행합니다. |

---

이전 선택 모듈: [09. Automatic Scaling · Prewarmed A/B](09-prewarmed-ab.md) 또는 이전 코어 모듈: [08. 관찰 가능성](08-observability.md) · 다음 모듈: [11. Sidecar(선택)](11-sidecar-option.md) 또는 [13. 정리](13-cleanup.md)
