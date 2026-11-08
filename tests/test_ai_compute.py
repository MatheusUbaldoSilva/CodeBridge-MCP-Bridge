"""Chave CPU / GPU / Automatico das IAs: preferencia, RAG, IA Local e card."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "app_rewrite"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.models import compute_preference as pref  # noqa: E402
from rag.models.fallback import ModelFallbackExhaustedError, manager_for_compute  # noqa: E402
from rag.models.lifecycle import LlamaServerConfig, ModelLoadError  # noqa: E402

import local_ai_server as srv  # noqa: E402

BASE = LlamaServerConfig(executable_path=Path("llama-server.exe"), model_path=Path("m.gguf"),
                         gpu_layers=99, device="CUDA0")


def fake_factory(fail_gpu=False, fail_cpu=False):
    created = []

    class FakeLife:
        def __init__(self, config):
            self.config = config
            created.append(config)

        def load(self, **kwargs):
            on_cpu = self.config.device == "none"
            if (on_cpu and fail_cpu) or (not on_cpu and fail_gpu):
                raise ModelLoadError("falhou")

        def snapshot(self):
            return None

    return FakeLife, created


class PreferenceTest(unittest.TestCase):
    def test_load_save_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ai" / "compute.json"
            self.assertEqual(pref.load_compute(path), "AUTO")
            pref.save_compute("cpu", path)
            self.assertEqual(json.loads(path.read_text()), {"compute": "CPU"})
            self.assertEqual(pref.load_compute(path), "CPU")
            # a IA Local le o mesmo arquivo
            self.assertEqual(srv.load_compute(path), "CPU")
            with patch.dict(os.environ, {pref.ENV_VAR: "gpu"}):
                self.assertEqual(pref.load_compute(path), "GPU")
                self.assertEqual(srv.load_compute(path), "GPU")
            path.write_text("lixo")
            self.assertEqual(pref.load_compute(path), "AUTO")
            with self.assertRaises(ValueError):
                pref.save_compute("TPU", path)


class RagManagerTest(unittest.TestCase):
    def test_cpu_mode_never_tries_gpu(self):
        factory, created = fake_factory()
        manager = manager_for_compute(BASE, compute="CPU", lifecycle_factory=factory,
                                      device_discovery=lambda exe: ["CUDA0"])
        manager.load()
        self.assertEqual([c.device for c in created], ["none"])
        self.assertEqual(created[0].gpu_layers, 0)

    def test_gpu_mode_never_falls_back_to_cpu(self):
        factory, created = fake_factory(fail_gpu=True)
        manager = manager_for_compute(BASE, compute="GPU", lifecycle_factory=factory,
                                      device_discovery=lambda exe: ["CUDA0"])
        with self.assertRaises(ModelFallbackExhaustedError):
            manager.load()
        self.assertEqual([c.device for c in created], ["CUDA0"])
        factory, created = fake_factory()
        manager = manager_for_compute(BASE, compute="GPU", lifecycle_factory=factory,
                                      device_discovery=lambda exe: [])
        with self.assertRaises(ModelFallbackExhaustedError):
            manager.load()
        self.assertEqual(created, [])  # sem placa: nem tenta a CPU

    def test_auto_keeps_gpu_first_then_cpu(self):
        factory, created = fake_factory(fail_gpu=True)
        manager = manager_for_compute(BASE, compute="AUTO", lifecycle_factory=factory,
                                      device_discovery=lambda exe: ["CUDA0"])
        manager.load()
        self.assertEqual([c.device for c in created], ["CUDA0", "none"])


class LocalAiDeviceTest(unittest.TestCase):
    def test_choose_device(self):
        gpu_box = {"vram_total_mb": 6144, "vram_used_mb": 500, "ram_total_mb": 16000, "ram_used_mb": 4000}
        cpu_box = {"vram_total_mb": None, "vram_used_mb": None, "ram_total_mb": 16000, "ram_used_mb": 4000}
        self.assertEqual(srv.choose_device("AUTO", gpu_box), ("GPU", None))
        self.assertEqual(srv.choose_device("AUTO", cpu_box), ("CPU", None))
        self.assertEqual(srv.choose_device("CPU", gpu_box), ("CPU", None))
        device, blocker = srv.choose_device("GPU", cpu_box)
        self.assertEqual(device, "GPU")
        self.assertIn("nenhuma placa", blocker)
        device, blocker = srv.choose_device("CPU", dict(cpu_box, ram_used_mb=12000))
        self.assertIn("processador", blocker)

    def test_server_starts_on_cpu_when_chosen(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            exe, model = base / "llama-server.exe", base / "m.gguf"
            exe.write_text("x")
            model.write_text("x")
            settings = base / "settings.json"
            srv.save_compute("CPU", srv.compute_file(settings))
            commands = []

            class Proc:
                pid, returncode = 1, None

                def poll(self):
                    return None

                def terminate(self):
                    pass

                def wait(self, timeout=None):
                    return 0

            old = (srv.LOG_FILE, srv.PID_FILE)
            srv.LOG_FILE, srv.PID_FILE = base / "log.txt", base / "pid"
            try:
                server = srv.LocalAiServer(
                    exe=exe, model=model, settings=settings,
                    popen=lambda cmd, **kw: commands.append(cmd) or Proc(),
                    health=lambda port, key: True,
                    memory=lambda: {"vram_total_mb": 6144, "vram_used_mb": 0,
                                    "ram_total_mb": 16000, "ram_used_mb": 4000})
                self.assertTrue(server.start())
                self.assertEqual(server.device, "CPU")
                cmd = commands[0]
                self.assertEqual(cmd[cmd.index("-ngl") + 1], "0")
                self.assertEqual(cmd[cmd.index("--device") + 1], "none")
                server.stop()
            finally:
                srv.LOG_FILE, srv.PID_FILE = old


class CardButtonsTest(unittest.TestCase):
    def test_buttons_like_timer_and_callback(self):
        from PySide6.QtWidgets import QApplication
        import ai_status

        QApplication.instance() or QApplication([])
        state = {"mode": "AUTO"}
        chosen = []

        def on_compute(mode):
            chosen.append(mode)
            state["mode"] = mode

        card = ai_status.AiStatusCard(local_server=lambda: None, scan=lambda: [],
                                      interval_ms=60000, compute=lambda: state["mode"],
                                      on_compute=on_compute)
        self.addCleanup(card.deleteLater)
        self.assertEqual([b.text() for b in card.compute_buttons.values()],
                         ["CPU", "GPU", "Automático"])
        self.assertTrue(card.compute_buttons["AUTO"].isChecked())
        card.compute_buttons["CPU"].click()
        self.assertEqual(chosen, ["CPU"])
        self.assertTrue(card.compute_buttons["CPU"].isChecked())
        self.assertIn("#c0762c", card.compute_buttons["CPU"].styleSheet())
        self.assertIn("#1b242c", card.compute_buttons["AUTO"].styleSheet())


if __name__ == "__main__":
    unittest.main()
