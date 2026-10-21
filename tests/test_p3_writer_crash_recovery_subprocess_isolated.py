"""Separate-process crash after journal, never touches installed RAG."""
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

from rag.runtime import production_generation_transition as writer

CANDIDATE="v1_delta_abc123ef"
BASE="v1_base_abc123ef"

CHILD = """
import os,sys
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch
from rag.runtime import production_generation_transition as w
root=Path(sys.argv[1])
original=w._atomic_json
def inject(path,payload):
    original(path,payload)
    if Path(path).name==w.JOURNAL_NAME:
        os._exit(47)
with patch.object(w,'_root',return_value=root), patch.object(
    w,'production_generation_lock',side_effect=lambda **_:nullcontext()
), patch('rag.runtime.production_cutover_gate.assess_real_cutover',return_value={
    'state':'READY','safe_to_activate':True,'blockers':[],
    'verified':{'candidate':{'validation':{'documents':211}}}
}), patch.object(w,'_atomic_json',side_effect=inject):
    w.publish_validated_generation(
        baseline='v1_base_abc123ef',candidate='v1_delta_abc123ef',
        operator_authorization='CODEBRIDGE_RAG_V1_ACTIVATE:v1_delta_abc123ef',
        public_reader_attestation={'generation_lock_enabled':True,'mcp_restart_confirmed':True})
"""


class CrashInSeparateProcessTests(unittest.TestCase):
    def test_durable_journal_after_process_crash_recovers_legacy(self):
        with tempfile.TemporaryDirectory(prefix="codebridge-p3-subprocess-") as tmp:
            root=Path(tmp)/"CodeBridge"/"rag"
            bundle=root/"generations"/CANDIDATE
            bundle.mkdir(parents=True)
            (bundle/"rag_index.sqlite3").write_bytes(b"candidate")
            (root/"rag_index.sqlite3").write_bytes(b"legacy")
            result=subprocess.run(
                [sys.executable,"-c",CHILD,str(root)],
                cwd=str(Path(__file__).resolve().parents[1]),
                capture_output=True,text=True,timeout=18)
            self.assertEqual(result.returncode,47,result.stderr)
            self.assertTrue((root/writer.JOURNAL_NAME).is_file())
            self.assertFalse((root/writer.POINTER_NAME).exists())
            with patch.object(writer,"_root",return_value=root), patch.object(
                writer,"production_generation_lock",side_effect=lambda **_:nullcontext()
            ):
                report=writer.rollback_pending_to_legacy(expected_candidate=CANDIDATE)
            self.assertEqual(report["state"],"RECOVERED_LEGACY")
            self.assertFalse((root/writer.JOURNAL_NAME).exists())
            self.assertEqual((root/"rag_index.sqlite3").read_bytes(),b"legacy")
            self.assertTrue((bundle/"rag_index.sqlite3").exists())
