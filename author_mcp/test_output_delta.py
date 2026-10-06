import unittest
from unittest.mock import patch

import mcp_server


def ex(payload, n=1):
    return {
        "request_syn":{"request_id":f"req{n}","operation":"EXECUTION_V2_OUTPUT"},
        "response_syn":{"response_id":f"res{n}"},
        "payload":payload,
    }


class FakeClient:
    responses=[]
    calls=[]
    def __init__(self,*a,**k): pass
    def exchange(self,op,payload=None,request_id=None):
        type(self).calls.append((op,payload or {}))
        return type(self).responses.pop(0)


class OutputDeltaTests(unittest.TestCase):
    def setUp(self):
        FakeClient.responses=[]
        FakeClient.calls=[]

    def test_terminal_wait_never_fetches_full_result(self):
        FakeClient.responses=[ex({
            "operation_ok":True,"execution_id":"e1","target":"CMD",
            "state":"FINISHED","cursor":9000,"next_cursor":9010,
            "text":"FINAL_ONLY","chars":10,"available_chars":9010,
            "has_more":False,"eof":True,"complete":True,
            "exit_code":0,
            "started_at":"2026-10-06T00:00:00+00:00",
            "finished_at":"2026-10-06T00:00:03+00:00",
            "shell_alive":True,"execution_recoverable":True,
        })]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e1",cursor=9000)
        self.assertEqual(r.stdout_delta,"FINAL_ONLY")
        self.assertEqual(r.stdout,"FINAL_ONLY")
        self.assertNotIn("HISTORY",r.stdout_delta)
        self.assertEqual(r.available_chars,9010)
        self.assertEqual(r.cursor_start,9000)
        self.assertEqual(r.cursor_end,9010)
        self.assertEqual(
            [call[0] for call in FakeClient.calls],
            ["EXECUTION_V2_OUTPUT"],
        )

    def test_successive_cursors_return_disjoint_deltas(self):
        FakeClient.responses=[
            ex({
                "operation_ok":True,"execution_id":"e2","target":"SSH",
                "state":"RUNNING","cursor":0,"next_cursor":5,
                "text":"AAAAA","chars":5,"available_chars":5,
                "has_more":False,"eof":False,"complete":False,
                "started_at":"2026-10-06T00:00:00+00:00",
                "shell_alive":True,"execution_recoverable":True,
            },1),
            ex({
                "operation_ok":True,"execution_id":"e2","target":"SSH",
                "state":"FINISHED","cursor":5,"next_cursor":10,
                "text":"BBBBB","chars":5,"available_chars":10,
                "has_more":False,"eof":True,"complete":True,
                "exit_code":0,
                "started_at":"2026-10-06T00:00:00+00:00",
                "finished_at":"2026-10-06T00:00:02+00:00",
                "shell_alive":True,"execution_recoverable":True,
            },2),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            first=mcp_server.codebridge_wait("e2",cursor=0)
            second=mcp_server.codebridge_wait("e2",cursor=first.cursor_end)
        self.assertEqual(first.stdout_delta,"AAAAA")
        self.assertEqual(second.stdout_delta,"BBBBB")
        self.assertEqual(first.cursor_end,second.cursor_start)
        self.assertEqual(first.stdout_delta+second.stdout_delta,"AAAAABBBBB")

    def test_terminal_at_eof_returns_metadata_without_history(self):
        FakeClient.responses=[ex({
            "operation_ok":True,"execution_id":"e3","target":"POWERSHELL5.1",
            "state":"FAILED","cursor":12000,"next_cursor":12000,
            "text":"","chars":0,"available_chars":12000,
            "has_more":False,"eof":True,"complete":True,
            "exit_code":9,"error_type":"PowerShellCommandError",
            "error_message":"failed","failed_command":"cmd /c exit 9",
            "started_at":"2026-10-06T00:00:00+00:00",
            "finished_at":"2026-10-06T00:00:01+00:00",
            "shell_alive":True,"execution_recoverable":True,
        })]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e3",cursor=12000)
        self.assertEqual(r.stdout_delta,"")
        self.assertEqual(r.stdout,"")
        self.assertEqual(r.exit_code,9)
        self.assertEqual(r.failed_command,"cmd /c exit 9")
        self.assertTrue(r.complete)


if __name__=="__main__":
    unittest.main()
