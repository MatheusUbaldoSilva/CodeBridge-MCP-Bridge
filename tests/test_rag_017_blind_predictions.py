import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from benchmarks.run_rag017_blind_predictions import run

class BlindPredictionsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.root=Path(self.temp.name)
  self.questions=self.root/"questions.jsonl"
  self.pred=self.root/"predictions.jsonl"
  self.manifest=self.root/"manifest.json"
  self.questions.write_text(json.dumps({"id":"eval-1","query":"Where is the code?"})+"\n",encoding="utf8")
  self.digest=hashlib.sha256(self.questions.read_bytes()).hexdigest()
 def tearDown(self):self.temp.cleanup()
 def test_rejects_changed_questions_before_opening_index(self):
  with patch("benchmarks.run_rag017_blind_predictions.open_qdrant_local") as op:
   with self.assertRaisesRegex(ValueError,"SHA-256 mismatch"):
    run(self.questions,self.pred,self.manifest,"0"*64)
   op.assert_not_called()
 def test_rejects_overwrite_before_opening_index(self):
  self.pred.write_text("existing",encoding="utf8")
  with patch("benchmarks.run_rag017_blind_predictions.open_qdrant_local") as op:
   with self.assertRaises(FileExistsError):
    run(self.questions,self.pred,self.manifest,self.digest)
   op.assert_not_called()
 def test_rejects_duplicate_question_ids(self):
  self.questions.write_text(self.questions.read_text()*2,encoding="utf8")
  sha=hashlib.sha256(self.questions.read_bytes()).hexdigest()
  with self.assertRaisesRegex(ValueError,"duplicate"):
   run(self.questions,self.pred,self.manifest,sha)
