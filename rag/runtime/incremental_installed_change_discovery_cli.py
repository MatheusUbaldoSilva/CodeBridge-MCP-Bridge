"""Read-only installed RAG source discovery and optional explicit Git candidate preview."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag.runtime.incremental_explicit_source_preview import preview_approved_unindexed_sources
from rag.runtime.incremental_installed_change_discovery import discover_installed_reindex_scope
from rag.runtime.incremental_preview_queue_handoff import prepare_preview_queue_handoff


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only installed RAG change inventory")
    parser.add_argument("--approve-source", action="append", dest="sources", default=[],
                        help="review one explicitly selected, committed relative source")
    parser.add_argument("--changed-at-epoch", type=float, default=None,
                        help="known source event observation timestamp (required with --approve-source)")
    parser.add_argument("--debounce-seconds", type=float, default=30)
    parser.add_argument("--show-queue-intent", action="store_true",
                        help="display revalidation-only queue intent; never enqueue")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    scope = discover_installed_reindex_scope(root)
    report = {"scope": scope, "read_only": True,
              "queue_updated": False, "active_index_updated": False}
    if args.show_queue_intent and not args.sources:
        report["queue_intent"] = {
            "state": "HANDOFF_BLOCKED", "reason": "NO_EXPLICIT_SOURCE_APPROVAL",
            "queued": False, "intents": [],
        }
    if args.sources:
        report["new_source_preview"] = preview_approved_unindexed_sources(
            root, approved_paths=tuple(args.sources),
            changed_at_epoch=args.changed_at_epoch,
            debounce_seconds=args.debounce_seconds,
        )
    if args.show_queue_intent and args.sources:
        report["queue_intent"] = prepare_preview_queue_handoff(
            report["new_source_preview"], approved_paths=tuple(args.sources),
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    blocked = (scope["state"] == "DISCOVERY_BLOCKED" or
               (args.show_queue_intent and not args.sources))
    if "queue_intent" in report:
        blocked = blocked or report["queue_intent"]["state"] != "ADVISORY_QUEUE_INTENTS_PREPARED"
    if args.sources:
        preview = report["new_source_preview"]
        blocked = blocked or (
            preview["state"] != "EXPLICIT_SOURCE_PREVIEW_ONLY"
            or len(preview.get("candidates", [])) != len(args.sources)
            or any(candidate.get("state") != "ELIGIBLE_FOR_DURABLE_QUEUE"
                   for candidate in preview.get("candidates", []))
        )
    return 2 if blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
