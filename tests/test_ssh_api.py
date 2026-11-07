"""Rotas /v1/ssh/files/list e /v1/ssh/transfer da API local."""
import json
import sys
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app_rewrite"))
sys.path.insert(0, str(ROOT / "tests"))
from api_server import BridgeAPI
import ssh_transfer as st
from test_ssh_transfer import Base


class _Terminals:
    def __init__(self, opener):
        self.open_sftp = opener
        self.transfers = st.TransferRegistry(opener)


class _Runtime:
    def __init__(self, opener):
        self.terminals = _Terminals(opener)

    def ensure_chatgpt_turn(self, **kwargs):
        return None

    def end_chatgpt_activity(self):
        return None


class SshApiTests(Base):
    def setUp(self):
        super().setUp()
        self.api = BridgeAPI(_Runtime(self.opener), token="t")
        self.api.start()

    def tearDown(self):
        self.api.stop()
        super().tearDown()

    def post(self, path, body):
        req = Request(f"http://127.0.0.1:{self.api.port}{path}",
                      data=json.dumps(body).encode("utf-8"), method="POST")
        req.add_header("Authorization", "Bearer t")
        req.add_header("Content-Type", "application/json")
        try:
            with urlopen(req, timeout=10) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_list_both_sides(self):
        code, data = self.post("/v1/ssh/files/list", {"side": "WINDOWS", "path": str(self.local)})
        self.assertEqual(code, 200)
        self.assertEqual([i["name"] for i in data["files"]["items"]], ["pasta", "solto.txt"])
        code, data = self.post("/v1/ssh/files/list", {"side": "LINUX"})
        self.assertEqual(data["files"]["path"], "/home")
        code, data = self.post("/v1/ssh/files/list", {"side": "MARTE"})
        self.assertEqual(code, 400)

    def test_transfer_and_status_from_ia(self):
        code, data = self.post("/v1/ssh/transfer", {
            "direction": "UPLOAD", "sources": [str(self.local / "solto.txt")],
            "destination": "/home"})
        self.assertEqual(code, 200)
        tid = data["transfer"]["id"]
        self.assertEqual(data["transfer"]["origin"], "IA")
        for _ in range(100):
            code, data = self.post("/v1/ssh/transfer/status", {"transfer_id": tid})
            if data["transfer"]["state"] != "RUNNING":
                break
            time.sleep(0.05)
        self.assertEqual(data["transfer"]["state"], "DONE")
        self.assertTrue(self.remote("solto.txt").exists())
        code, data = self.post("/v1/ssh/transfer/status", {"transfer_id": "nada"})
        self.assertEqual((code, data["error"]), (404, "transfer_not_found"))


if __name__ == "__main__":
    unittest.main()