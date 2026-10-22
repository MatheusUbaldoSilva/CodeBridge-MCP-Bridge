"""Verify updater has both safety checks and includes the process gate in NSIS."""
import ast
from pathlib import Path
import unittest


class UpdaterGateWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.file=Path("installer/updater.py").read_text(encoding="utf-8")
        cls.nsis=Path("installer/CodeBridge.nsi").read_text(encoding="utf-8")
        cls.tree=ast.parse(cls.file)
        cls.window=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef)
                        and x.name=="UpdaterWindow")

    def method(self,name):
        return next(x for x in self.window.body if isinstance(x,ast.FunctionDef)
                    and x.name==name)

    def test_gate_is_imported_by_updater(self):
        self.assertTrue(any(
            isinstance(x,ast.ImportFrom) and x.module=="p9b_update_process_guard"
            for x in self.tree.body
        ))

    def test_start_update_gates_before_worker_start(self):
        method=self.method("start_update")
        lines={x.lineno for x in ast.walk(method)
               if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)
               and x.func.id=="inspect_update_processes"}
        self.assertEqual(len(lines),1)
        self.assertLess(min(lines),next(x.lineno for x in ast.walk(method)
            if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)
            and x.func.attr=="start"))

    def test_download_completion_gates_before_subprocess(self):
        method=self.method("download_finished")
        gate=min(x.lineno for x in ast.walk(method)
                 if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)
                 and x.func.id=="inspect_update_processes")
        launch=min(x.lineno for x in ast.walk(method)
                   if isinstance(x,ast.Call) and isinstance(x.func,ast.Attribute)
                   and x.func.attr=="Popen")
        self.assertLess(gate,launch)

    def test_nsis_bundles_guard_source(self):
        self.assertIn('  File "p9b_update_process_guard.py"',self.nsis)

if __name__=="__main__":
    unittest.main()
