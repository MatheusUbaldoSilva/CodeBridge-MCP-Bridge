"""Isolated real GUI-process opt-in PRECHECK transport, no production writes."""
from __future__ import annotations
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from rag.runtime.knowledge_deletion_operational_admission_dev import selection_sha256

APP_ROOT=Path(__file__).resolve().parents[1]/"app_rewrite"
_kernel=ctypes.WinDLL("kernel32",use_last_error=True)
_kernel.GetNamedPipeServerProcessId.argtypes=[
    wintypes.HANDLE,ctypes.POINTER(wintypes.ULONG)
]
_kernel.GetNamedPipeServerProcessId.restype=wintypes.BOOL


class GuiAdmissionDiagnosticTests(unittest.TestCase):
    def _exchange(self, *,operation="PRECHECK", spoof_receipts=False,
                  spoof_review=False):
        code=(
            "import json,os,sys,time\n"
            "from PySide6.QtWidgets import QApplication\n"
            "sys.path.insert(0,sys.argv[1])\n"
            "app=QApplication([])\n"
            "import rag_panel,rag_deletion_review_panel\n"
            "main=rag_panel.RagPanel()\n"
            "review_panel=rag_deletion_review_panel.KnowledgeRemovalReviewPanel()\n"
            "main.show(); review_panel.show()\n"
            "from rag.runtime.knowledge_deletion_gui_admission_dev import "
            "start_gui_admission_diagnostic_dev\n"
            "reader=lambda:{'read_only':True,'queue_pending_count':1,"
            "'canary_count':1,'public_generation':'pub','blockers':"
            "['PENDING_REVIEW_JOBS_PRESENT'],'canary_catalog_consistent':True}\n"
            "scope=lambda project:dict(state='TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING',"
            "read_only=True,project_id=project,target_isolation_proven=True,"
            "target_queue_jobs=0,target_active_canaries=0,unrelated_queue_jobs=1,"
            "unrelated_active_canaries=1,catalog_cas_required=True,"
            "catalog_sha256='b'*64,public_pointer_sha256='c'*64,blockers=[])\n"
            "review=lambda project,paths:dict(state='READ_ONLY_REVIEW',"
            "project_id=project,selected_paths=paths,generation='pub',"
            "review_sha256=('f' if sys.argv[2]=='spoof' else 'a')*64,"
            "execution_enabled=False,"
            "source_files_modified=False)\n"
            "pipe=start_gui_admission_diagnostic_dev("
            "inventory_reader=reader,project_reader=scope,review_reader=review)\n"
            "print(json.dumps({'pipe':pipe,'pid':os.getpid()}),flush=True)\n"
            "time.sleep(6)\n"
        )
        env=os.environ.copy()
        env["QT_QPA_PLATFORM"]="offscreen"
        env["CODEBRIDGE_RAGDEL_DEV_ADMISSION_DIAGNOSTIC"]="1"
        env["PYTHONPATH"]=str(APP_ROOT.parent)+os.pathsep+env.get("PYTHONPATH","")
        child=subprocess.Popen(
            [sys.executable,"-u","-c",code,str(APP_ROOT),
             "spoof" if spoof_review else "ok"],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
        )
        try:
            identity=json.loads(child.stdout.readline())
            self.assertTrue(identity["pipe"])
            sys.path.insert(0,str(APP_ROOT))
            from ipc_named_pipe import NamedPipeClient
            digest=selection_sha256("private_demo",["src/a.md"],"pub")
            message={"operation":operation,"request":{
                "project_id":"private_demo","selected_paths":["src/a.md"],
                "generation":"pub","selection_sha256":digest,
                "review_sha256":"a"*64,"catalog_sha256":"b"*64,
                "public_pointer_sha256":"c"*64,
                "created_epoch":0,"operational_channel_attested":True,
                "operator_confirmation":"RAG_DEL_REVIEW:private_demo:"+digest,
            }}
            if spoof_receipts:
                message["gui_witness"]={"state":"GUI_LOADED_CODE_KERNEL_PINNED_READONLY"}
                message["operational_inventory"]={"queue_pending_count":0}
            with NamedPipeClient.connect(identity["pipe"],timeout=5) as conn:
                server_id=wintypes.ULONG()
                self.assertTrue(
                    _kernel.GetNamedPipeServerProcessId(
                        conn._handle,ctypes.byref(server_id)
                    )
                )
                self.assertEqual(server_id.value,identity["pid"])
                challenge=json.loads(conn.receive().decode("utf-8"))
                self.assertEqual(
                    challenge["schema"],"RAG_DEL_ADMISSION_PRECHECK_CHALLENGE_V1"
                )
                message["schema"]="RAG_DEL_ADMISSION_PRECHECK_REQUEST_V1"
                message["challenge"]=challenge["challenge"]
                conn.send(json.dumps(message).encode("utf-8"))
                report=json.loads(conn.receive().decode("utf-8"))
                conn.send(b"CLOSE")
            self.assertFalse(report["activation_authorized"])
            self.assertFalse(report["operational_use_allowed"])
            self.assertFalse(report["deletion_enabled"])
            self.assertTrue(report["kernel_peer_accesscheck_complete"])
            return report
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=6)

    def test_real_gui_process_precheck_vetoes_unattested_operational_channel(self):
        receipt=self._exchange()
        self.assertEqual(receipt["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
        self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",receipt["blockers"])
        self.assertIn("GUI_WITNESS_MISSING",receipt["blockers"])
        self.assertIn("SHARED_CATALOG_CANARY_PIN_BLOCKS_ANY_WRITE",receipt["blockers"])

    def test_gui_process_rejects_delete_opcode(self):
        receipt=self._exchange(operation="DELETE")
        self.assertEqual(receipt["blockers"],["UNSUPPORTED_OPERATION"])

    def test_gui_process_rejects_peer_supplied_trust_receipts(self):
        receipt=self._exchange(spoof_receipts=True)
        self.assertEqual(receipt["blockers"],["UNSUPPORTED_OPERATION"])

    def test_gui_server_review_sha_mismatch_blocks(self):
        receipt=self._exchange(spoof_review=True)
        self.assertIn("SERVER_READ_ONLY_REVIEW_MISMATCH",receipt["blockers"])
        self.assertFalse(receipt["activation_authorized"])

    def test_opt_in_required(self):
        from rag.runtime.knowledge_deletion_gui_admission_dev import (
            start_gui_admission_diagnostic_dev, OPT_IN_ENV
        )
        original=os.environ.pop(OPT_IN_ENV,None)
        try:
            self.assertIsNone(start_gui_admission_diagnostic_dev())
        finally:
            if original is not None:
                os.environ[OPT_IN_ENV]=original
