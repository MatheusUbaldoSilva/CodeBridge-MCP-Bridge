"""Synthetic-only post-stop store gate, not a production backup approval."""
from __future__ import annotations
from rag.runtime.offline_synthetic_stop_trial import run_synthetic_stop_trial
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles
from rag.runtime.offline_store_tree_catalog import catalog_synthetic_stores

def inspect_synthetic_after_stop(fixture_root):
    result = {"state":"BLOCKED", "issues":[], "copy_authorized":False,
              "all_handles_closed":False, "production_quiescence_proven":False}
    try:
        stopped=run_synthetic_stop_trial(fixture_root)
        handles=inspect_fixture_handles(fixture_root)
        catalog=catalog_synthetic_stores(fixture_root)
        if stopped.get("child_exit_code") != 0 or not stopped.get("handle_released"):
            result["issues"].append("SYNTHETIC_STOP_UNVERIFIED")
        if handles.get("state") != "LAB_HANDLES_READABLE_UNPROVEN":
            result["issues"].append("LAB_HANDLES_INCOMPLETE")
        if catalog.get("state") != "LAB_FILE_TREE_CATALOG_UNPROVEN":
            result["issues"].append("LAB_CATALOG_INCOMPLETE")
        if not result["issues"]:
            result["state"]="LAB_POST_STOP_STORES_READABLE_UNPROVEN"
        result["lab_files_checked"]=catalog.get("files_checked",0)
    except (OSError,RuntimeError,ValueError,TypeError,KeyError) as error:
        result["issues"].append(type(error).__name__)
    return result
