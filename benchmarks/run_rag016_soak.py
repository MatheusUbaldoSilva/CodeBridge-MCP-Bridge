from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.soak import run_storage_retrieval_soak


OUTPUT = ROOT / "benchmarks" / "rag016_soak_latest.json"


def main() -> None:
    result = run_storage_retrieval_soak(
        ROOT,
        project_id="codebridge",
        index_cycles=10,
        query_cycles=1000,
        paths=("rag", "author_mcp", "docs"),
    )
    rendered = json.dumps(
        {
            "benchmark": "RAG-016-A_SOAK",
            **result.to_dict(),
        },
        ensure_ascii=False,
        indent=2,
    )
    OUTPUT.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
