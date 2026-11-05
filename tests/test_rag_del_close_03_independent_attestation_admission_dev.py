"""Independent GUI witness + admission gate integration; read-only DEV only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from rag.runtime.knowledge_deletion_gui_witness_verify_dev import (
    verify_dev_gui_witness,
)
from rag.runtime.knowledge_deletion_operational_admission_dev import (
    review_operational_deletion_admission,
    selection_sha256,
)


class IndependentlyVerifiedAdmissionTests(unittest.TestCase):
    def test_external_verifier_witness_reaches_gate_but_never_authorizes(self):
        root=Path(__file__).resolve().parents[1]
        code=(
            "import os,sys,json,time\n"
            "sys.path.insert(0,sys.argv[1])\n"
            "import rag_panel,rag_deletion_review_panel\n"
            "from rag.runtime.knowledge_deletion_gui_witness_dev "
            "import start_dev_gui_witness,gui_birth_us\n"
            "start_dev_gui_witness()\n"
            "print(json.dumps({'pid':os.getpid(),'birth':gui_birth_us()}),flush=True)\n"
            "time.sleep(8)\n"
        )
        env=os.environ.copy()
        env["QT_QPA_PLATFORM"]="offscreen"
        proc=subprocess.Popen(
            [sys.executable,"-u","-c",code,str(root/"app_rewrite")],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
        )
        try:
            identity=json.loads(proc.stdout.readline())
            # This verifier executes in the parent/test process, not the GUI.
            witness=verify_dev_gui_witness(
                expected_pid=identity["pid"],
                expected_birth_us=identity["birth"],
            )
            self.assertEqual(
                witness["state"],"GUI_LOADED_CODE_KERNEL_PINNED_READONLY",witness
            )
            project="private_test"
            paths=["docs/alpha.md"]
            generation="scratch-generation-01"
            digest=selection_sha256(project,paths,generation)
            request=dict(
                project_id=project,selected_paths=paths,generation=generation,
                selection_sha256=digest,review_sha256="a"*64,
                catalog_sha256="b"*64,public_pointer_sha256="c"*64,
                created_epoch=120,
                operator_confirmation="RAG_DEL_REVIEW:"+project+":"+digest,
            )
            inventory=dict(
                read_only=True,queue_pending_count=0,canary_count=0,
                canary_catalog_consistent=True,
                public_generation=generation,blockers=[],
            )
            server_review=dict(
                state="READ_ONLY_REVIEW",project_id=project,
                selected_paths=paths,generation=generation,
                review_sha256="a"*64,execution_enabled=False,
                source_files_modified=False,
            )
            result=review_operational_deletion_admission(
                request,gui_witness=witness,
                operational_inventory=inventory,
                server_review=server_review,now_epoch=120,
            )
            self.assertNotIn("GUI_WITNESS_MISSING",result["blockers"])
            self.assertIn("OPERATIONAL_IPC_NOT_ATTESTED",result["blockers"])
            self.assertEqual(result["state"],"RAG_DEL_COMMAND_ADMISSION_BLOCKED")
            self.assertFalse(result["activation_authorized"])
            self.assertFalse(result["deletion_enabled"])
            self.assertFalse(result["operational_use_allowed"])
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.communicate(timeout=5)


if __name__=="__main__":
    unittest.main()

