import re
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[2]
MODULES = [
    "01-prerequisites.md",
    "02-environment-setup.md",
    "03-deploy-code.md",
    "04-app-settings.md",
    "05-deployment-slots-swap.md",
    "06-traffic-split-canary.md",
    "07-autoscale.md",
    "08-observability.md",
    "09-easy-auth.md",
    "10-sidecar-option.md",
    "11-autoheal-option.md",
    "12-cleanup.md",
]


def bash_blocks_before_troubleshooting(document):
    instructional_content = document.split("## 트러블슈팅", 1)[0]
    return re.findall(
        r"^```bash\n(.*?)\n```$",
        instructional_content,
        flags=re.MULTILINE | re.DOTALL,
    )


@pytest.mark.parametrize("module_name", MODULES)
def test_instructional_bash_blocks_have_purpose_comments(module_name):
    document = (ROOT / "docs" / module_name).read_text(encoding="utf-8")
    uncommented = [
        block.splitlines()[0]
        for block in bash_blocks_before_troubleshooting(document)
        if not any(line.startswith("# ") for line in block.splitlines())
    ]

    assert not uncommented, (
        f"{module_name} has Bash blocks without purpose comments: {uncommented}"
    )
