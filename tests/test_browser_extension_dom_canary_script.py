import subprocess
import sys
from pathlib import Path


def test_dom_canary_script_help_mentions_mock_and_real_provider_modes() -> None:
    project_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/run_browser_extension_dom_canary.py", "--help"],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "--mock" in result.stdout
    assert "--chatgpt-url" in result.stdout
    assert "--claude-url" in result.stdout
    assert "--headless" in result.stdout
