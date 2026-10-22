"""Read-only installed RAG source discovery and optional explicit Git candidate preview."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.runtime.incremental_explicit_source_preview import preview_approved_unindexed_sources
from rag.runtime.incremental_installed_change_discovery import discover_installed_reindex_scope


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only installed RAG change inventory")
    parser.add_argument("--approve-source", action="append", dest="sources", default=[],
                        help="review one explicitly selected, committed relative source")
    parser.add_argument("--changed-at-epoch", type=float, default=None,
                        help="known source event observation timestamp (required with --approve-source)")
    parser.add_argument("--debounce-seconds", type=float, default=30)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    scope = discover_installed_reindex_scope(root)
    report = {"scope": scope, "read_only": True,
              "queue_updated": False, "active_index_updated": False}
    if args.sources:
        report["new_source_preview"] = preview_approved_unindexed_sources(
            root, approved_paths=tuple(args.sources),
            changed_at_epoch=args.changed_at_epoch,
            debounce_seconds=args.debounce_seconds,
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    blocked = scope["state"] == "DISCOVERY_BLOCKED"
    if args.sources:
        blocked = blocked or report["new_source_preview"]["state"] != "EXPLICIT_SOURCE_PREVIEW_ONLY"
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
