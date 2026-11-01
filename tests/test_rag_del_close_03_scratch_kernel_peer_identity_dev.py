"""Cross-process kernel peer PID/birth check on a unique scratch Windows pipe.

No installed CodeBridge IPC, live queue or RAG storage is touched.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import uuid
import unittest
import win32api
import win32con
import win32process

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from ipc_named_pipe import NamedPipeServer
from rag.runtime.knowledge_deletion_scratch_pipe_peer_identity_dev import (
    inspect_scratch_connected_peer_dev,
)


class ScratchKernelPeerIdentityTests(unittest.TestCase):
    def _exchange(self, *, spoof=False, birth_delta=0):
        name=r"\\.\pipe\CB.RAGDEL.PEER."+uuid.uuid4().hex
        results=queue.Queue()
        child_code=(
            "import os,sys,time\n"
            "from ipc_named_pipe import NamedPipeClient\n"
            "with NamedPipeClient.connect(sys.argv[1],timeout=5) as c:\n"
            " c.send(str(os.getpid()+int(sys.argv[2])).encode())\n"
            " c.receive()\n"
            " c.send(b'CLOSE')\n"
        )
        app_path=str(Path(__file__).resolve().parents[1]/"app_rewrite")
        environment=os.environ.copy()
        environment["PYTHONPATH"]=app_path+os.pathsep+environment.get("PYTHONPATH","")
        def serve():
            try:
                with NamedPipeServer(name).accept() as connection:
                    claimed=int(connection.receive().decode())
                    observation=inspect_scratch_connected_peer_dev(
                        connection,expected_client_pid=claimed
                    )
                    birth=observation["observed_birth"]
                    if birth_delta:
                        second=inspect_scratch_connected_peer_dev(
                            connection,expected_client_pid=claimed,
                            expected_client_birth=birth+birth_delta
                        )
                    else:
                        second=inspect_scratch_connected_peer_dev(
                            connection,expected_client_pid=claimed,
                            expected_client_birth=birth
                        )
                    connection.send(b"CHECKED")
                    close=connection.receive()
                    results.put((observation,second,close,claimed))
            except Exception as exc:
                results.put(exc)
        thread=threading.Thread(target=serve,daemon=True)
        thread.start()
        child=subprocess.Popen(
            [sys.executable,"-c",child_code,name,"7" if spoof else "0"],
            env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True
        )
        try:
            out,err=child.communicate(timeout=8)
            thread.join(timeout=8)
            self.assertFalse(thread.is_alive(),"scratch server remains connected")
            answer=results.get(timeout=1)
            if isinstance(answer,Exception):
                raise answer
            self.assertEqual(child.returncode,0,err)
            self.assertEqual(answer[2],b"CLOSE")
            return answer[0],answer[1],answer[3]
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=3)

    def test_real_distinct_process_kernel_peer_and_birth(self):
        first,second,pid=self._exchange()
        self.assertEqual(first["state"],"SCRATCH_KERNEL_PEER_PID_BIRTH_OBSERVED")
        self.assertEqual(first["observed_peer_pid"],pid)
        self.assertTrue(first["expected_pid_matches"])
        self.assertTrue(first["same_operator_user"])
        self.assertGreater(first["observed_birth"],0)
        self.assertEqual(second["state"],"SCRATCH_KERNEL_PEER_PID_BIRTH_OBSERVED")
        self.assertFalse(second["installed_gui_attested"])
        self.assertFalse(second["activation_authorized"])
        self.assertFalse(second["operational_use_allowed"])

    def test_client_supplied_spoofed_pid_is_rejected(self):
        first,second,pid=self._exchange(spoof=True)
        self.assertEqual(first["observed_peer_pid"],pid-7)
        self.assertFalse(first["expected_pid_matches"])
        self.assertIn("PEER_PID_MISMATCH",first["blockers"])
        self.assertFalse(first["activation_authorized"])

    def test_mismatched_birth_receipt_is_rejected(self):
        first,second,pid=self._exchange(birth_delta=1_000_000)
        self.assertEqual(first["observed_peer_pid"],pid)
        self.assertEqual(first["state"],"SCRATCH_KERNEL_PEER_PID_BIRTH_OBSERVED")
        self.assertFalse(second["expected_birth_matches"])
        self.assertIn("PEER_BIRTH_MISMATCH",second["blockers"])
        self.assertFalse(second["operational_use_allowed"])

    def test_reject_missing_client_identity(self):
        with self.assertRaises(ValueError):
            inspect_scratch_connected_peer_dev(object(),expected_client_pid=0)


if __name__ == "__main__":
    unittest.main()
