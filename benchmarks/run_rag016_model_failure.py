from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.model_failure import run_model_failure_canary


OUTPUT = ROOT / "benchmarks" / "rag016_model_failure_latest.json"


def main() -> None:
    result = run_model_failure_canary(
        Path(r"C:\llama\llama-server.exe")
    )
    rendered = json.dumps(
        result.to_dict(),
        ensure_ascii=False,
        indent=2,
    )
    OUTPUT.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
