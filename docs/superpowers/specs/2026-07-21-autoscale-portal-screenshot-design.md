# Autoscale Portal Screenshot Design

## Goal

Add an Azure Portal confirmation immediately after the expected output in
`docs/07-autoscale.md` step 1. The confirmation supplements the Azure CLI
read-back without implying that the screenshot exposes settings it does not
show.

## Content and Placement

Insert the Portal guidance after the step 1 expected JSON output and before the
existing ARM property explanation.

Follow the established presentation used in modules 04 and 06:

1. A note stating that the CLI configuration can also be checked in Azure
   Portal.
2. The navigation path:
   **Azure Portal > Web App > App Service plan > Scale out**.
3. The values visible in the supplied screenshot:
   - Scale out method: **Automatic**
   - Maximum burst: **5**
   - Always ready instances: **1**
4. An `🖼️ 예상 화면` heading and the screenshot.

Do not state that the screenshot confirms `Prewarmed = 1`, because that value is
not displayed in the supplied Portal view. The existing CLI read-back remains
the authoritative confirmation for the Prewarmed setting.

## Image

Copy the supplied screenshot to:

`docs/images/07-automatic-scaling-portal.png`

Use alt text that describes the three visible values without including the
resource suffix shown in the screenshot.

## Scope

Only the screenshot asset and `docs/07-autoscale.md` are implementation
targets. No rehearsal script, application code, or autoscale configuration
changes are required.

## Validation

- Confirm the Markdown image path resolves to the committed image.
- Confirm the guidance appears directly after the step 1 expected output.
- Confirm the text mentions only the three values visible in the screenshot.
- Run the existing autoscale documentation contract test to ensure the step 1
  Azure CLI structure remains unchanged.
