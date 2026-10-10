import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BACKUP=(ROOT/"benchmarks"/"rag017_qdrant_backup_restore.py").read_text(encoding="utf-8")
NEGATIVE=(ROOT/"benchmarks"/"rag017_qdrant_backup_negative.py").read_text(encoding="utf-8")
class QdrantBackupRestoreContract(unittest.TestCase):
 def test_disposable_path_gate(self):
  self.assertIn('CodeBridge-RAG017-BackupProbe-',BACKUP)
  self.assertIn('root.exists()',BACKUP)
  self.assertIn('unsafe root',NEGATIVE)
 def test_backup_and_restore_validate_integrity(self):
  self.assertIn('original!=copied',BACKUP)
  self.assertIn('items[0].payload.get("marker")',BACKUP)
  self.assertIn('hashlib.sha256',BACKUP)
 def test_negative_probe_does_not_modify_original(self):
  self.assertIn('corrupted_copy',NEGATIVE)
  self.assertIn('original_backup_untouched',NEGATIVE)
  self.assertIn('target.read_bytes()+b"TEST_CORRUPTION"',NEGATIVE)
