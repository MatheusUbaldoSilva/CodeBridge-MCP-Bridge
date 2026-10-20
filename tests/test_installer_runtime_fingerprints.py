import hashlib
import tempfile
import unittest
from pathlib import Path
from installer.runtime_fingerprints import fingerprint, collect_runtime_fingerprints

class RuntimeFingerprintTests(unittest.TestCase):
    def test_binary_sha256_exact_and_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"binary.bin"
            payload=b"\x00AB\xff\x00"
            path.write_bytes(payload)
            before=path.stat().st_mtime_ns
            value=fingerprint(path)
            self.assertEqual(value["sha256"],hashlib.sha256(payload).hexdigest())
            self.assertEqual(value["bytes"],len(payload))
            self.assertEqual(path.stat().st_mtime_ns,before)

    def test_missing_files_not_created(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"not-installed"
            state=Path(temp)/"rag-not-created"
            result=collect_runtime_fingerprints(root,state)
            self.assertEqual(result["state"],"READ_ONLY_RUNTIME_FINGERPRINTS")
            self.assertFalse(any(x["exists"] for x in result["files"].values()))
            self.assertFalse(root.exists())
            self.assertFalse(state.exists())
            self.assertFalse(result["writes_performed"])
