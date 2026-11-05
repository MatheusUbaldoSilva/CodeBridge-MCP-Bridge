"""Real Windows source transport tests: read-only scratch admission IPC."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
import unittest
from rag.runtime.knowledge_deletion_operational_admission_dev import selection_sha256
from rag.runtime.knowledge_deletion_admission_pipe_dev import (
    serve_one_deletion_admission_precheck_dev,
)

class AdmissionPipeDevTests(unittest.TestCase):
    def setUp(self):
        self.project="private_lab"
        self.paths=["notes/one.md"]
        self.generation="scratch-v1"
        digest=selection_sha256(self.project,self.paths,self.generation)
        self.message=dict(operation="PRECHECK",request=dict(
            project_id=self.project,selected_paths=self.paths,generation=self.generation,
            selection_sha256=digest,review_sha256="a"*64,catalog_sha256="b"*64,
            public_pointer_sha256="c"*64,created_epoch=100,
            operational_channel_attested=False,
            operator_confirmation=f"RAG_DEL_REVIEW:{self.project}:{digest}"))
        self.gui=dict(
            state="GUI_LOADED_CODE_KERNEL_PINNED_READONLY",
            installed_gui_loaded_code_observed=True,
            expected_loaded_code_matches=True,
            peer_accesscheck_observed=True,
            challenge_bound=True,expected_pid=42,observed_server_pid=42)
        self.inventory=dict(
            read_only=True,queue_pending_count=0,canary_count=0,
            canary_catalog_consistent=True,public_generation=self.generation,
            blockers=[])
    def _exchange(self):
        root=Path(__file__).resolve().parents[1]
        pipe=r"\\.\pipe\CB.RAGDEL.ADMISSION.SCRATCH."+uuid.uuid4().hex
        messages=queue.Queue()
        def serve():
            try:
                messages.put(serve_one_deletion_admission_precheck_dev(
                    pipe,get_gui_witness=lambda:self.gui,
                    get_operational_inventory=lambda:self.inventory,
                    get_project_conflicts=getattr(self,"get_project_conflicts",None),
                    now_epoch=110))
            except Exception as error:
                messages.put(error)
        thread=threading.Thread(target=serve,daemon=True)
        thread.start()
        script=(
            "import sys,json\n"
            "sys.path.insert(0,sys.argv[2])\n"
            "from ipc_named_pipe import NamedPipeClient\n"
            "with NamedPipeClient.connect(sys.argv[1],timeout=5) as c:\n"
            " c.send(sys.stdin.buffer.read())\n"
            " r=c.receive()\n"
            " c.send(b'CLOSE')\n"
            " print(r.decode('utf-8'),flush=True)\n"
        )
        child=subprocess.Popen([sys.executable,"-u","-c",script,pipe,
                                str(root/"app_rewrite")],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        try:
            data=json.dumps(self.message).encode("utf-8")
            out,err=child.communicate(data,timeout=8)
            thread.join(timeout=8)
            self.assertFalse(thread.is_alive(),"unclosed scratch IPC server")
            server=messages.get(timeout=1)
            if isinstance(server,Exception):
                raise server
            self.assertEqual(child.returncode,0,err.decode(errors="replace"))
            response=json.loads(out.decode())
            self.assertEqual(server,response)
            return response
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=4)

    def test_live_or_predictable_pipe_name_rejected(self):
        for name in (r"\\.\pipe\CodeBridge.WindowsControl",
                     r"\\.\pipe\CB.RAGDEL.ADMISSION.SCRATCH.fixed",
                     r"\\.\pipe\CB.RAGDEL.ADMISSION.SCRATCH."+ "a"*31):
            with self.subTest(name=name), self.assertRaises(ValueError):
                serve_one_deletion_admission_precheck_dev(
                    name,get_gui_witness=lambda:self.gui,
                    get_operational_inventory=lambda:self.inventory)

    def test_real_cross_process_pipe_peer_checks_and_no_permission(self):
        r=self._exchange()
        self.assertEqual(r["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
        self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",r["blockers"])
        self.assertTrue(r["kernel_peer_accesscheck_complete"])
        self.assertGreater(r["kernel_connected_client_pid"],0)
        self.assertFalse(r["activation_authorized"])
        self.assertFalse(r["operational_use_allowed"])

    def test_unknown_operation_cannot_become_deletion(self):
        self.message["operation"]="DELETE"
        r=self._exchange()
        self.assertEqual(r["blockers"],["UNSUPPORTED_OPERATION"])
        self.assertFalse(r["deletion_enabled"])

    def test_client_cannot_supply_gui_or_queue_evidence(self):
        self.message["gui_witness"] = dict(
            state="GUI_LOADED_CODE_KERNEL_PINNED_READONLY",
            challenge_bound=True)
        self.message["operational_inventory"] = dict(
            queue_pending_count=0, canary_count=0)
        r=self._exchange()
        self.assertEqual(r["blockers"],["UNSUPPORTED_OPERATION"])
        self.assertFalse(r["operational_use_allowed"])

    def test_server_only_project_observer_not_client_payload(self):
        self.message["request"]["catalog_sha256"]="b"*64
        self.message["request"]["public_pointer_sha256"]="c"*64
        self.inventory["queue_pending_count"]=1
        self.inventory["canary_count"]=1
        self.inventory["blockers"]=["PENDING_REVIEW_JOBS_PRESENT"]
        self.observed_projects=[]
        self.get_project_conflicts=lambda pid:(
            self.observed_projects.append(pid)
            or dict(state="TARGET_CONFLICTS_CLEAR_FOR_READONLY_PLANNING",
                    project_id=pid,read_only=True,target_isolation_proven=True,
                    target_queue_jobs=0,target_active_canaries=0,
                    unrelated_queue_jobs=1,unrelated_active_canaries=1,
                    catalog_cas_required=True,catalog_sha256="b"*64,
                    public_pointer_sha256="c"*64,blockers=[])
        )
        try:
            result=self._exchange()
        finally:
            del self.get_project_conflicts
        self.assertEqual(self.observed_projects,[self.project])
        self.assertEqual(result["blockers"],[
            "OPERATIONAL_IPC_NOT_ATTESTED",
            "SHARED_CATALOG_CANARY_PIN_BLOCKS_ANY_WRITE"])
        self.assertFalse(result["activation_authorized"])

    def test_even_forged_positive_receipts_remain_non_operational(self):
        self.message["request"]["operational_channel_attested"]=True
        r=self._exchange()
        self.assertEqual(r["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
        self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",r["blockers"])
        self.assertFalse(r["activation_authorized"])
        self.assertFalse(r["deletion_enabled"])
