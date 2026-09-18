# -*- coding: utf-8 -*-
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
from PySide6.QtGui import QColor, QIcon, QPalette
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

ORGANIZATION_URL = "https://platform.openai.com/settings/organization/general"
API_KEYS_URL = "https://platform.openai.com/settings/organization/api-keys"
TUNNELS_URL = "https://platform.openai.com/settings/organization/tunnels"
CHATGPT_URL = "https://chatgpt.com/"

DARK_STYLESHEET = """
QWidget {
    background-color: #0b1117;
    color: #e8eef4;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QWizard, QWizardPage {
    background-color: #0b1117;
}
QLabel {
    color: #dce6ee;
    background: transparent;
}
QLineEdit {
    background-color: #111922;
    color: #f3f7fa;
    border: 1px solid #2a3a49;
    border-radius: 6px;
    padding: 7px 9px;
    min-height: 22px;
    selection-background-color: #117a8b;
}
QLineEdit:focus {
    border: 1px solid #22b8cf;
}
QPushButton {
    background-color: #18232e;
    color: #f1f6f9;
    border: 1px solid #304354;
    border-radius: 6px;
    padding: 7px 14px;
    min-height: 22px;
}
QPushButton:hover {
    background-color: #20303e;
    border-color: #3e5a6e;
}
QPushButton:pressed {
    background-color: #111922;
}
QPushButton:default {
    background-color: #0f6f78;
    border-color: #16a5b3;
    font-weight: 600;
}
QCheckBox {
    color: #dce6ee;
    spacing: 7px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}
QCheckBox::indicator:unchecked {
    border: 1px solid #42586a;
    background: #111922;
    border-radius: 3px;
}
QCheckBox::indicator:checked {
    border: 1px solid #21b8a8;
    background: #118b7e;
    border-radius: 3px;
}
QMessageBox {
    background-color: #0b1117;
}
"""


def apply_dark_theme(app):
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0b1117"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e8eef4"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111922"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#15202a"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#111922"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eef4"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e8eef4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#18232e"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f1f6f9"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#117a8b"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    app.setStyleSheet(DARK_STYLESHEET)


def open_url(url):
    webbrowser.open(url, new=2)


def copy_text(text):
    QApplication.clipboard().setText(str(text or ""))


class OrganizationPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Organização OpenAI")
        self.setSubTitle(
            "Confirme a organização correta antes de criar a API key e o túnel."
        )

        layout = QVBoxLayout(self)

        text = QLabel(
            "Clique em Abrir Organização OpenAI. Na página Geral da organização, "
            "confira o nome da organização e localize o campo Organization ID. "
            "Copie esse identificador e cole abaixo. O Organization ID identifica "
            "a organização da empresa e é diferente da API key e do Tunnel ID."
        )
        text.setWordWrap(True)
        layout.addWidget(text)

        open_org = QPushButton("Abrir Organização OpenAI")
        open_org.clicked.connect(lambda: open_url(ORGANIZATION_URL))
        layout.addWidget(open_org)

        hint = QLabel(
            "Página: platform.openai.com/settings/organization/general\n"
            "Procure por: Organization ID"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#8fb2c7; padding: 4px 0 8px 0;")
        layout.addWidget(hint)

        self.company = QLineEdit()
        self.company.setPlaceholderText("Ex.: Atlântic Drones")

        self.organization_id = QLineEdit()
        self.organization_id.setPlaceholderText("Cole o Organization ID da OpenAI")

        self.plugin = QLineEdit("CodeBridge MCP")

        form = QFormLayout()
        form.addRow("Nome da empresa:", self.company)
        form.addRow("Organization ID:", self.organization_id)
        form.addRow("Nome do plugin:", self.plugin)
        layout.addLayout(form)

        self.registerField("company*", self.company)
        self.registerField("organization_id*", self.organization_id)
        self.registerField("plugin*", self.plugin)

    def validatePage(self):
        organization_id = self.organization_id.text().strip()
        if len(organization_id) < 4 or any(ch.isspace() for ch in organization_id):
            QMessageBox.warning(
                self,
                "Organization ID inválido",
                "Cole o Organization ID exatamente como aparece na página Geral "
                "da organização da OpenAI.",
            )
            return False
        return True


class OpenAIPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("API key e OpenAI Tunnel")
        self.setSubTitle(
            "Crie uma chave com acesso a Túneis e um túnel para este computador."
        )

        layout = QVBoxLayout(self)

        info = QLabel(
            "1. Clique em Criar API key. Em computador de empresa, prefira "
            "Conta de serviço.\n"
            "2. Se usar permissões Restritas, a linha Túneis não pode ficar "
            "como Nenhum: a identidade precisa de Ler + Usar em Túneis.\n"
            "3. Clique em Criar Tunnel e crie um túnel para esta máquina.\n"
            "4. Cole abaixo a API key e o Tunnel ID (formato tunnel_...)."
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
        self.api_key.setPlaceholderText(
            "Cole a API key ou deixe vazio para manter a chave já configurada"
        )

        self.tunnel_id = QLineEdit()
        self.tunnel_id.setPlaceholderText("tunnel_...")

        form = QFormLayout()
        form.addRow("API key:", self.api_key)
        form.addRow("Tunnel ID:", self.tunnel_id)
        layout.addLayout(form)

        warning = QLabel(
            "Importante: a API key autentica o tunnel-client local. "
            "Ela NÃO deve ser usada como senha do plugin no ChatGPT. "
            "Se esta máquina já estiver configurada, deixe a API key vazia "
            "para preservar a chave protegida pelo Windows."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet("color:#f2c879; padding-top: 6px;")
        layout.addWidget(warning)

        self.registerField("api_key", self.api_key)
        self.registerField("tunnel_id*", self.tunnel_id)

    def validatePage(self):
        key = self.api_key.text().strip()
        tunnel_id = self.tunnel_id.text().strip()

        if key and (len(key) < 20 or any(ch.isspace() for ch in key)):
            QMessageBox.warning(
                self,
                "API key inválida",
                "Cole a API key completa da organização, sem espaços.",
            )
            return False

        if not tunnel_id.startswith("tunnel_") or any(
            ch.isspace() for ch in tunnel_id
        ):
            QMessageBox.warning(
                self,
                "Tunnel ID inválido",
                "O Tunnel ID deve ter o formato tunnel_...",
            )
            return False

        try:
            config = ConfigStore()
            config.save_company(
                self.field("company"),
                tunnel_id,
                self.field("plugin"),
                organization_id=self.field("organization_id"),
            )
            manager = SecureTunnelManager(config)

            if key:
                manager.save_runtime_key(key)
            elif not manager.credential_configured():
                QMessageBox.warning(
                    self,
                    "API key necessária",
                    "Esta máquina ainda não possui uma API key protegida. "
                    "Cole a chave da organização para continuar.",
                )
                return False

            manager.prepare_profile()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Não foi possível configurar o túnel",
                f"{type(exc).__name__}: {exc}\n\n"
                "Confira a API key, as permissões de Túneis e o Tunnel ID.",
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
            "Agora vincule o ChatGPT ao OpenAI Tunnel que você acabou de configurar."
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
        organization_id = str(self.field("organization_id") or "")
        logo = ROOT / "assets" / "codebridge_plugin_256.png"

        self.instructions.setText(
            "No ChatGPT:\n\n"
            "1. Abra Configurações > Plugins > Novo plugin.\n"
            f"2. Nome: {plugin}\n"
            "3. Descrição sugerida: CodeBridge para execução segura de comandos "
            "no computador local.\n"
            f"4. Ícone: {logo}\n"
            "5. Em Conexão, selecione o OpenAI Tunnel criado para esta máquina.\n"
            f"   Organization ID: {organization_id}\n"
            f"   Tunnel ID: {tunnel_id}\n"
            "6. Não reutilize a API key da organização como credencial do plugin. "
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
        self.setTitle("Configuração concluída")
        self.setSubTitle(
            "O CodeBridge está instalado e a configuração empresarial foi salva."
        )

        layout = QVBoxLayout(self)

        info = QLabel(
            "Ao iniciar o CodeBridge, ele sobe o MCP local e o Secure Tunnel "
            "da empresa. Depois, faça o teste codebridge_ping no ChatGPT. "
            "As próximas versões podem ser aplicadas pelo atalho "
            "Atualizar CodeBridge, sem refazer esta configuração."
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
        self.resize(780, 560)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        icon = ROOT / "assets" / "codebridge.ico"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))

        self.organization = OrganizationPage()
        self.openai = OpenAIPage()
        self.chatgpt = ChatGPTPage()
        self.finish_page = FinishPage()

        self.addPage(self.organization)
        self.addPage(self.openai)
        self.addPage(self.chatgpt)
        self.addPage(self.finish_page)

        self.setButtonText(QWizard.WizardButton.BackButton, "Voltar")
        self.setButtonText(QWizard.WizardButton.NextButton, "Próximo")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Concluir")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")

        current = ConfigStore().load_company()
        if current.get("company_name"):
            self.organization.company.setText(current["company_name"])
        if current.get("organization_id"):
            self.organization.organization_id.setText(current["organization_id"])
        if current.get("plugin_name"):
            self.organization.plugin.setText(current["plugin_name"])
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
    apply_dark_theme(app)
    wizard = SetupWizard()
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
