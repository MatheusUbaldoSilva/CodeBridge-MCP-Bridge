import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.incremental_discovery_guard import inventory_folder, assert_discovery_unchanged


class DiscoveryGuardTests(unittest.TestCase):
    def test_detects_added_removed_and_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            first = folder / "first.md"
            first.write_text("original", encoding="utf-8")
            before = inventory_folder(folder)
            assert_discovery_unchanged(before, folder)
            first.write_text("changed to longer content", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed during discovery"):
                assert_discovery_unchanged(before, folder)
            before = inventory_folder(folder)
            second = folder / "new.txt"
            second.write_text("new", encoding="utf-8")
            with self.assertRaises(ValueError):
                assert_discovery_unchanged(before, folder)
            before = inventory_folder(folder)
            second.unlink()
            with self.assertRaises(ValueError):
                assert_discovery_unchanged(before, folder)

    def test_symlink_directory_not_traversed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            other = Path(tmp) / "other"
            root.mkdir()
            other.mkdir()
            (other / "external.txt").write_text("secret", encoding="utf-8")
            try:
                (root / "external").symlink_to(other, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            self.assertEqual(inventory_folder(root), {})


if __name__ == "__main__":
    unittest.main()
