# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "browser_extension" / "codebridge_chatgpt_timer"
MANIFEST = EXT / "manifest.json"
DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "CodeBridge-MCP-Bridge"
)
VERIFIED_STATE = DATA_DIR / "extension_verified.json"
COMPANION_HEALTH = "http://127.0.0.1:8768/healthz"

STYLE = """
QWidget {
    background: #0b1117;
    color: #e8eef4;
    font-family: 'Segoe UI';
    font-size: 10pt;
}
QLabel {
    color: #dce6ee;
}
QPushButton {
    background: #18232e;
    color: #f1f6f9;
    border: 1px solid #304354;
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 24px;
}
QPushButton:default {
    background: #0f6f78;
    border-color: #16a5b3;
    font-weight: 600;
}
"""


def version():
    try:
        return str(
            json.loads(
                MANIFEST.read_text(encoding="utf-8")
            ).get("version")
            or ""
        )
    except Exception:
        return ""


def norm(value):
    text = os.path.expandvars(str(value or "").strip())
    if not text:
        return ""
    return os.path.normcase(os.path.abspath(text))


def chrome_root():
    return (
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "User Data"
    )


def records():
    wanted_path = norm(EXT)
    found = []
    base = chrome_root()

    if not base.is_dir():
        return found

    for profile in base.iterdir():
        if not profile.is_dir():
            continue

        for pref_name in ("Secure Preferences", "Preferences"):
            pref_file = profile / pref_name
            if not pref_file.is_file():
                continue

            try:
                data = json.loads(
                    pref_file.read_text(encoding="utf-8")
                )
            except Exception:
                continue

            settings = (
                data.get("extensions", {})
                .get("settings", {})
            )

            for extension_id, item in settings.items():
                if not isinstance(item, dict):
                    continue

                manifest = item.get("manifest") or {}
                path = str(item.get("path") or "")
                normalized = norm(path)
                name = str(manifest.get("name") or "")

                if (
                    name != "CodeBridge ChatGPT Timer"
                    and normalized != wanted_path
                    and "codebridge_chatgpt_timer"
                    not in normalized.lower()
                ):
                    continue

                found.append(
                    {
                        "profile": profile.name,
                        "id": str(extension_id),
                        "path": path,
                        "version": str(
                            manifest.get("version")
                            or (
                                item.get(
                                    "service_worker_registration_info"
                                )
                                or {}
                            ).get("version")
                            or ""
                        ),
                        "expected": normalized == wanted_path,
                        "state": item.get("state"),
                        "disable_reasons": item.get(
                            "disable_reasons"
                        ),
                    }
                )

    unique = {
        (
            item["profile"],
            item["id"],
            item["path"],
        ): item
        for item in found
    }
    return list(unique.values())


def companion_health():
    try:
        request = urllib.request.Request(
            COMPANION_HEALTH,
            headers={
                "User-Agent": "CodeBridge-Extension-Setup/1.0"
            },
        )
        with urllib.request.urlopen(
            request,
            timeout=1.5,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )
        return bool(
            response.status == 200
            and payload.get("ok") is True
            and payload.get("service")
            == "chatgpt-companion"
        )
    except Exception:
        return False


def extension_heartbeat_status():
    try:
        request = urllib.request.Request(
            "http://127.0.0.1:8768/v1/extension/status",
            headers={
                "User-Agent": "CodeBridge-Extension-Setup/1.0",
                "X-CodeBridge-Companion": "chatgpt-timer-v1",
            },
        )
        with urllib.request.urlopen(
            request,
            timeout=1.5,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )
            status = response.status

        if status != 200 or payload.get("ok") is not True:
            return {}

        extension = payload.get("extension")
        return extension if isinstance(extension, dict) else {}
    except Exception:
        return {}


def verified_state():
    try:
        data = json.loads(
            VERIFIED_STATE.read_text(encoding="utf-8")
        )
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_verified_state(extension_version):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": str(extension_version or ""),
        "path": norm(EXT),
    }
    VERIFIED_STATE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def installer_attention_required():
    expected_version = version()
    official = [
        item
        for item in records()
        if item.get("expected")
    ]

    if not official:
        return True

    usable = [
        item
        for item in official
        if record_enabled(item) is not False
    ]
    if not usable:
        return True

    heartbeat = extension_heartbeat_status()
    heartbeat_id = str(heartbeat.get("extension_id") or "")
    official_ids = {
        str(item.get("id") or "")
        for item in usable
    }
    live_official = bool(
        heartbeat.get("connected")
        and heartbeat_id
        and heartbeat_id in official_ids
        and (
            not expected_version
            or heartbeat.get("version") == expected_version
        )
    )

    if live_official:
        save_verified_state(expected_version)
        return False

    verified = verified_state()
    if verified.get("path") != norm(EXT):
        return True

    if (
        expected_version
        and verified.get("version") != expected_version
    ):
        return True

    return False


def codebridge_launcher():
    pythonw = ROOT / "runtime" / "python" / "pythonw.exe"
    main_py = ROOT / "app_rewrite" / "main.py"
    if not pythonw.is_file():
        raise FileNotFoundError(f"Runtime Python não encontrado: {pythonw}")
    if not main_py.is_file():
        raise FileNotFoundError(f"CodeBridge não encontrado: {main_py}")
    return pythonw, main_py


def start_codebridge():
    if companion_health():
        return True
    pythonw, main_py = codebridge_launcher()
    subprocess.Popen(
        [str(pythonw), str(main_py)],
        cwd=str(ROOT / "tools") if (ROOT / "tools").is_dir() else str(ROOT),
        close_fds=True,
    )
    return True


def ensure_codebridge(timeout=20.0):
    if companion_health():
        return True
    try:
        start_codebridge()
    except Exception:
        return False
    deadline = time.monotonic() + max(1.0, float(timeout))
    while time.monotonic() < deadline:
        if companion_health():
            return True
        time.sleep(0.4)
    return companion_health()


def chrome_executable():
    candidates = [
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def open_url(url):
    chrome = chrome_executable()

    if url.startswith("chrome://") and chrome is not None:
        subprocess.Popen(
            [str(chrome), "--new-tab", url],
            close_fds=True,
        )
        return

    os.startfile(url)


def open_folder():
    if not EXT.is_dir():
        raise FileNotFoundError(
            f"Pasta da extensão não encontrada: {EXT}"
        )
    os.startfile(str(EXT))


def record_enabled(record):
    state = record.get("state")
    disable_reasons = record.get("disable_reasons")

    if disable_reasons:
        return False

    if state is None:
        return None

    return state == 1


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(
            "Extensão ChatGPT Timer — CodeBridge"
        )
        self.resize(780, 620)

        icon = ROOT / "assets" / "codebridge.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("Extensão ChatGPT Timer")
        title.setStyleSheet(
            "font-size:20pt;"
            "font-weight:700;"
            "color:#f3f7fa"
        )
        layout.addWidget(title)

        intro = QLabel(
            "Necessária para detectar o fim da resposta "
            "do ChatGPT e concluir o cronômetro. "
            "Depois de carregar a extensão uma vez, "
            "as atualizações futuras do CodeBridge "
            "mantêm esta mesma pasta."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.status.setStyleSheet(
            "background:#111922;"
            "border:1px solid #2a3a49;"
            "border-radius:7px;"
            "padding:12px"
        )
        layout.addWidget(self.status)

        steps = QLabel(
            "<b>Primeira ativação</b><br><br>"
            "1. Abra as extensões do Chrome.<br>"
            "2. Ative <b>Modo do desenvolvedor</b>.<br>"
            "3. Clique em <b>Carregar sem compactação</b>.<br>"
            "4. Selecione a pasta oficial mostrada abaixo.<br>"
            "5. Volte ao CodeBridge e clique em "
            "<b>Testar extensão</b>.<br><br>"
            "<b>Se ela já aponta para a pasta oficial</b><br><br>"
            "Depois de uma atualização, abra "
            "<b>chrome://extensions</b>, encontre "
            "<b>CodeBridge ChatGPT Timer</b>, clique em "
            "<b>Recarregar ↻</b> e teste novamente.<br><br>"
            "<b>Migração de uma pasta antiga</b><br><br>"
            "Remova uma única vez a extensão antiga antes de "
            "usar <b>Carregar sem compactação</b> com a pasta oficial. "
            "Depois disso, não será necessário remover novamente."
        )
        steps.setWordWrap(True)
        layout.addWidget(steps)

        path_label = QLabel(
            "<b>Pasta oficial:</b><br>"
            + str(EXT)
        )
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_label.setStyleSheet("color:#9fc4d8")
        layout.addWidget(path_label)

        row = QHBoxLayout()

        button = QPushButton(
            "Abrir extensões do Chrome"
        )
        button.clicked.connect(
            lambda: self._safe_open(
                "chrome://extensions/"
            )
        )
        row.addWidget(button)

        button = QPushButton(
            "Abrir pasta da extensão"
        )
        button.clicked.connect(self.folder)
        row.addWidget(button)

        layout.addLayout(row)

        row = QHBoxLayout()

        self.start_button = QPushButton("Iniciar CodeBridge")
        self.start_button.clicked.connect(self.start_runtime)
        row.addWidget(self.start_button)

        self.test_button = QPushButton("Testar extensão")
        self.test_button.setDefault(True)
        self.test_button.clicked.connect(self.refresh)
        row.addWidget(self.test_button)

        button = QPushButton("Abrir ChatGPT")
        button.clicked.connect(
            lambda: self._safe_open(
                "https://chatgpt.com/"
            )
        )
        row.addWidget(button)

        layout.addLayout(row)

        note = QLabel(
            "O teste confirma o caminho e a versão registrados pelo "
            "Chrome, o Companion local em 127.0.0.1:8768 e o "
            "heartbeat enviado pela própria extensão."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#f2c879")
        layout.addWidget(note)

        self.refresh()

    def _safe_open(self, url):
        try:
            open_url(url)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Não foi possível abrir",
                f"{type(error).__name__}: {error}",
            )

    def folder(self):
        try:
            open_folder()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Pasta não encontrada",
                f"{type(error).__name__}: {error}",
            )

    def start_runtime(self):
        self.start_button.setEnabled(False)
        self.start_button.setText("Iniciando CodeBridge...")
        QApplication.processEvents()
        if ensure_codebridge(timeout=20.0):
            self.refresh()
            return
        self.start_button.setEnabled(True)
        self.start_button.setText("Iniciar CodeBridge")
        QMessageBox.warning(
            self,
            "CodeBridge ainda não está pronto",
            "Não foi possível detectar o Companion local em 127.0.0.1:8768. "
            "Confirme a janela de permissão do Windows e tente novamente.",
        )
        self.refresh()


    def refresh(self):
        expected_version = version()
        found = records()
        official = [
            item
            for item in found
            if item.get("expected")
        ]
        legacy = [
            item
            for item in found
            if not item.get("expected")
            and record_enabled(item) is not False
        ]
        companion_ok = companion_health()
        heartbeat = extension_heartbeat_status()
        heartbeat_ok = bool(heartbeat.get("connected"))

        self.test_button.setEnabled(companion_ok)
        self.start_button.setEnabled(not companion_ok)
        self.start_button.setText(
            "CodeBridge aberto" if companion_ok else "Iniciar CodeBridge"
        )

        lines = [
            "<b>Estado atual</b>",
            "",
            "Versão embutida: "
            + (expected_version or "desconhecida"),
        ]

        if official:
            primary = official[0]
            enabled = record_enabled(primary)

            lines.append(
                "Chrome: extensão detectada na pasta oficial"
            )
            lines.append(
                "Perfil: " + primary["profile"]
            )
            lines.append(
                "Versão detectada: "
                + (
                    primary.get("version")
                    or "desconhecida"
                )
            )

            if enabled is True:
                lines.append(
                    "Estado registrado: habilitada"
                )
            elif enabled is False:
                lines.append(
                    "Estado registrado: desabilitada"
                )
            else:
                lines.append(
                    "Estado registrado: não determinado"
                )

            if (
                expected_version
                and primary.get("version")
                and primary["version"] != expected_version
            ):
                lines.append(
                    "Ação: clique em Recarregar ↻ "
                    "no chrome://extensions"
                )
        else:
            lines.append(
                "Chrome: extensão ainda não detectada "
                "na pasta oficial"
            )
            lines.append(
                "Ação: use Carregar sem compactação "
                "uma única vez"
            )

        if legacy:
            lines.append(
                "Migração: existe registro da extensão "
                "apontando para outro caminho"
            )
            if official:
                lines.append(
                    "Ação: remova o registro antigo para evitar "
                    "duas extensões ativas"
                )
            else:
                lines.append(
                    "Ação: remova a extensão antiga antes de "
                    "carregar a pasta oficial"
                )

        lines.append(
            "CodeBridge: "
            + ("ABERTO" if companion_ok else "FECHADO")
        )

        lines.append(
            "Companion 127.0.0.1:8768: "
            + ("ONLINE" if companion_ok else "OFFLINE")
        )

        if heartbeat_ok:
            heartbeat_version = heartbeat.get("version") or "desconhecida"
            heartbeat_age = heartbeat.get("age_seconds")
            lines.append("Heartbeat: conectado")
            lines.append(
                "Versão ativa da extensão: " + heartbeat_version
            )
            if heartbeat_age is not None:
                lines.append(
                    "Último heartbeat: "
                    + f"{float(heartbeat_age):.1f}s"
                )
        else:
            lines.append("Heartbeat: não detectado")
            if official and companion_ok:
                lines.append(
                    "Ação: recarregue a extensão no Chrome "
                    "e teste novamente"
                )

        official_ids = {
            str(item.get("id") or "")
            for item in official
            if record_enabled(item) is not False
        }
        environment_ready = bool(
            official_ids
            and expected_version
            and companion_ok
            and heartbeat_ok
            and heartbeat.get("version") == expected_version
            and str(heartbeat.get("extension_id") or "")
            in official_ids
        )

        if environment_ready:
            save_verified_state(expected_version)
            headline = "● Extensão conectada"
            color = "#79d99a"
        elif official:
            headline = "● Extensão requer verificação"
            color = "#f2c879"
        else:
            headline = "● Ativação necessária"
            color = "#f2c879"

        self.status.setText(
            "<span style='color:"
            + color
            + ";font-weight:700'>"
            + headline
            + "</span><br><br>"
            + "<br>".join(lines)
        )


def main():
    if "--needs-attention" in sys.argv:
        return 10 if installer_attention_required() else 0

    if "--ensure-codebridge" in sys.argv:
        return 0 if ensure_codebridge(timeout=20.0) else 12

    app = QApplication(sys.argv)
    app.setApplicationName(
        "CodeBridge Extension Assistant"
    )
    app.setStyleSheet(STYLE)

    window = Window()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
