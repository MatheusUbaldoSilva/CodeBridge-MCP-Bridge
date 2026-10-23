import tempfile,unittest
from pathlib import Path
from installer.rag_p9b_same_machine_external_probe import inspect_external_runtime

class ExternalRuntimeTests(unittest.TestCase):
    def test_independent_python_and_psutil_paths(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root)
            installed=base/"installed";installed.mkdir()
            external=base/"external";external.mkdir()
            library=external/"psutil";library.mkdir()
            module=library/"__init__.py";module.write_text("")
            executable=external/"python.exe";executable.write_bytes(b"test")
            proof=inspect_external_runtime(installed=installed,interpreter=executable,
                psutil_origin=module,staged_lib=external)
            self.assertTrue(proof["verified"])
    def test_denies_python_inside_live_app(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);installed=base/"installed";installed.mkdir()
            external=base/"external";external.mkdir()
            py=installed/"python.exe";py.write_bytes(b"test")
            module=external/"psutil.py";module.write_text("")
            proof=inspect_external_runtime(installed=installed,interpreter=py,
                psutil_origin=module,staged_lib=external)
            self.assertEqual(proof["reason"],"DEPENDENCY_STILL_INSIDE_INSTALLED_APP")
    def test_denies_psutil_inside_live_app(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root);installed=base/"installed";installed.mkdir()
            external=base/"external";external.mkdir()
            py=external/"python.exe";py.write_bytes(b"test")
            module=installed/"psutil.py";module.write_text("")
            proof=inspect_external_runtime(installed=installed,interpreter=py,
                psutil_origin=module,staged_lib=external)
            self.assertEqual(proof["reason"],"DEPENDENCY_STILL_INSIDE_INSTALLED_APP")
if __name__=="__main__":unittest.main()
