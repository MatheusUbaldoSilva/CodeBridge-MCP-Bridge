"""Offscreen independent-process challenge of DEV GUI witness; never real GUI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from rag.runtime.knowledge_deletion_gui_witness_verify_dev import (
    verify_dev_gui_witness,
)


class GuiWitnessDevTests(unittest.TestCase):
    def test_real_loaded_code_challenge_and_pid_birth(self):
        root=Path(__file__).resolve().parents[1]
        code=(
            "import os,sys,json,time\n"
            "sys.path.insert(0,sys.argv[1])\n"
            "import rag_panel,rag_deletion_review_panel\n"
            "from rag.runtime.knowledge_deletion_gui_witness_dev "
            "import start_dev_gui_witness,gui_birth_us\n"
            "start_dev_gui_witness()\n"
            "print(json.dumps({'pid':os.getpid(),'birth':gui_birth_us()}),flush=True)\n"
            "time.sleep(6)\n"
        )
        env=os.environ.copy()
        env["QT_QPA_PLATFORM"]="offscreen"
        proc=subprocess.Popen(
            [sys.executable,"-u","-c",code,str(root/"app_rewrite")],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env,
        )
        try:
            row=proc.stdout.readline()
            self.assertTrue(row,"GUI child did not publish process identity")
            identity=json.loads(row)
            result=verify_dev_gui_witness(
                expected_pid=identity["pid"],expected_birth_us=identity["birth"]
            )
            self.assertEqual(result["state"],"GUI_LOADED_CODE_KERNEL_PINNED_READONLY",result)
            self.assertEqual(result["observed_server_pid"],identity["pid"])
            self.assertTrue(result["challenge_bound"])
            self.assertTrue(result["installed_gui_loaded_code_observed"])
            self.assertTrue(result["expected_loaded_code_matches"])
            self.assertTrue(result["peer_accesscheck_observed"])
            self.assertEqual(len(result["loaded_code_receipts"]),2)
            self.assertFalse(result["activation_authorized"])
            self.assertFalse(result["installed_gui_operationally_attested"])
            self.assertFalse(result["operational_use_allowed"])
        finally:
            proc.kill()
            proc.communicate(timeout=4)

    def test_requires_positive_pinned_process_birth(self):
        with self.assertRaises(ValueError):
            verify_dev_gui_witness(expected_pid=1,expected_birth_us=0)


if __name__=="__main__":
    unittest.main()
