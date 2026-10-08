from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.gpu_canary import run_gpu_canary


OUTPUT = ROOT / "benchmarks" / "rag016_gpu_canary_latest.json"


def main() -> None:
    result = run_gpu_canary(
        Path(r"C:\llama\llama-server.exe")
    )
    rendered = json.dumps(
        {
            "benchmark": "RAG-016-D_GPU",
            **result.to_dict(),
        },
        ensure_ascii=False,
        indent=2,
    )
    OUTPUT.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
