"""Read-only scoped preflight for disposable unified P9-B recovery evidence."""
from __future__ import annotations

import tempfile
from pathlib import Path

from installer.rag_p9b_frozen_disposable_bundle import _contained, verify_disposable_bundle
from installer.rag_p9b_windows_shell_scope import (
    APP_KEYS, DESKTOP_LINK, MENU_LINKS, inspect_shell_scope,
)


def assess_disposable_scope(*, manifest, manifest_sha256, installed, appdata, desktop,
                            registry_query, temp_root=None):
    rejected = {"state": "P9B_DISPOSABLE_SCOPE_REFUSED", "verified": False,
                "read_only": True, "production_modified": False,
                "cutover_authorized": False}
    consistency = verify_disposable_bundle(
        manifest, manifest_sha256, temp_root=temp_root)
    if consistency.get("verified") is not True:
        return {**rejected, "reason": "FROZEN_BUNDLE_UNVERIFIED"}
    try:
        import json
        body = json.loads(Path(manifest).read_text(encoding="utf-8"))
        temp = Path(temp_root or tempfile.gettempdir()).resolve(strict=True)
        for name, path in (("installed", installed),("appdata", appdata),("desktop", desktop)):
            if (not _contained(path, temp)
                    or str(Path(path).resolve()) != body["scopes"][name]):
                return {**rejected, "reason": "BOUND_SCOPE_MISMATCH", "scope": name}
        # Refuse shortcut directory redirection before the existing inventory
        # reads any file. Missing directories are safe (absent shortcut).
        menu = (Path(appdata) / "Microsoft" / "Windows" / "Start Menu"
                / "Programs" / "CodeBridge")
        node = menu
        while node != Path(appdata):
            if node.is_symlink() or (hasattr(node, "is_junction") and node.is_junction()):
                return {**rejected, "reason": "SHELL_PATH_REDIRECTED"}
            node = node.parent
        prefix = body["scopes"]["hkcu_prefix"]
        if not callable(registry_query):
            return {**rejected, "reason": "INJECTED_REGISTRY_QUERY_REQUIRED"}
        def isolated_query(key):
            scoped_key = prefix + "\\" + ("APP" if key == APP_KEYS[0] else "UNINSTALL")
            return registry_query(scoped_key)
        proof = inspect_shell_scope(
            appdata=appdata, desktop=desktop, registry_query=isolated_query)
        if (proof.get("state") != "SHELL_SCOPE_OBSERVED_ONLY"
                or len(proof.get("shortcuts", [])) != len(MENU_LINKS)+1
                or set(proof.get("registry_keys", {})) != set(APP_KEYS)):
            return {**rejected, "reason": "SHELL_SCOPE_NOT_VERIFIED"}
        return {**rejected, "state": "P9B_DISPOSABLE_SCOPE_OBSERVED",
                "verified": True, "transaction_id": consistency["transaction_id"],
                "shortcuts_observed": len(MENU_LINKS)+1, "registry_keys_observed": len(APP_KEYS),
                "nsis_executed": False}
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        return {**rejected, "reason": "SCOPE_PREFLIGHT_FAILED"}