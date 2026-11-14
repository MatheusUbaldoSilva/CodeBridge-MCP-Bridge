"""Testes de build_result da ferramenta codebridge_project_sync (engine fake)."""
import unittest

from project_sync_tools import build_result


class FakeEngine:
    def __init__(self):
        self.pairs = []

    def list_pairs(self):
        return list(self.pairs)

    def add_pair(self, remote, local, project_id=None, interval_min=10,
                 auto=False, index=False, mirror=False):
        pair = {"id": "sync1", "remote": remote, "local": local,
                "project_id": project_id, "interval_min": interval_min,
                "auto": auto}
        self.pairs.append(pair)
        return pair

    def remove_pair(self, pair_id):
        n = len(self.pairs)
        self.pairs = [p for p in self.pairs if p["id"] != pair_id]
        return n != len(self.pairs)

    def set_auto(self, pair_id, value):
        for p in self.pairs:
            if p["id"] == pair_id:
                p["auto"] = value
                return p
        return None

    def sync_by_id(self, pair_id):
        if any(p["id"] == pair_id for p in self.pairs):
            return {"id": pair_id, "added": 2, "updated": 0, "skipped": 0}
        return None

    def sync_pairs(self, pairs):
        return [{"id": p["id"], "added": 1} for p in pairs]

    def run_due(self):
        return [{"id": "sync1", "added": 0, "skipped": 3}]


class BuildResultTest(unittest.TestCase):
    def setUp(self):
        self.eng = FakeEngine()

    def test_list_vazio(self):
        r = build_result(self.eng, "list")
        self.assertTrue(r["operation_ok"])
        self.assertEqual(r["pairs"], [])

    def test_add_exige_remote_local(self):
        r = build_result(self.eng, "add", remote="/r")
        self.assertFalse(r["operation_ok"])
        self.assertIn("obrigatorios", r["error_message"])

    def test_add_ok_e_list(self):
        r = build_result(self.eng, "add", remote="/root/proj",
                         local="C:/dest", project_id="proj")
        self.assertTrue(r["operation_ok"])
        self.assertEqual(r["pair"]["id"], "sync1")
        self.assertEqual(len(build_result(self.eng, "list")["pairs"]), 1)

    def test_set_auto_inexistente(self):
        r = build_result(self.eng, "set_auto", pair_id="xxx", auto=True)
        self.assertFalse(r["operation_ok"])

    def test_run_par_inexistente(self):
        r = build_result(self.eng, "run", pair_id="xxx")
        self.assertFalse(r["operation_ok"])
        self.assertIn("nao encontrado", r["error_message"])

    def test_run_ok(self):
        build_result(self.eng, "add", remote="/r", local="/l")
        r = build_result(self.eng, "run", pair_id="sync1")
        self.assertTrue(r["operation_ok"])
        self.assertEqual(r["result"]["added"], 2)

    def test_run_due(self):
        r = build_result(self.eng, "run_due")
        self.assertTrue(r["operation_ok"])
        self.assertEqual(r["results"][0]["skipped"], 3)

    def test_acao_invalida(self):
        r = build_result(self.eng, "xyz")
        self.assertFalse(r["operation_ok"])
        self.assertIn("list|add", r["error_message"])


if __name__ == "__main__":
    unittest.main()