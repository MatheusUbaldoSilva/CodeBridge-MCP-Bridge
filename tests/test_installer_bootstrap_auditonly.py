"""Bootstrap audit-only path does not run installers or mutate runtime."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class BootstrapReadOnlyAuditTests(unittest.TestCase):
    def test_audit_gate_comes_before_mutation(self):
        root=Path(__file__).resolve().parents[1]
        contents=(root/"installer"/"bootstrap.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$AuditOnly",contents)
        self.assertLess(contents.index("if ($AuditOnly)"),
                        contents.index("New-Item -ItemType Directory -Force -Path $TempDir"))

    def test_audit_missing_runtime_does_not_create_directory(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/"does-not-exist"
            ps=subprocess.run([
                "powershell.exe","-NoProfile","-ExecutionPolicy","Bypass",
                "-File",str(root/"installer"/"bootstrap.ps1"),
                "-InstallRoot",str(target),"-AuditOnly",
            ],capture_output=True,text=True,timeout=30)
            self.assertEqual(ps.returncode,2,ps.stderr)
            self.assertIn("RUNTIME_AUDIT_UNAVAILABLE",ps.stdout)
            self.assertFalse(target.exists())
