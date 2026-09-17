import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app_rewrite"
AUTHOR = ROOT / "author_mcp"
AUTHOR_PYTHON = AUTHOR / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(APP))

from runtime import BridgeRuntime

rt = BridgeRuntime()
try:
    rt.start()
    state = rt.snapshot()["author_mcp"]
    assert state.get("state") == "ONLINE", state
    assert state.get("managed_by_codebridge") is True, state
    test = subprocess.run(
        [str(AUTHOR_PYTHON), str(AUTHOR / "test_author_mcp_v2_all_targets.py")],
        cwd=str(AUTHOR),
        capture_output=True,
        text=True,
        timeout=60,
    )
    print(test.stdout, end="")
    if test.stderr:
        print(test.stderr, end="", file=sys.stderr)
    assert test.returncode == 0, test.returncode
    assert "AUTHOR_MCP_V2_ALL_TARGETS=PASS" in test.stdout
finally:
    rt.stop()
    time.sleep(0.5)

print("MANAGED_AUTHOR_MCP_ALL_TARGETS=PASS")
