# -*- coding: utf-8 -*-
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app_rewrite"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from constants import APP_VERSION, DATA_DIR

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QColor, QIcon, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

try:
    import psutil
except Exception:
    psutil = None


REPOSITORY = "MatheusUbaldoSilva/CodeBridge-MCP-Bridge"
COMMIT_API = f"https://api.github.com/repos/{REPOSITORY}/commits/main"
RAW_ROOT = "https://raw.githubusercontent.com"

DARK_STYLESHEET = """
QWidget {
    background-color: #0b1117;
    color: #e8eef4;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QLabel { color: #dce6ee; }
QPushButton {
    background-color: #0f6f78;
    color: white;
    border: 1px solid #16a5b3;
    border-radius: 6px;
    padding: 8px 14px;
    min-height: 24px;
    font-weight: 600;
}
QPushButton:hover { background-color: #11818c; }
QPushButton:disabled {
    background-color: #24303a;
    color: #788994;
    border-color: #34434f;
}
QProgressBar {
    border: 1px solid #2a3a49;
    border-radius: 5px;
    background: #111922;
    color: #e8eef4;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk {
    background-color: #118b7e;
    border-radius: 4px;
}
"""


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eef4"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111922"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eef4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#18232e"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f6f9"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#117a8b"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLESHEET)


def codebridge_running():
    runtime_file = DATA_DIR / "runtime.json"
    if not runtime_file.is_file():
        return False

    try:
        import json

        payload = json.loads(runtime_file.read_text(encoding="utf-8"))
        pid = int(payload.get("pid") or 0)
    except Exception:
        return False

    if pid <= 0:
        return False

    if psutil is None:
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False

    try:
        process = psutil.Process(pid)
        cmdline = " ".join(process.cmdline()).lower()
        return process.is_running() and "app_rewrite" in cmdline and "main.py" in cmdline
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True
    except Exception:
        return False


class DownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(str)
    failed = Signal(str)

    def run(self):
        try:
            temp_dir = Path(tempfile.gettempdir()) / "CodeBridge-Update"
            temp_dir.mkdir(parents=True, exist_ok=True)
            installer = temp_dir / "CodeBridge-Setup.exe"

            api_request = urllib.request.Request(
                COMMIT_API,
                headers={
                    "User-Agent": "CodeBridge-Updater/2.0",
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(api_request, timeout=30) as response:
                commit = json.loads(response.read().decode("utf-8"))
            commit_sha = str(commit.get("sha") or "").strip()
            if len(commit_sha) != 40:
                raise RuntimeError("Não foi possível resolver o commit mais recente")

            base = f"{RAW_ROOT}/{REPOSITORY}/{commit_sha}/installer/dist"
            hash_url = base + "/CodeBridge-Setup.sha256"
            installer_url = base + "/CodeBridge-Setup.exe"

            hash_request = urllib.request.Request(
                hash_url, headers={"User-Agent": "CodeBridge-Updater/2.0"}
            )
            with urllib.request.urlopen(hash_request, timeout=30) as response:
                expected = response.read().decode("ascii", errors="ignore").strip()
            expected = expected.split()[0].lower()
            if len(expected) != 64:
                raise RuntimeError("Hash SHA-256 publicado é inválido")

            request = urllib.request.Request(
                installer_url,
                headers={"User-Agent": "CodeBridge-Updater/2.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                digest = hashlib.sha256()
                with open(installer, "wb") as handle:
                    while True:
                        chunk = response.read(1024 * 256)
                        if not chunk:
                            break
                        handle.write(chunk)
                        digest.update(chunk)
                        received += len(chunk)
                        if total:
                            self.progress.emit(min(100, int(received * 100 / total)))

            actual = digest.hexdigest().lower()
            if actual != expected:
                installer.unlink(missing_ok=True)
                raise RuntimeError(
                    "O SHA-256 do instalador baixado não corresponde ao publicado"
                )

            self.progress.emit(100)
            self.finished.emit(str(installer))
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class UpdaterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.thread = None
        self.worker = None

        self.setWindowTitle("Atualizar CodeBridge")
        self.resize(520, 280)

        icon = ROOT / "assets" / "codebridge.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        layout = QVBoxLayout(self)

        title = QLabel("Atualizar CodeBridge")
        title.setStyleSheet("font-size:18pt; font-weight:700; color:#f3f7fa;")
        layout.addWidget(title)

        text = QLabel(
            f"Versão instalada: {APP_VERSION}\n\n"
            "Este atualizador baixa o CodeBridge-Setup.exe mais recente do GitHub, "
            "confere o SHA-256 publicado e executa o instalador em modo de atualização. "
            "A configuração da empresa, API key protegida, Tunnel ID e SSH são mantidos."
        )
        text.setWordWrap(True)
        layout.addWidget(text)

        warning = QLabel(
            "Feche o CodeBridge antes de atualizar. O atualizador não apaga "
            "os dados de configuração."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#f2c879; padding:6px 0;")
        layout.addWidget(warning)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.button = QPushButton("Baixar e atualizar")
        self.button.clicked.connect(self.start_update)
        layout.addWidget(self.button)

    def start_update(self):
        if codebridge_running():
            QMessageBox.warning(
                self,
                "CodeBridge está aberto",
                "Feche o CodeBridge completamente e clique novamente em "
                "Baixar e atualizar.",
            )
            return

        self.button.setEnabled(False)
        self.button.setText("Baixando atualização...")
        self.progress.setValue(0)

        self.thread = QThread(self)
        self.worker = DownloadWorker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.progress.setValue)
        self.worker.finished.connect(self.download_finished)
        self.worker.failed.connect(self.download_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.start()

    def download_finished(self, installer):
        self.button.setText("Atualização pronta")
        try:
            subprocess.Popen([installer], cwd=str(Path(installer).parent))
        except Exception as exc:
            self.button.setEnabled(True)
            self.button.setText("Baixar e atualizar")
            QMessageBox.critical(
                self,
                "Falha ao abrir atualização",
                f"{type(exc).__name__}: {exc}",
            )
            return
        QApplication.instance().quit()

    def download_failed(self, message):
        self.button.setEnabled(True)
        self.button.setText("Tentar novamente")
        QMessageBox.critical(
            self,
            "Falha ao baixar atualização",
            message,
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CodeBridge Updater")
    apply_dark_theme(app)
    window = UpdaterWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
