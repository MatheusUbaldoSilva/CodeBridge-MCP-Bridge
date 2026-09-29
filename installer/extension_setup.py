# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
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
            f"Pasta da extensÃƒÂ£o nÃƒÂ£o encontrada: {EXT}"
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
            "ExtensÃƒÂ£o ChatGPT Timer Ã¢â‚¬â€ CodeBridge"
        )
        self.resize(780, 620)

        icon = ROOT / "assets" / "codebridge.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("ExtensÃƒÂ£o ChatGPT Timer")
        title.setStyleSheet(
            "font-size:20pt;"
            "font-weight:700;"
            "color:#f3f7fa"
        )
        layout.addWidget(title)

        intro = QLabel(
            "NecessÃƒÂ¡ria para detectar o fim da resposta "
            "do ChatGPT e concluir o cronÃƒÂ´metro. "
            "Depois de carregar a extensÃƒÂ£o uma vez, "
            "as atualizaÃƒÂ§ÃƒÂµes futuras do CodeBridge "
            "mantÃƒÂªm esta mesma pasta."
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
            "<b>Primeira ativaÃƒÂ§ÃƒÂ£o</b><br><br>"
            "1. Abra as extensÃƒÂµes do Chrome.<br>"
            "2. Ative <b>Modo do desenvolvedor</b>.<br>"
            "3. Clique em <b>Carregar sem compactaÃƒÂ§ÃƒÂ£o</b>.<br>"
            "4. Selecione a pasta oficial mostrada abaixo.<br>"
            "5. Volte ao CodeBridge e clique em "
            "<b>Testar extensÃƒÂ£o</b>.<br><br>"
            "<b>Se ela jÃƒÂ¡ aponta para a pasta oficial</b><br><br>"
            "Depois de uma atualizaÃƒÂ§ÃƒÂ£o, abra "
            "<b>chrome://extensions</b>, encontre "
            "<b>CodeBridge ChatGPT Timer</b>, clique em "
            "<b>Recarregar Ã¢â€ Â»</b> e teste novamente.<br><br>"
            "<b>MigraÃƒÂ§ÃƒÂ£o de uma pasta antiga</b><br><br>"
            "Remova uma ÃƒÂºnica vez a extensÃƒÂ£o antiga antes de "
            "usar <b>Carregar sem compactaÃƒÂ§ÃƒÂ£o</b> com a pasta oficial. "
            "Depois disso, nÃƒÂ£o serÃƒÂ¡ necessÃƒÂ¡rio remover novamente."
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
            "Abrir extensÃƒÂµes do Chrome"
        )
        button.clicked.connect(
            lambda: self._safe_open(
                "chrome://extensions/"
            )
        )
        row.addWidget(button)

        button = QPushButton(
            "Abrir pasta da extensÃƒÂ£o"
        )
        button.clicked.connect(self.folder)
        row.addWidget(button)

        layout.addLayout(row)

        row = QHBoxLayout()

        button = QPushButton("Testar extensÃƒÂ£o")
        button.setDefault(True)
        button.clicked.connect(self.refresh)
        row.addWidget(button)

        button = QPushButton("Abrir ChatGPT")
        button.clicked.connect(
            lambda: self._safe_open(
                "https://chatgpt.com/"
            )
        )
        row.addWidget(button)

        layout.addLayout(row)

        note = QLabel(
            "O teste confirma o caminho e a versÃƒÂ£o registrados pelo "
            "Chrome, o Companion local em 127.0.0.1:8768 e o "
            "heartbeat enviado pela prÃƒÂ³pria extensÃƒÂ£o."
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
                "NÃƒÂ£o foi possÃƒÂ­vel abrir",
                f"{type(error).__name__}: {error}",
            )

    def folder(self):
        try:
            open_folder()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Pasta nÃƒÂ£o encontrada",
                f"{type(error).__name__}: {error}",
            )

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

        lines = [
            "<b>Estado atual</b>",
            "",
            "VersÃƒÂ£o embutida: "
            + (expected_version or "desconhecida"),
        ]

        if official:
            primary = official[0]
            enabled = record_enabled(primary)

            lines.append(
                "Chrome: extensÃƒÂ£o detectada na pasta oficial"
            )
            lines.append(
                "Perfil: " + primary["profile"]
            )
            lines.append(
                "VersÃƒÂ£o detectada: "
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
                    "Estado registrado: nÃƒÂ£o determinado"
                )

            if (
                expected_version
                and primary.get("version")
                and primary["version"] != expected_version
            ):
                lines.append(
                    "AÃƒÂ§ÃƒÂ£o: clique em Recarregar Ã¢â€ Â» "
                    "no chrome://extensions"
                )
        else:
            lines.append(
                "Chrome: extensÃƒÂ£o ainda nÃƒÂ£o detectada "
                "na pasta oficial"
            )
            lines.append(
                "AÃƒÂ§ÃƒÂ£o: use Carregar sem compactaÃƒÂ§ÃƒÂ£o "
                "uma ÃƒÂºnica vez"
            )

        if legacy:
            lines.append(
                "MigraÃƒÂ§ÃƒÂ£o: existe registro da extensÃƒÂ£o "
                "apontando para outro caminho"
            )
            if official:
                lines.append(
                    "AÃƒÂ§ÃƒÂ£o: remova o registro antigo para evitar "
                    "duas extensÃƒÂµes ativas"
                )
            else:
                lines.append(
                    "AÃƒÂ§ÃƒÂ£o: remova a extensÃƒÂ£o antiga antes de "
                    "carregar a pasta oficial"
                )

        lines.append(
            "Companion 127.0.0.1:8768: "
            + ("OK" if companion_ok else "indisponÃƒÂ­vel")
        )

        if heartbeat_ok:
            heartbeat_version = heartbeat.get("version") or "desconhecida"
            heartbeat_age = heartbeat.get("age_seconds")
            lines.append("Heartbeat: conectado")
            lines.append(
                "VersÃƒÂ£o ativa da extensÃƒÂ£o: " + heartbeat_version
            )
            if heartbeat_age is not None:
                lines.append(
                    "ÃƒÅ¡ltimo heartbeat: "
                    + f"{float(heartbeat_age):.1f}s"
                )
        else:
            lines.append("Heartbeat: nÃƒÂ£o detectado")
            if official and companion_ok:
                lines.append(
                    "AÃƒÂ§ÃƒÂ£o: recarregue a extensÃƒÂ£o no Chrome "
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
            headline = "Ã¢â€”Â ExtensÃƒÂ£o conectada"
            color = "#79d99a"
        elif official:
            headline = "Ã¢â€”Â ExtensÃƒÂ£o requer verificaÃƒÂ§ÃƒÂ£o"
            color = "#f2c879"
        else:
            headline = "Ã¢â€”Â AtivaÃƒÂ§ÃƒÂ£o necessÃƒÂ¡ria"
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
