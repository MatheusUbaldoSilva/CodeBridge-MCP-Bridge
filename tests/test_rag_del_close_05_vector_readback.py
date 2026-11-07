"""Readback de vetores na exclusao: tolera o arredondamento do Qdrant, nao corrupcao."""
import random
import tempfile
import unittest
from pathlib import Path

from rag.runtime.knowledge_deletion_vector_copy import _same_vector


class SameVectorTests(unittest.TestCase):
    def test_float32_rounding_accepted(self):
        a = [0.1, -0.25, 0.5]
        self.assertTrue(_same_vector(a, [0.1 + 1.49e-8, -0.25, 0.5 - 1.49e-8]))

    def test_real_change_rejected(self):
        self.assertFalse(_same_vector([0.1, 0.2], [0.1, 0.2 + 1e-4]))

    def test_shape_and_values_strict(self):
        self.assertFalse(_same_vector([0.1, 0.2], [0.1]))
        self.assertFalse(_same_vector([], []))
        self.assertFalse(_same_vector([0.1], [float("nan")]))
        self.assertFalse(_same_vector([0.1], [True]))
        self.assertFalse(_same_vector([0.1], None))

    def test_named_vectors(self):
        self.assertTrue(_same_vector({"d": [0.5]}, {"d": [0.5 + 1e-9]}))
        self.assertFalse(_same_vector({"d": [0.5]}, {"e": [0.5]}))


class RealQdrantRoundTripTests(unittest.TestCase):
    """O mesmo caminho do piloto: ler de uma colecao e regravar em outra."""

    def test_reupserted_normalized_vectors_pass_readback(self):
        try:
            from qdrant_client.models import PointStruct
            from rag.index.qdrant_local import (
                close_qdrant_local, ensure_vector_collections, open_qdrant_local)
        except Exception as error:  # pragma: no cover - ambiente sem qdrant
            self.skipTest(f"qdrant indisponivel: {error}")
        with tempfile.TemporaryDirectory() as tmp:
            source = open_qdrant_local(Path(tmp) / "a")
            target = open_qdrant_local(Path(tmp) / "b")
            try:
                ensure_vector_collections(source)
                ensure_vector_collections(target)
                info = source.get_collection("text").config.params.vectors
                size = info.size if hasattr(info, "size") else next(iter(info.values())).size
                rng = random.Random(7)
                points = [PointStruct(id=i + 1, vector=[rng.uniform(-1, 1) for _ in range(size)],
                                      payload={"n": i}) for i in range(64)]
                source.upsert("text", points=points, wait=True)
                first = source.retrieve("text", ids=[p.id for p in points], with_vectors=True,
                                        with_payload=True)
                target.upsert("text", points=[PointStruct(id=p.id, vector=p.vector, payload=p.payload)
                                              for p in first], wait=True)
                second = {p.id: p for p in target.retrieve(
                    "text", ids=[p.id for p in points], with_vectors=True, with_payload=True)}
                for point in first:
                    self.assertEqual(point.payload, second[point.id].payload)
                    self.assertTrue(_same_vector(point.vector, second[point.id].vector))
            finally:
                close_qdrant_local(target)
                close_qdrant_local(source)


if __name__ == "__main__":
    unittest.main()