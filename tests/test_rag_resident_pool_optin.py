import unittest
from unittest.mock import patch
from rag.runtime.resident_models import ResidentEmbeddingPool
from rag.runtime.production_search import search_persistent_semantic

class ResidentPoolTests(unittest.TestCase):
 def test_pool_starts_empty(self):
  pool=ResidentEmbeddingPool()
  self.assertIsNone(pool.text_lifecycle)
  self.assertIsNone(pool.code_lifecycle)
  pool.close()
 def test_idempotent_close(self):
  pool=ResidentEmbeddingPool()
  pool.close()
  pool.close()
 def test_resident_mode_disabled_by_default(self):
  self.assertFalse(search_persistent_semantic.__kwdefaults__["experimental_resident_models"])
