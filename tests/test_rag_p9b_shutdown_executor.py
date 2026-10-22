import unittest
from unittest.mock import patch, Mock
from installer.rag_p9b_shutdown_executor import execute_shutdown


PLAN={"state":"SHUTDOWN_PLAN_ONLY","identity_digest":"abc","processes":[
    dict(component=c,pid=i,create_time=100.0+i)
    for c,i in (("GUI",10),("MCP",20),("ADAPTER",30),("TUNNEL",40))
]}


class FakeProc:
    def __init__(self,pid):
        self.pid=pid
        self.birth=100.0+pid
        self.running=True
        self.terminated=0
    def create_time(self): return self.birth
    def is_running(self): return self.running
    def terminate(self):
        self.terminated+=1
        self.running=False
    def wait(self,timeout=4): return 0


class FakePsutil:
    class AccessDenied(Exception): pass
    class NoSuchProcess(Exception): pass
    class TimeoutExpired(Exception): pass
    def __init__(self):
        self.procs={pid:FakeProc(pid) for pid in (10,20,30,40)}
    def process_iter(self,attrs):
        return [Mock(info={"pid":p.pid}) for p in self.procs.values()]
    def Process(self,pid): return self.procs[pid]


class ExecutorTests(unittest.TestCase):
    def setup_controller(self):
        fake=FakePsutil()
        return fake

    def test_requires_independent_execution(self):
        fake=self.setup_controller()
        result=execute_shutdown(".",expected_digest="abc",psutil_module=fake)
        self.assertEqual(result["reason"],"INDEPENDENT_EXECUTION_REQUIRED")
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),0)

    @patch("installer.rag_p9b_shutdown_executor.make_shutdown_plan",return_value=PLAN)
    def test_digest_change_aborts_without_signals(self,_):
        fake=self.setup_controller()
        result=execute_shutdown(".",expected_digest="other",execute=True,
                                independent=True,psutil_module=fake)
        self.assertEqual(result["reason"],"IDENTITY_DIGEST_CHANGED")
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),0)

    @patch("installer.rag_p9b_shutdown_executor.make_shutdown_plan",return_value=PLAN)
    def test_birthtime_changed_aborts_without_signals(self,_):
        fake=self.setup_controller()
        fake.procs[20].birth+=10
        result=execute_shutdown(".",expected_digest="abc",execute=True,
                                independent=True,psutil_module=fake)
        self.assertEqual(result["reason"],"PID_REUSED")
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),0)

    @patch("installer.rag_p9b_shutdown_executor.make_shutdown_plan",return_value=PLAN)
    def test_gui_close_fail_aborts(self,_):
        fake=self.setup_controller()
        result=execute_shutdown(".",expected_digest="abc",execute=True,
                                independent=True,psutil_module=fake,
                                gui_close=lambda pid:False)
        self.assertEqual(result["reason"],"GUI_WM_CLOSE_FAILED")
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),0)

    @patch("installer.rag_p9b_shutdown_executor.make_shutdown_plan",return_value=PLAN)
    def test_gui_timeout_does_not_send_signals_to_other_services(self,_):
        fake=self.setup_controller()
        result=execute_shutdown(".",expected_digest="abc",execute=True,
                                independent=True,psutil_module=fake,
                                gui_close=lambda pid:True,sleep=lambda _:None)
        self.assertEqual(result["reason"],"GUI_GRACEFUL_TIMEOUT")
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),0)

    @patch("installer.rag_p9b_shutdown_executor.make_shutdown_plan",return_value=PLAN)
    def test_order_and_complete_stopped(self,_):
        fake=self.setup_controller()
        def gui_close(pid):
            fake.procs[pid].running=False
            return True
        result=execute_shutdown(".",expected_digest="abc",execute=True,
                                independent=True,psutil_module=fake,
                                gui_close=gui_close,sleep=lambda _:None)
        self.assertEqual(result["state"],"SHUTDOWN_SIGNALS_COMPLETED")
        self.assertEqual(result["stopped"],["GUI","MCP","ADAPTER","TUNNEL"])
        self.assertEqual(sum(p.terminated for p in fake.procs.values()),3)
        self.assertFalse(result["installer_executed"])


if __name__=="__main__":
    unittest.main()
