import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app_rewrite"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from config_store import ConfigStore
from secure_tunnel_manager import SecureTunnelManager

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

API_KEYS_URL = "https://platform.openai.com/settings/organization/api-keys"
TUNNELS_URL = "https://platform.openai.com/settings/organization/tunnels"
CHATGPT_URL = "https://chatgpt.com/"


def open_url(url):
    webbrowser.open(url, new=2)


def copy_text(text):
    QApplication.clipboard().setText(str(text or ""))


class IntroPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("ConfiguraÃ§Ã£o empresarial do CodeBridge")
        self.setSubTitle(
            "Este assistente configura a chave da organizaÃ§Ã£o, o OpenAI Tunnel "
            "e mostra como criar o MCP do CodeBridge no ChatGPT."
        )
        layout = QVBoxLayout(self)
        text = QLabel(
            "Antes de continuar, tenha acesso Ã  organizaÃ§Ã£o da empresa na "
            "OpenAI Platform. A API key ficarÃ¡ protegida no Windows por DPAPI "
            "e nÃ£o serÃ¡ gravada no GitHub nem em arquivo de texto."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        self.company = QLineEdit()
        self.company.setPlaceholderText("Ex.: Empresa")
        self.plugin = QLineEdit("CodeBridge MCP")
        form = QFormLayout()
        form.addRow("Empresa:", self.company)
        form.addRow("Nome do plugin:", self.plugin)
        layout.addLayout(form)
        self.registerField("company*", self.company)
        self.registerField("plugin*", self.plugin)


class OpenAIPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("API key e OpenAI Tunnel")
        self.setSubTitle("Crie uma chave da organizaÃ§Ã£o e um tÃºnel para este computador.")
        layout = QVBoxLayout(self)
        info = QLabel(
            "1. Clique em Criar API key e crie uma chave para a empresa.\n"
            "2. Clique em Criar Tunnel e crie um tÃºnel para esta mÃ¡quina.\n"
            "3. Cole abaixo a API key e o Tunnel ID (formato tunnel_...)."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        buttons = QHBoxLayout()
        api_btn = QPushButton("Criar API key")
        api_btn.clicked.connect(lambda: open_url(API_KEYS_URL))
        tunnel_btn = QPushButton("Criar Tunnel")
        tunnel_btn.clicked.connect(lambda: open_url(TUNNELS_URL))
        buttons.addWidget(api_btn)
        buttons.addWidget(tunnel_btn)
        layout.addLayout(buttons)
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("Cole a API key da organizaÃ§Ã£o")
        self.tunnel_id = QLineEdit()
        self.tunnel_id.setPlaceholderText("tunnel_...")
        form = QFormLayout()
        form.addRow("API key:", self.api_key)
        form.addRow("Tunnel ID:", self.tunnel_id)
        layout.addLayout(form)
        warning = QLabel(
            "Importante: esta API key autentica o tunnel-client local. "
            "Ela NÃƒO deve ser colada como senha do plugin no ChatGPT."
        )
        warning.setWordWrap(True)
        layout.addWidget(warning)
        self.registerField("api_key", self.api_key)
        self.registerField("tunnel_id*", self.tunnel_id)

    def validatePage(self):
        key = self.api_key.text().strip()
        tunnel_id = self.tunnel_id.text().strip()
        if len(key) < 20 or any(ch.isspace() for ch in key):
            QMessageBox.warning(
                self, "API key invÃ¡lida",
                "Cole a API key completa da organizaÃ§Ã£o, sem espaÃ§os.",
            )
            return False
        if not tunnel_id.startswith("tunnel_") or any(ch.isspace() for ch in tunnel_id):
            QMessageBox.warning(
                self, "Tunnel ID invÃ¡lido",
                "O Tunnel ID deve ter o formato tunnel_...",
            )
            return False
        try:
            config = ConfigStore()
            config.save_company(
                self.field("company"), tunnel_id, self.field("plugin")
            )
            manager = SecureTunnelManager(config)
            manager.save_runtime_key(key)
            manager.prepare_profile()
        except Exception as exc:
            QMessageBox.critical(
                self, "NÃ£o foi possÃ­vel configurar o tÃºnel",
                f"{type(exc).__name__}: {exc}\n\n"
                "Confira a API key, o Tunnel ID e tente novamente.",
            )
            return False
        finally:
            self.api_key.clear()
            key = None
        return True


class ChatGPTPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Criar o MCP no ChatGPT")
        self.setSubTitle(
            "Agora vincule o ChatGPT ao OpenAI Tunnel que vocÃª acabou de configurar."
        )
        layout = QVBoxLayout(self)
        self.instructions = QLabel()
        self.instructions.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.instructions.setWordWrap(True)
        layout.addWidget(self.instructions)
        row = QHBoxLayout()
        chatgpt = QPushButton("Abrir ChatGPT")
        chatgpt.clicked.connect(lambda: open_url(CHATGPT_URL))
        copy_name = QPushButton("Copiar nome")
        copy_name.clicked.connect(lambda: copy_text(self.field("plugin")))
        copy_tunnel = QPushButton("Copiar Tunnel ID")
        copy_tunnel.clicked.connect(lambda: copy_text(self.field("tunnel_id")))
        row.addWidget(chatgpt)
        row.addWidget(copy_name)
        row.addWidget(copy_tunnel)
        layout.addLayout(row)
        logo_btn = QPushButton("Abrir pasta do logo")
        logo_btn.clicked.connect(self.open_logo_folder)
        layout.addWidget(logo_btn)

    def initializePage(self):
        plugin = str(self.field("plugin") or "CodeBridge MCP")
        tunnel_id = str(self.field("tunnel_id") or "")
        logo = ROOT / "assets" / "codebridge_plugin_256.png"
        self.instructions.setText(
            "No ChatGPT:\n\n"
            "1. Abra ConfiguraÃ§Ãµes > Plugins > Novo plugin.\n"
            f"2. Nome: {plugin}\n"
            "3. DescriÃ§Ã£o sugerida: CodeBridge para execuÃ§Ã£o segura de comandos "
            "no computador local.\n"
            f"4. Ãcone: {logo}\n"
            "5. Em ConexÃ£o, selecione o OpenAI Tunnel criado para esta mÃ¡quina.\n"
            f"   Tunnel ID: {tunnel_id}\n"
            "6. NÃ£o reutilize a API key da organizaÃ§Ã£o como credencial do plugin. "
            "Ela fica somente neste computador para o tunnel-client.\n"
            "7. Salve o plugin.\n\n"
            "Teste final no ChatGPT:\n"
            "Use o CodeBridge e chame codebridge_ping com desafio TESTE_INSTALACAO."
        )

    def open_logo_folder(self):
        logo = ROOT / "assets" / "codebridge_plugin_256.png"
        try:
            subprocess.Popen(["explorer.exe", f"/select,{logo}"])
        except Exception:
            os.startfile(str(logo.parent))


class FinishPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("ConfiguraÃ§Ã£o concluÃ­da")
        self.setSubTitle(
            "O CodeBridge estÃ¡ instalado e a configuraÃ§Ã£o empresarial foi salva."
        )
        layout = QVBoxLayout(self)
        info = QLabel(
            "Ao iniciar o CodeBridge, ele sobe o MCP local e o Secure Tunnel "
            "da empresa. Depois, faÃ§a o teste codebridge_ping no ChatGPT."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        self.launch = QCheckBox("Abrir o CodeBridge ao finalizar")
        self.launch.setChecked(True)
        layout.addWidget(self.launch)


class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Configurar CodeBridge")
        self.resize(760, 520)
        icon = ROOT / "assets" / "codebridge.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.intro = IntroPage()
        self.openai = OpenAIPage()
        self.chatgpt = ChatGPTPage()
        self.finish_page = FinishPage()
        self.addPage(self.intro)
        self.addPage(self.openai)
        self.addPage(self.chatgpt)
        self.addPage(self.finish_page)
        current = ConfigStore().load_company()
        if current.get("company_name"):
            self.intro.company.setText(current["company_name"])
        if current.get("plugin_name"):
            self.intro.plugin.setText(current["plugin_name"])
        if current.get("tunnel_id"):
            self.openai.tunnel_id.setText(current["tunnel_id"])

    def accept(self):
        launch = self.finish_page.launch.isChecked()
        super().accept()
        if launch:
            pythonw = ROOT / "runtime" / "python" / "pythonw.exe"
            if not pythonw.is_file():
                pythonw = Path(sys.executable)
            main = ROOT / "app_rewrite" / "main.py"
            subprocess.Popen(
                [str(pythonw), str(main)],
                cwd=str(ROOT / "app_rewrite"),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("CodeBridge Setup")
    wizard = SetupWizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
