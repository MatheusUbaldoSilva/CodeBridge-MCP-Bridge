"""DQ-E-F-6: same-process Qt object / loaded pinned-reader observation (DEV only).

Invoke with a live RagPanel object on its owning GUI thread. Does not import
modules, load models, run readers, or prove an installed process to a remote
caller. This intentionally NEVER grants permission to publish or delete.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import sys

def inspect_gui_loaded_reader_dev(panel:object, repo_root:Path)->dict:
    if not isinstance(repo_root,Path) or not repo_root.is_absolute():
        raise ValueError("repo_root must be absolute")
    root=repo_root.resolve()
    expected_panel=root/"app_rewrite"/"rag_panel.py"
    expected_helper=root/"rag"/"runtime"/"knowledge_deletion_public_inventory_read.py"
    current_module=sys.modules.get(type(panel).__module__)
    qt_widget=sys.modules.get("PySide6.QtWidgets")
    qt_core=sys.modules.get("PySide6.QtCore")
    pinned=sys.modules.get("rag.runtime.knowledge_deletion_public_inventory_read")
    app=None
    if qt_widget is not None:
        QApplication=getattr(qt_widget,"QApplication",None)
        app=QApplication.instance() if QApplication is not None else None
    def source_matches(module,path):
        if module is None or not path.is_file() or path.is_symlink():
            return False
        actual=getattr(module,"__file__",None)
        return isinstance(actual,str) and Path(actual).resolve()==path
    loaded_panel=(
        current_module is not None
        and getattr(current_module,"RagPanel",None) is type(panel)
        and source_matches(current_module,expected_panel)
    )
    operation=getattr(current_module,"_rag_operation",None) if loaded_panel else None
    op_code=getattr(operation,"__code__",None)
    pinned_code=(
        op_code is not None and
        Path(op_code.co_filename).resolve()==expected_panel and
        "read_pinned_public_document_inventory" in op_code.co_names and
        "documents" in op_code.co_consts
    )
    helper_loaded=source_matches(pinned,expected_helper)
    reader=getattr(pinned,"read_pinned_public_document_inventory",None) if helper_loaded else None
    reader_code=getattr(reader,"__code__",None)
    helper_code=(
        reader_code is not None and
        Path(reader_code.co_filename).resolve()==expected_helper and
        "production_generation_read" in reader_code.co_names
    )
    qt_instance=False
    thread_correct=False
    if app is not None and loaded_panel and qt_core is not None:
        widget_type=getattr(qt_widget,"QWidget",None)
        if widget_type is not None and isinstance(panel,widget_type):
            qt_instance=True
            thread_correct=(
                panel.thread()==app.thread()
                and qt_core.QThread.currentThread()==app.thread()
            )
    checks={
        "panel_class_loaded_from_dev_source":bool(loaded_panel),
        "public_documents_route_present_in_loaded_code":bool(pinned_code),
        "pinned_reader_module_loaded_from_dev_source":bool(helper_loaded),
        "pinned_reader_lock_reference_loaded":bool(helper_code),
        "qapplication_running":qt_instance,
        "on_gui_owner_thread":thread_correct,
    }
    positive=all(checks.values())
    code_receipt=(
        hashlib.sha256(op_code.co_code+b"\0"+reader_code.co_code).hexdigest()
        if positive else None
    )
    return {
        "state":"DEV_GUI_INPROCESS_READER_OBSERVED" if positive
                else "DEV_GUI_INPROCESS_READER_NOT_ATTESTED",
        "checks":checks,
        "code_receipt_sha256":code_receipt,
        "observed_process_pid":os.getpid() if positive else None,
        "lab_inprocess_observed":positive,
        "installed_gui_trusted_channel_attested":False,
        "gui_runtime_attested_for_operational_deletion":False,
        "activation_authorized":False,
        "operational_use_allowed":False,
        "read_only":True,
    }
