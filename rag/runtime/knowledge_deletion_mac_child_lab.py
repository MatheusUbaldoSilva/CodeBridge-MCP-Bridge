"""DQ-E-D-3C-G-5 child: scratch-only stdin MAC proof. No models or RAG."""
from __future__ import annotations
import json
import os
import sys
from rag.runtime.knowledge_deletion_pipe_receipt_mac_lab import sign_lab_stdio_receipts
from rag.runtime.knowledge_deletion_std_handle_receipt_lab import inspect_native_std_handle_receipts_lab
from rag.runtime.knowledge_deletion_parent_identity_lab import current_process_creation_filetime_lab
from rag.runtime.knowledge_deletion_child_stdio_lab import assert_scratch_stdio_pipes_win32

def main() -> int:
    try:
        assert_scratch_stdio_pipes_win32()
        stdio_receipts={
            name: value["descriptor_sha256"]
            for name,value in inspect_native_std_handle_receipts_lab()["receipts"].items()
        }
        raw=sys.stdin.buffer.readline(8193)
        if not raw or len(raw)>8192:
            return 2
        item=json.loads(raw)
        if not isinstance(item,dict) or set(item)!={
            "secret","session_id","challenge","request_sha256","project_id","generation"
        }:
            return 2
        secret=bytes.fromhex(item["secret"])
        pid=os.getpid()
        birth=current_process_creation_filetime_lab()
        mac=sign_lab_stdio_receipts(secret,creation_filetime=birth,
            stdio_receipts=stdio_receipts,session_id=item["session_id"],
            challenge=item["challenge"],request_sha256=item["request_sha256"],
            project_id=item["project_id"],generation=item["generation"],child_pid=pid)
        print(json.dumps({"pid":pid,"mac":mac,"birth":birth,
                          "stdio_receipts":stdio_receipts},sort_keys=True),flush=True)
        return 0
    except (TypeError,KeyError,ValueError,UnicodeError,OverflowError):
        return 2

if __name__=="__main__":
    raise SystemExit(main())
