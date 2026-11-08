"""Instalador das IAs (app_rewrite/ai_setup.py): plano, downloads, llama-server e fluxo completo."""
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
for path in (str(ROOT / "app_rewrite"), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

import ai_setup  # noqa: E402
import ai_status  # noqa: E402
import local_ai_server as srv  # noqa: E402
from rag import llama_binary  # noqa: E402

GB = 1024 ** 3


def art_for(key, name, data):
    return ai_setup.Artifact(key, key.upper(), name, "https://exemplo/" + name, len(data),
                             hashlib.sha256(data).hexdigest())


class FakeResponse(io.BytesIO):
    def __init__(self, data, status):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeWeb:
    """Serve bytes por URL, respeita Range e pode cortar a conexao no meio."""

    def __init__(self, files, cut_after=None):
        self.files, self.cut_after, self.calls = files, cut_after, []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.calls.append((url, request.headers.get("Range")))
        data = self.files[url]
        start = 0
        rng = request.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].rstrip("-"))
        body = data[start:]
        if self.cut_after is not None:
            body, self.cut_after = body[:self.cut_after], None
        return FakeResponse(body, 206 if rng else 200)


def llama_zip(path, nested=True):
    with zipfile.ZipFile(path, "w") as archive:
        prefix = "llama-b10819/" if nested else ""
        archive.writestr(prefix + "llama-server.exe", b"exe")
        archive.writestr(prefix + "ggml-base.dll", b"dll")
    return path.read_bytes()


def version_run(cmd, **kwargs):
    class Out:
        returncode = 0
        stdout = ""
        stderr = "version: 0.4.0-dev (build 10819, commit 6a1a922d2)" if Path(cmd[0]).is_file() else ""
    if not Path(cmd[0]).is_file():
        raise OSError("nao existe")
    return Out()


class PlanTest(unittest.TestCase):
    def test_tiers(self):
        gpu = ai_setup.Hardware(gpu_name="RTX 3050", vram_mb=6144, driver="576.02", ram_mb=16000)
        self.assertEqual((ai_setup.make_plan(gpu).variant, ai_setup.make_plan(gpu).qwen,
                          ai_setup.make_plan(gpu).compute), ("cuda", "7B", "AUTO"))
        small_gpu = ai_setup.Hardware(gpu_name="GTX", vram_mb=4096, driver="550.1", ram_mb=8000)
        self.assertEqual((ai_setup.make_plan(small_gpu).variant, ai_setup.make_plan(small_gpu).qwen),
                         ("cuda", "3B"))
        work = ai_setup.Hardware(ram_mb=16100)
        plan = ai_setup.make_plan(work)
        self.assertEqual((plan.variant, plan.qwen, plan.compute), ("cpu", "7B", "CPU"))
        self.assertEqual(ai_setup.make_plan(ai_setup.Hardware(ram_mb=7900)).qwen, "3B")
        self.assertEqual(ai_setup.make_plan(ai_setup.Hardware(ram_mb=4000)).qwen, "1.5B")
        old_driver = ai_setup.Hardware(gpu_name="GTX", vram_mb=8192, driver="472.12", ram_mb=16000)
        plan = ai_setup.make_plan(old_driver)
        self.assertEqual(plan.variant, "cpu")
        self.assertIn("antigo", plan.reason)

    def test_detect_hardware(self):
        class Out:
            returncode, stdout = 0, "NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144, 576.02\n"

        hw = ai_setup.detect_hardware(run=lambda *a, **k: Out(), ram_bytes=16 * GB, disk_root=ROOT)
        self.assertEqual((hw.gpu_name, hw.vram_mb, hw.driver, hw.ram_mb),
                         ("NVIDIA GeForce RTX 3050 6GB Laptop GPU", 6144, "576.02", 16384))
        self.assertTrue(hw.cuda_ok)

        def no_nvidia(*a, **k):
            raise FileNotFoundError("nvidia-smi")
        hw = ai_setup.detect_hardware(run=no_nvidia, ram_bytes=8 * GB, disk_root=ROOT)
        self.assertIsNone(hw.gpu_name)
        self.assertFalse(hw.cuda_ok)
        self.assertIn("sem placa NVIDIA", hw.describe())

    def test_pinned_artifacts(self):
        for art in ai_setup.ALL_ARTIFACTS:
            self.assertEqual(len(art.sha256), 64, art.key)
            self.assertTrue(art.url.startswith("https://"), art.key)
            self.assertIn(art.name, art.url)
        self.assertIn("/b10819/", ai_setup.LLAMA_CUDA.url)
        self.assertEqual(ai_setup.QWEN["7B"].size, 4683073536)


class DownloadTest(unittest.TestCase):
    def test_resume_after_cut_and_verify(self):
        data = os.urandom(3 * 1024 * 1024 + 17)
        art = art_for("x", "x.bin", data)
        web = FakeWeb({art.url: data}, cut_after=1024 * 1024)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "x.bin"
            ai_setup.download(art, dest, opener=web, sleep=lambda s: None)
            self.assertEqual(dest.read_bytes(), data)
            self.assertFalse(dest.with_name("x.bin.part").exists())
        self.assertEqual(web.calls[1][1], "bytes=%d-" % (1024 * 1024))

    def test_corrupt_download_is_removed(self):
        art = art_for("x", "x.bin", b"certo")
        web = FakeWeb({art.url: b"errad"})
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "x.bin"
            with self.assertRaises(ai_setup.SetupError):
                ai_setup.download(art, dest, opener=web, sleep=lambda s: None)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_name("x.bin.part").exists())

    def test_cancel_keeps_partial(self):
        data = os.urandom(3 * 1024 * 1024)
        art = art_for("x", "x.bin", data)
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "x.bin"
            calls = []

            def cancelled():
                calls.append(1)
                return len(calls) > 2
            with self.assertRaises(ai_setup.Cancelled):
                ai_setup.download(art, dest, opener=FakeWeb({art.url: data}), cancelled=cancelled,
                                  sleep=lambda s: None)
            self.assertTrue(dest.with_name("x.bin.part").exists())

    def test_verified_cache_skips_hash(self):
        data = b"modelo"
        art = art_for("m", "m.gguf", data)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.gguf"
            path.write_bytes(data)
            cache = ai_setup.VerifiedCache(Path(tmp) / "state.json")
            self.assertFalse(cache.quick_valid(path, art))
            self.assertTrue(cache.verify(path, art))
            self.assertTrue(ai_setup.VerifiedCache(Path(tmp) / "state.json").quick_valid(path, art))
            path.write_bytes(b"outro")
            self.assertFalse(cache.verify(path, art))


class LlamaTest(unittest.TestCase):
    def test_version_and_variant(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "llama-server.exe"
            self.assertFalse(ai_setup.llama_ok(exe, "cpu", version_run))
            exe.write_text("x")
            self.assertEqual(ai_setup.llama_version(exe, version_run), 10819)
            self.assertTrue(ai_setup.llama_ok(exe, "cpu", version_run))
            self.assertFalse(ai_setup.llama_ok(exe, "cuda", version_run))
            for dll in ("ggml-cuda.dll", "cublas64_12.dll", "cudart64_12.dll"):
                (Path(tmp) / dll).write_text("x")
            self.assertTrue(ai_setup.llama_ok(exe, "cuda", version_run))

    def test_extract_flat_and_unsafe_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            first = base / "a.zip"
            llama_zip(first, nested=True)
            second = base / "b.zip"
            with zipfile.ZipFile(second, "w") as archive:
                archive.writestr("cudart64_12.dll", b"rt")
            target = base / "llama.new"
            target.mkdir()
            exe = ai_setup.extract_flat([first, second], target)
            self.assertEqual(exe, target / "llama-server.exe")
            self.assertTrue((target / "cudart64_12.dll").is_file())
            bad = base / "bad.zip"
            with zipfile.ZipFile(bad, "w") as archive:
                archive.writestr("../fora.exe", b"x")
            with self.assertRaises(ai_setup.SetupError):
                ai_setup.extract_flat([bad], target)


class FlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.base = base
        self.zip_bytes = llama_zip(base / "src.zip")
        self.qwen = art_for("qwen_3b", "qwen2.5-coder-3b-instruct-q4_k_m.gguf", b"qwen3b" * 1000)
        self.text = art_for("rag_text", ai_setup.RAG_TEXT.name, b"jina-texto")
        self.code = art_for("rag_code", ai_setup.RAG_CODE.name, b"jina-codigo")
        self.cpu = art_for("llama_cpu", "llama-cpu.zip", self.zip_bytes)
        self.web = FakeWeb({a.url: d for a, d in (
            (self.qwen, b"qwen3b" * 1000), (self.text, b"jina-texto"), (self.code, b"jina-codigo"),
            (self.cpu, self.zip_bytes))})
        local = base / "Local"
        ai_dir = local / "CodeBridge" / "ai"
        for patcher in (
            patch.dict(os.environ, {"LOCALAPPDATA": str(local), llama_binary.ENV_VAR: "",
                                    "CODEBRIDGE_AI_COMPUTE": ""}),
            patch.dict(ai_setup.QWEN, {"3B": self.qwen}),
            patch.object(ai_setup, "RAG_TEXT", self.text),
            patch.object(ai_setup, "RAG_CODE", self.code),
            patch.object(ai_setup, "LLAMA_CPU", self.cpu),
            patch.object(srv, "AI_DIR", ai_dir),
            patch.object(srv, "MODEL_CHOICE_FILE", ai_dir / "model.json"),
            patch.object(llama_binary, "USER_LLAMA_DIR", local / "CodeBridge" / "llama"),
            patch.object(llama_binary, "LEGACY_LLAMA_SERVER", base / "nao" / "llama-server.exe"),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.hw = ai_setup.Hardware(ram_mb=8000, cpu_count=8, disk_free_mb=100000)

    def make(self, events, **kwargs):
        options = dict(emit=events.append, hardware=self.hw, opener=self.web,
                       version_run=version_run,
                       local_test=lambda exe, model, cancelled: "respondeu OK (CPU)",
                       rag_test=lambda exe: "texto 1024 e código 896 dimensões")
        options.update(kwargs)
        return ai_setup.Setup(**options)

    def test_full_install_then_nothing_to_do(self):
        events = []
        self.assertEqual(self.make(events).run(), ai_setup.EXIT_OK, events[-1])
        local = self.base / "Local" / "CodeBridge"
        self.assertTrue((local / "llama" / "llama-server.exe").is_file())
        self.assertEqual((local / "ai" / "models" / self.qwen.name).read_bytes(), b"qwen3b" * 1000)
        choice = json.loads((local / "ai" / "model.json").read_text(encoding="utf-8"))
        self.assertEqual(choice["name"], "Qwen2.5-Coder 3B")
        self.assertEqual(json.loads((local / "ai" / "compute.json").read_text()), {"compute": "CPU"})
        self.assertEqual(json.loads((local / "ai" / "setup.json").read_text(encoding="utf-8"))["tests"], "ok")
        self.assertEqual(llama_binary.llama_server_path(), local / "llama" / "llama-server.exe")
        self.assertEqual(srv.selected_model(), local / "ai" / "models" / self.qwen.name)
        self.assertFalse(list((local / "downloads").glob("*")))
        self.assertEqual(ai_setup.quick_check(hardware=self.hw, version_run=version_run), [])

        calls = len(self.web.calls)
        events = []
        self.assertEqual(self.make(events).run(), ai_setup.EXIT_OK)
        self.assertEqual(len(self.web.calls), calls)  # nada baixado de novo
        states = [e for e in events if e[0] == "step" and e[2] == "ok"]
        self.assertTrue(any("já instalado" in e[3] for e in states))

    def test_offline_package_and_failed_test(self):
        package = self.base / "CodeBridge-IAs"
        package.mkdir()
        for art, data in ((self.qwen, b"qwen3b" * 1000), (self.text, b"jina-texto"),
                          (self.code, b"jina-codigo"), (self.cpu, self.zip_bytes)):
            (package / art.name).write_bytes(data)

        def broken_rag(exe):
            raise RuntimeError("sem memória")
        events = []
        setup = self.make(events, source_dir=package, opener=lambda *a, **k: self.fail("baixou"),
                          rag_test=broken_rag)
        self.assertEqual(setup.run(), ai_setup.EXIT_TEST_FAILED)
        self.assertIn("RAG: sem memória", events[-1][2])
        self.assertTrue(srv.selected_model().is_file())

    def test_not_enough_disk(self):
        self.hw.disk_free_mb = 0
        events = []
        self.assertEqual(self.make(events).run(), ai_setup.EXIT_ERROR)
        self.assertIn("Espaço insuficiente", events[-1][2])

    def test_keeps_previous_choice_and_fixes_gpu_mode(self):
        from rag.models import compute_preference
        compute_preference.save_compute("GPU")
        srv.MODEL_CHOICE_FILE.parent.mkdir(parents=True, exist_ok=True)
        srv.MODEL_CHOICE_FILE.write_text(json.dumps({"file": str(ai_setup.qwen_target("3B"))}))
        self.hw.ram_mb = 32000  # pediria o 7B, mas o 3B ja escolhido fica
        events = []
        self.assertEqual(self.make(events).run(), ai_setup.EXIT_OK, events[-1])
        self.assertIn("mantido o Qwen 3B", [e for e in events if e[0] == "plan"][0][1])
        self.assertEqual(compute_preference.load_compute(), "CPU")  # sem placa: GPU vira CPU


class LocalServerModelTest(unittest.TestCase):
    def test_names_choice_and_requirements(self):
        self.assertEqual(srv.model_name_for("qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"), "Qwen2.5-Coder 1.5B")
        self.assertEqual(srv.model_name_for(srv.DEFAULT_MODEL_FILE), "Qwen2.5-Coder 7B")
        with tempfile.TemporaryDirectory() as tmp:
            choice = Path(tmp) / "model.json"
            self.assertEqual(srv.selected_model(choice), srv.DEFAULT_MODEL_FILE)
            choice.write_text(json.dumps({"file": str(Path(tmp) / "q3.gguf")}))
            self.assertEqual(srv.selected_model(choice), Path(tmp) / "q3.gguf")
            model = Path(tmp) / "q3.gguf"
            model.write_bytes(b"x" * (2 * 1048576))
            self.assertEqual(srv.requirements_for(model), (2 + srv.VRAM_OVERHEAD_MB, 2 + srv.CPU_OVERHEAD_MB))
        self.assertEqual(srv.requirements_for(Path("nao_existe.gguf")),
                         (srv.REQUIRED_FREE_VRAM_MB, srv.REQUIRED_FREE_RAM_CPU_MB))

    def test_small_model_starts_where_7b_would_not(self):
        box = {"vram_total_mb": None, "vram_used_mb": None, "ram_total_mb": 8000, "ram_used_mb": 4500}
        self.assertIsNotNone(srv.choose_device("CPU", box)[1])  # 7B: falta RAM
        self.assertEqual(srv.choose_device("CPU", box, need=(2500, 3500)), ("CPU", None))

    def test_status_card_shows_chosen_size(self):
        class Server:
            state, model = "OFF", Path("qwen2.5-coder-3b-instruct-q4_k_m.gguf")

            def is_installed(self):
                return True
        rows = ai_status.describe(Server(), [])
        self.assertEqual(rows[0]["model"], "Qwen 3B")
        proc = ai_status.parse_cmdline(["x", "-m", "qwen2.5-coder-3b-instruct-q4_k_m.gguf", "-ngl", "0"])
        self.assertEqual(ai_status._device_of([proc], ai_status.MODELS[0][3]), "CPU")


class DialogTest(unittest.TestCase):
    def test_dialog_shows_events(self):
        from PySide6.QtWidgets import QApplication
        QApplication.instance() or QApplication([])
        dialog = ai_setup.dialog_class()(lambda emit: None, auto_start=False)
        self.addCleanup(dialog.deleteLater)
        dialog.on_event(("plan", "Plano: tudo no processador."))
        dialog.on_event(("step", "llama", "run", "baixando"))
        dialog.on_event(("progress", 50, 100, "Baixando · 1,0 de 2,0 GB"))
        self.assertEqual(dialog.progress.value(), 500)
        self.assertEqual(dialog.icons["llama"].text(), "◔")
        dialog.on_event(("step", "llama", "ok", "instalado"))
        self.assertEqual(dialog.icons["llama"].text(), "✔")
        self.assertEqual(dialog.details["llama"].text(), "instalado")
        dialog.on_event(("done", ai_setup.EXIT_ERROR, "Falhou"))
        self.assertEqual(dialog.action_button.text(), "Fechar")
        self.assertFalse(dialog.retry_button.isHidden())
        self.assertEqual(dialog.result_code(), ai_setup.EXIT_ERROR)
        self.assertEqual(dialog.plan_label.text(), "Plano: tudo no processador.")


if __name__ == "__main__":
    unittest.main()
