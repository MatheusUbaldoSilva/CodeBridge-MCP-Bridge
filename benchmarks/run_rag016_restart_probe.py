from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag.benchmark.restart import (
    prepare_restart_probe,
    verify_restart_probe,
)


OUTPUT = ROOT / "benchmarks" / "rag016_restart_latest.json"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("prepare", "verify"))
    parser.add_argument("--state-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    state_dir = Path(args.state_dir)

    if args.stage == "prepare":
        probe = prepare_restart_probe(
            ROOT,
            state_dir,
            project_id="codebridge",
            paths=("rag", "author_mcp", "docs"),
        )
    else:
        probe = verify_restart_probe(state_dir)

    payload = {
        "benchmark": "RAG-016-B_RESTART",
        "stage": args.stage,
        **probe.to_dict(),
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )
    OUTPUT.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
