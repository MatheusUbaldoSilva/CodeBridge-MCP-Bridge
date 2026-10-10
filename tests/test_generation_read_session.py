import sqlite3
import tempfile
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.runtime.generation_activation import activate_test_generation
from rag.runtime.generation_read_session import pin_generation_for_read, GenerationReadError


def create_generation(root, name):
    folder = root / "generations" / name
    (folder / "qdrant").mkdir(parents=True)
    database = sqlite3.connect(folder / "rag_index.sqlite3")
    try:
        database.execute("CREATE TABLE marker(generation TEXT)")
        database.execute("INSERT INTO marker VALUES (?)", (name,))
        database.commit()
    finally:
        database.close()
    (folder / "rag-index-manifest.json").write_text("{}")


class ReadSessionTests(unittest.TestCase):
    def test_pinned_reader_survives_pointer_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "codebridge-rag-generation-test"
            root.mkdir()
            create_generation(root, "one")
            create_generation(root, "two")
            activate_test_generation(root, "one")
            session = pin_generation_for_read(root)
            activate_test_generation(root, "two")
            reader = session.open_sqlite()
            try:
                self.assertEqual(reader.execute("SELECT generation FROM marker").fetchone()[0], "one")
            finally:
                reader.close()
            self.assertEqual(session.qdrant.parent, session.sqlite.parent)
            self.assertEqual(session.manifest.parent, session.sqlite.parent)
            self.assertEqual(pin_generation_for_read(root).name, "two")

    def test_requires_active_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(GenerationReadError):
                pin_generation_for_read(tmp)


if __name__ == "__main__":
    unittest.main()
