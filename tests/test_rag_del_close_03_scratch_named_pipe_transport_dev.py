"""Real Windows NamedPipe transport in a unique disposable channel only.

NEVER invokes installed GUI or RAG deletion. Tests source transport integrity,
not the identity of a connected installed process or operational authorization.
"""
from __future__ import annotations
import os
import sys
import threading
import queue
import uuid
import win32security
from pathlib import Path
from unittest import TestCase

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app_rewrite"))
from ipc_named_pipe import (
    NamedPipeServer, NamedPipeClient, build_current_user_pipe_sddl,
    current_user_sid_string
)


class ScratchNamedPipeTests(TestCase):
    def test_sddl_source_locks_to_current_sid(self):
        sddl=build_current_user_pipe_sddl()
        sid=current_user_sid_string()
        self.assertEqual(sddl, f"D:P(A;;GA;;;{sid})S:(ML;;NW;;;ME)")
        self.assertNotIn("(A;;GA;;;WD)",sddl)
        # Same-user ACL is NOT trusted installed process identity.

    def test_actual_source_named_pipe_roundtrip(self):
        name=r"\\.\pipe\CB.RAGDEL.SCRATCH."+uuid.uuid4().hex
        results=queue.Queue()
        def serve():
            try:
                with NamedPipeServer(name).accept() as connection:
                    # Kernel object DACL of the ACTUAL scratch transport, not
                    # merely source-level SDDL metadata.
                    descriptor=win32security.GetSecurityInfo(
                        connection._handle,
                        win32security.SE_KERNEL_OBJECT,
                        win32security.DACL_SECURITY_INFORMATION,
                    )
                    dacl=descriptor.GetSecurityDescriptorDacl()
                    if dacl is None:
                        raise AssertionError("scratch Named Pipe has no DACL")
                    allowed=[
                        win32security.ConvertSidToStringSid(dacl.GetAce(i)[2])
                        for i in range(dacl.GetAceCount())
                        if dacl.GetAce(i)[0][0] == 0
                    ]
                    if allowed != [current_user_sid_string()]:
                        raise AssertionError("scratch Named Pipe DACL does not match owner")
                    request=connection.receive()
                    connection.send(b"ACK:"+request)
                    final_ack=connection.receive()
                results.put((request,final_ack))
            except Exception as exc:
                results.put(exc)
        thread=threading.Thread(target=serve, daemon=True)
        thread.start()
        with NamedPipeClient.connect(name,timeout=3) as client:
            client.send(b"NO_RAG_WRITE")
            response=client.receive()
            client.send(b"CLOSE")
        thread.join(timeout=3)
        self.assertFalse(thread.is_alive(), "scratch pipe thread did not finish")
        server_result=results.get(timeout=1)
        if isinstance(server_result,Exception):
            raise server_result
        self.assertEqual(response,b"ACK:NO_RAG_WRITE")
        self.assertEqual(server_result,(b"NO_RAG_WRITE",b"CLOSE"))
