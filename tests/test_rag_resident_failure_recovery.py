import unittest
from unittest.mock import MagicMock
from rag.models.code_lifecycle import CodeModelLifecycle
from rag.models.lifecycle import TextModelLifecycle
from rag.runtime.resident_models import ResidentEmbeddingPool

class ResidentFailureRecoveryTests(unittest.TestCase):
 def test_code_invalid_instance_is_cleared(self):
  pool=ResidentEmbeddingPool()
  client=MagicMock(spec=CodeModelLifecycle)
  pool.code_lifecycle=client
  with self.assertRaises(Exception):
   pool.embed_code("code question",object())
  self.assertIsNone(pool.code_lifecycle)
  client.unload.assert_called_once_with(timeout_seconds=15)

 def test_text_invalid_instance_is_cleared_even_if_unload_fails(self):
  pool=ResidentEmbeddingPool()
  client=MagicMock(spec=TextModelLifecycle)
  client.unload.side_effect=RuntimeError("unload failed")
  pool.text_lifecycle=client
  with self.assertRaises(Exception):
   pool.embed_text("text question",object())
  self.assertIsNone(pool.text_lifecycle)
  client.unload.assert_called_once_with(timeout_seconds=15)

 def test_closing_after_invalidated_instance_is_idempotent(self):
  pool=ResidentEmbeddingPool()
  lifecycle=MagicMock(spec=CodeModelLifecycle)
  pool.code_lifecycle=lifecycle
  with self.assertRaises(Exception):
   pool.embed_code("hello",object())
  pool.close()
  pool.close()
  lifecycle.unload.assert_called_once()
