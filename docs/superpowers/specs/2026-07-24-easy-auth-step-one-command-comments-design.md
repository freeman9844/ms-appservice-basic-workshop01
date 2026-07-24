# Easy Auth Step 1 Command Comments Design

## Goal

Make module 09 Step 1 self-explanatory by adding concise Korean comments
directly inside the executable Bash block.

## Comment Mapping

Add a comment immediately before each logical command:

1. `authV2` extension: prepares the Azure CLI commands used to configure Easy
   Auth v2 in Step 2.
2. Tenant lookup: stores the current Microsoft Entra tenant identifier for the
   issuer URL used in Step 2.
3. App registration creation: registers the web application, configures the
   Easy Auth callback URI and single-tenant audience, and stores the
   Application (Client) ID.
4. ID token setting: enables OpenID Connect ID token issuance so Easy Auth can
   receive the signed-in user's identity claims.
5. Client secret creation: creates the credential Easy Auth uses to prove the
   application's identity to Microsoft Entra ID.
6. Client ID output: prints the identifier needed to delete the app
   registration in module 12.

## Identity Boundary

The comments must make these distinctions explicit:

- The user signs in with their own Microsoft Entra user account.
- The Client ID and Client Secret identify and authenticate the application,
  not the user.
- This step creates an app registration and does not enable an App Service
  managed identity.

## Scope

Do not alter any command, variable, redirect URI, audience, secret handling, or
cleanup behavior. Do not add a separate table or long explanation outside the
code block.

## Validation

Add a module 09 document contract test that requires the command comments and
the user/application/managed-identity distinction. After implementation,
commit on local `main` and synchronize `main` to GitHub.
