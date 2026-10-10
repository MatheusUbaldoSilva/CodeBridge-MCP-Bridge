"""Offline publication rehearsal with rollback, restricted to explicit test roots.

Not wired to production paths or the GUI. Caller must prove consumers stopped
before adapting this code for production use.
"""
from __future__ import annotations
from pathlib import Path
import os
import shutil


class OfflinePublishError(RuntimeError):
    pass


def rehearsal_publish(validated_bundle, active, *, fail_after=None):
    bundle = Path(validated_bundle).resolve()
    target = Path(active).resolve()
    if bundle == target or target in bundle.parents or bundle in target.parents:
        raise OfflinePublishError("overlapping paths")
    # Fail closed: rehearsal runs only beneath deliberately named test root.
    if "codebridge-rag-offline-test" not in {p.lower() for p in target.parts}:
        raise OfflinePublishError("only codebridge-rag-offline-test roots permitted")
    if not bundle.is_dir() or not target.is_dir():
        raise OfflinePublishError("bundle and active test directory required")
    for name in ("rag_index.sqlite3", "rag-index-manifest.json", "qdrant"):
        if not (bundle / name).exists() or not (target / name).exists():
            raise OfflinePublishError("incomplete bundle")
    backup = target.with_name(target.name + ".rollback")
    incoming = target.with_name(target.name + ".incoming")
    if backup.exists() or incoming.exists():
        raise OfflinePublishError("existing recovery artifacts; manual inspection required")
    from rag.runtime.incremental_bundle_validate import validate_incremental_bundle
    validate_incremental_bundle(bundle)
    try:
        shutil.copytree(bundle, incoming)
        validate_incremental_bundle(incoming)
        if fail_after == "copy":
            raise OfflinePublishError("injected failure after copy")
        os.replace(target, backup)
        try:
            if fail_after == "backup":
                raise OfflinePublishError("injected failure after backup")
            os.replace(incoming, target)
            if fail_after == "activate":
                raise OfflinePublishError("injected failure after activate")
            validate_incremental_bundle(target)
        except BaseException:
            # Keep the failed candidate for inspection if already activated.
            if target.exists():
                os.replace(target, incoming)
            os.replace(backup, target)
            raise
        return {"state": "OFFLINE_TEST_ACTIVATED", "backup": str(backup),
                "active": str(target)}
    except BaseException:
        if incoming.exists():
            shutil.rmtree(incoming)
        raise
