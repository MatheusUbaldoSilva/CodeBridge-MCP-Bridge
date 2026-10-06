import unittest
from unittest.mock import patch
import mcp_server

def ex(op, payload, n=1):
    return {
        "request_syn":{"request_id":f"req{n}","operation":op},
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

class WaitTests(unittest.TestCase):
    def setUp(self):
        FakeClient.responses=[]
        FakeClient.calls=[]

    def test_partial_output_returns_without_reexecution(self):
        FakeClient.responses=[ex("EXECUTION_V2_OUTPUT",{
            "operation_ok":True,"execution_id":"e1","state":"RUNNING",
            "cursor":7,"next_cursor":12,"text":"hello","chars":5,
            "available_chars":5,"has_more":False,"eof":False,"complete":False
        })]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e1",cursor=7,wait_timeout_ms=5000)
        self.assertEqual(r.state,"RUNNING")
        self.assertEqual(r.cursor,7)
        self.assertEqual(r.next_cursor,12)
        self.assertEqual(r.text,"hello")
        self.assertFalse(r.complete)
        self.assertFalse(r.timed_out)
        self.assertEqual([x[0] for x in FakeClient.calls],["EXECUTION_V2_OUTPUT"])

    def test_timeout_keeps_cursor(self):
        FakeClient.responses=[ex("EXECUTION_V2_OUTPUT",{
            "operation_ok":True,"execution_id":"e2","state":"RUNNING",
            "cursor":9,"next_cursor":9,"text":"","chars":0,
            "available_chars":0,"has_more":False,"eof":False,"complete":False
        })]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient), patch.object(mcp_server.time,"monotonic",side_effect=[100.0,100.0]):
            r=mcp_server.codebridge_wait("e2",cursor=9,wait_timeout_ms=0)
        self.assertTrue(r.timed_out)
        self.assertEqual(r.cursor,9)
        self.assertEqual(r.next_cursor,9)
        self.assertEqual(r.text,"")

    def test_failure_returns_terminal_result(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_OUTPUT",{
                "operation_ok":True,"execution_id":"e3","state":"FAILED",
                "cursor":0,"next_cursor":3,"text":"bad","chars":3,
                "available_chars":3,"has_more":False,"eof":True,"complete":True
            },1),
            ex("EXECUTION_V2_RESULT",{
                "operation_ok":True,"execution_id":"e3","state":"FAILED",
                "target":"POWERSHELL5.1","exit_code":7,
                "error_type":"PowerShellCommandError","error_message":"falhou"
            },2),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e3")
        self.assertEqual(r.state,"FAILED")
        self.assertEqual(r.exit_code,7)
        self.assertEqual(r.error_type,"PowerShellCommandError")
        self.assertTrue(r.complete)

    def test_cancelled_is_terminal(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_OUTPUT",{
                "operation_ok":True,"execution_id":"e4","state":"CANCELLED",
                "cursor":2,"next_cursor":2,"text":"","chars":0,
                "available_chars":0,"has_more":False,"eof":True,"complete":True
            },1),
            ex("EXECUTION_V2_RESULT",{
                "operation_ok":True,"execution_id":"e4","state":"CANCELLED",
                "target":"SSH","exit_code":130,
                "error_type":"CommandCancelled","error_message":"cancelado"
            },2),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e4",cursor=2)
        self.assertEqual(r.state,"CANCELLED")
        self.assertEqual(r.next_cursor,2)
        self.assertTrue(r.complete)

    def test_invalid_id_rejected(self):
        with self.assertRaises(ValueError):
            mcp_server.codebridge_wait("")

if __name__=="__main__":
    unittest.main()