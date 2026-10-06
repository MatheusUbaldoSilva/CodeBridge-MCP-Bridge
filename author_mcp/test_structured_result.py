import unittest
from unittest.mock import patch
import mcp_server

def ex(op,payload,n=1):
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

class StructuredResultTests(unittest.TestCase):
    def setUp(self):
        FakeClient.responses=[]
        FakeClient.calls=[]

    def test_exec_final_contract_contains_minimum_fields(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_START",{
                "operation_ok":True,"execution_id":"e1","target":"POWERSHELL5.1","state":"CREATED"
            },1),
            ex("EXECUTION_V2_STATUS",{
                "operation_ok":True,"execution_id":"e1","target":"POWERSHELL5.1","state":"FINISHED",
                "started_at":"2026-10-06T00:00:00+00:00","finished_at":"2026-10-06T00:00:00.250000+00:00"
            },2),
            ex("EXECUTION_V2_RESULT",{
                "operation_ok":True,"execution_id":"e1","target":"POWERSHELL5.1","state":"FINISHED",
                "started_at":"2026-10-06T00:00:00+00:00","finished_at":"2026-10-06T00:00:00.250000+00:00",
                "exit_code":0,"output":"OK\n","error_type":None,"error_message":None
            },3),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient), patch.object(mcp_server.time,"sleep",return_value=None):
            r=mcp_server.codebridge_exec("POWERSHELL5.1","Write-Output OK",wait_timeout_ms=1500)
        d=r.model_dump()
        minimum={"state","execution_id","target","exit_code","stdout","stderr","duration_ms","started_at","finished_at","error_source","error_type","error_message","raw_available"}
        self.assertTrue(minimum.issubset(d))
        self.assertEqual(r.stdout,"OK\n")
        self.assertEqual(r.output,r.stdout)
        self.assertEqual(r.stderr,"")
        self.assertEqual(r.stream_mode,"COMBINED")
        self.assertFalse(r.streams_separated)
        self.assertEqual(r.duration_ms,250)
        self.assertIsNone(r.error_source)

    def test_exec_failure_classifies_command_error(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_START",{
                "operation_ok":True,"execution_id":"e2","target":"CMD","state":"CREATED"
            },1),
            ex("EXECUTION_V2_STATUS",{
                "operation_ok":True,"execution_id":"e2","target":"CMD","state":"FAILED",
                "started_at":"2026-10-06T00:00:00+00:00","finished_at":"2026-10-06T00:00:01+00:00"
            },2),
            ex("EXECUTION_V2_RESULT",{
                "operation_ok":True,"execution_id":"e2","target":"CMD","state":"FAILED",
                "started_at":"2026-10-06T00:00:00+00:00","finished_at":"2026-10-06T00:00:01+00:00",
                "exit_code":7,"output":"bad\n","error_type":"CmdCommandError","error_message":"falhou"
            },3),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient), patch.object(mcp_server.time,"sleep",return_value=None):
            r=mcp_server.codebridge_exec("CMD","exit /b 7",wait_timeout_ms=1500)
        self.assertEqual(r.state,"FAILED")
        self.assertEqual(r.error_source,"command")
        self.assertEqual(r.exit_code,7)
        self.assertEqual(r.stdout,"bad\n")

    def test_wait_final_returns_full_stdout_while_text_remains_delta(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_OUTPUT",{
                "operation_ok":True,"execution_id":"e3","state":"FINISHED",
                "cursor":5,"next_cursor":10,"text":"PART2","chars":5,
                "available_chars":10,"has_more":False,"eof":True,"complete":True
            },1),
            ex("EXECUTION_V2_RESULT",{
                "operation_ok":True,"execution_id":"e3","target":"SSH","state":"FINISHED",
                "started_at":"2026-10-06T00:00:00+00:00","finished_at":"2026-10-06T00:00:02+00:00",
                "exit_code":0,"output":"PART1PART2","error_type":None,"error_message":None
            },2),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e3",cursor=5)
        self.assertEqual(r.text,"PART2")
        self.assertEqual(r.stdout,"PART1PART2")
        self.assertEqual(r.stderr,"")
        self.assertEqual(r.duration_ms,2000)
        self.assertEqual(r.next_cursor,10)
        self.assertTrue(r.complete)

    def test_wait_partial_does_not_duplicate_full_stdout(self):
        FakeClient.responses=[
            ex("EXECUTION_V2_OUTPUT",{
                "operation_ok":True,"execution_id":"e4","state":"RUNNING",
                "cursor":0,"next_cursor":5,"text":"PART1","chars":5,
                "available_chars":5,"has_more":False,"eof":False,"complete":False
            },1),
        ]
        with patch.object(mcp_server,"ProtocolHTTPClient",FakeClient):
            r=mcp_server.codebridge_wait("e4",cursor=0)
        self.assertEqual(r.text,"PART1")
        self.assertEqual(r.stdout,"")
        self.assertIsNone(r.duration_ms)
        self.assertEqual(r.stream_mode,"COMBINED")

if __name__=="__main__":
    unittest.main()