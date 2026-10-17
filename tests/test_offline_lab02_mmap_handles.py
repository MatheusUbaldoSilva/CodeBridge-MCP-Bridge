import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_incremental_bundle_e2e import create_bundle
from rag.runtime.offline_store_handle_probe import inspect_fixture_handles
from rag.runtime.offline_store_tree_catalog import catalog_synthetic_stores

MAPPED_CHILD = """import mmap,sys
f=open(sys.argv[1],'rb')
mapping=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)
f.close()
print('MAPPED',flush=True)
sys.stdin.readline()
mapping.close()
"""

@unittest.skipUnless(sys.platform == "win32", "Windows-only mmap lab")
class SyntheticMappedFiles(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="rag-lab02-d-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "codebridge-rag-generation-test"
        create_bundle(self.root, [("lab", "mapped", "synthetic")])

    def check_mapping_not_authorized(self, file_path):
        child = subprocess.Popen(
            [sys.executable, "-c", MAPPED_CHILD, str(file_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "MAPPED")
            probe = inspect_fixture_handles(self.root)
            self.assertFalse(probe["copy_authorized"])
            self.assertFalse(probe["all_handles_closed"])
            self.assertFalse(probe["production_quiescence_proven"])
            catalog = catalog_synthetic_stores(self.root)
            self.assertFalse(catalog["copy_authorized"])
            self.assertFalse(catalog["all_handles_closed"])
            self.assertFalse(catalog["production_quiescence_proven"])
        finally:
            child.stdin.write("\n")
            child.stdin.flush()
            output, errors = child.communicate(timeout=10)
            self.assertEqual(child.returncode, 0, errors)
        released = inspect_fixture_handles(self.root)
        self.assertFalse(released["copy_authorized"])
        self.assertFalse(released["all_handles_closed"])

    def test_manifest_mapped_after_original_descriptor_closed(self):
        self.check_mapping_not_authorized(self.root / "rag-index-manifest.json")

    def test_qdrant_file_mapped_after_original_descriptor_closed(self):
        vector = next(p for p in (self.root / "qdrant").rglob("*") if p.is_file())
        self.check_mapping_not_authorized(vector)

if __name__ == "__main__":
    unittest.main()
