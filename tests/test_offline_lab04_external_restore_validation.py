import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_fixture_snapshot import capture_fixture
from rag.runtime.offline_fixture_restore import restore_fixture_snapshot

class Lab04ExternalRestoreValidation(unittest.TestCase):
    def test_independent_python_validates_inactive_restore(self):
        with tempfile.TemporaryDirectory(prefix="rag-lab04-external-") as temp:
            root=Path(temp)/"codebridge-rag-generation-test"
            create_bundle(root,[("lab","independent","synthetic")])
            capture_fixture(root,"saved")
            result=restore_fixture_snapshot(root,"saved","external")
            self.assertEqual(result["state"],"LAB_FIXTURE_RESTORED_NOT_ACTIVATED")
            restored=root/"offline-fixture-restores"/"external"/"snapshot"
            command=("import json,sys;"
                     "from rag.runtime.incremental_bundle_validate import validate_incremental_bundle;"
                     "print(json.dumps(validate_incremental_bundle(sys.argv[1])))")
            child=subprocess.run([sys.executable,"-c",command,str(restored)],
                                 capture_output=True,text=True,timeout=20,
                                 cwd=str(Path(__file__).resolve().parents[1]))
            self.assertEqual(child.returncode,0,child.stderr)
            evidence=json.loads(child.stdout)
            self.assertEqual(evidence["state"],"VALIDATED_OFFLINE_NOT_PUBLISHED")
            self.assertEqual(evidence["documents"],1)
            self.assertFalse(result["production_authorized"])
            self.assertFalse((root/"active-generation.json").exists())

if __name__=="__main__":
    unittest.main()
