"""Regression: downloader GUI and direct NSIS installer both enforce process gate."""
import ast
from pathlib import Path
import unittest
from unittest.mock import patch

from installer import p9b_update_process_guard


class InstallerAndUpdaterGuardTests(unittest.TestCase):
    def setUp(self):
        self.nsis=Path("installer/CodeBridge.nsi").read_text(encoding="utf-8")
        self.python=Path("installer/updater.py").read_text(encoding="utf-8")

    def test_nsis_oninit_checks_before_installer_section(self):
        source=self.nsis
        oninit=source.split("Function .onInit",1)[1].split("FunctionEnd",1)[0]
        self.assertIn('Call CheckRunningCodeBridgeBeforeUpdate',oninit)
        self.assertLess(oninit.index('Call CheckRunningCodeBridgeBeforeUpdate'),
                        oninit.index('init_done:'))
        guard=source.split("Function CheckRunningCodeBridgeBeforeUpdate",1)[1]
        guard=guard.split("FunctionEnd",1)[0]
        self.assertIn('InitPluginsDir',guard)
        self.assertIn('File "p9b_update_process_guard.py"',guard)
        self.assertIn('nsExec::ExecToStack',guard)
        self.assertIn('StrCmp $0 "0" update_safe',guard)
        self.assertIn("Abort",guard)
        self.assertLess(source.index("Function CheckRunningCodeBridgeBeforeUpdate"),
                        source.index('Section "CodeBridge" SEC_MAIN'))

    def test_nsis_payload_includes_postupdate_guard_source(self):
        self.assertEqual(self.nsis.count('  File "p9b_update_process_guard.py"'),2)

    def test_cli_propagates_block_and_does_not_mutate(self):
        with patch(
            "installer.p9b_update_process_guard.inspect_update_processes",
            return_value={"state":"UPDATE_PROCESS_BLOCKED","blockers":["CODEBRIDGE_MCP_RUNNING"]},
        ):
            self.assertEqual(p9b_update_process_guard.main(
                ["--install-root","."]),2)
        with patch(
            "installer.p9b_update_process_guard.inspect_update_processes",
            return_value={"state":"NO_RUNNING_CODEBRIDGE","blockers":[]},
        ):
            self.assertEqual(p9b_update_process_guard.main(
                ["--install-root","."]),0)


if __name__=="__main__":
    unittest.main()
