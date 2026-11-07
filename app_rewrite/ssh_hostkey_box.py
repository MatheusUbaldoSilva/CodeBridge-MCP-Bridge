"""Quadro da aba Configuracao SSH que mostra a chave do servidor.

Primeira conexao: mostra a impressao digital e o botao "Aceitar e confiar".
Chave trocada: alerta vermelho e "Substituir chave" com confirmacao.
Chave conhecida: uma linha verde discreta.
"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout,
)

KEY_FILES = {
    "ssh-ed25519": "/etc/ssh/ssh_host_ed25519_key.pub",
    "ssh-rsa": "/etc/ssh/ssh_host_rsa_key.pub",
}


def key_file_hint(key_type):
    if str(key_type).startswith("ecdsa"):
        return "/etc/ssh/ssh_host_ecdsa_key.pub"
    return KEY_FILES.get(key_type, "/etc/ssh/ssh_host_*_key.pub")


class HostKeyBox(QFrame):
    accept_requested = Signal(dict, bool)

    def __init__(self, parent=None, confirm=None):
        super().__init__(parent)
        self._info = None
        self._confirm = confirm or self._ask
        self.setObjectName("sshHostKeyBox")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        self.title = QLabel()
        self.title.setStyleSheet("font-weight: 600;")
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextSelectableByMouse)
        buttons = QHBoxLayout()
        self.accept_btn = QPushButton("Aceitar e confiar")
        self.replace_btn = QPushButton("Substituir chave")
        self.cancel_btn = QPushButton("Agora nao")
        self.accept_btn.clicked.connect(self._accept)
        self.replace_btn.clicked.connect(self._replace)
        self.cancel_btn.clicked.connect(self.hide)
        for b in (self.accept_btn, self.replace_btn, self.cancel_btn):
            buttons.addWidget(b)
        buttons.addStretch(1)
        layout.addWidget(self.title)
        layout.addWidget(self.details)
        layout.addLayout(buttons)
        self.hide()

    @property
    def info(self):
        return self._info

    def show_info(self, info):
        self._info = dict(info or {})
        state = self._info.get("state")
        kind = self._info.get("key_type", "?")
        fp = self._info.get("fingerprint", "?")
        where = f"{self._info.get('host', '')}:{self._info.get('port', 22)}"
        check_cmd = f"ssh-keygen -lf {key_file_hint(kind)}"
        if state == "TRUSTED":
            self.title.setText("Chave do servidor conferida")
            self.details.setText(f"{kind}  {fp}")
            self.setStyleSheet("#sshHostKeyBox { border: 1px solid #2f7d4f; border-radius: 6px; }")
            self.accept_btn.hide(); self.replace_btn.hide(); self.cancel_btn.hide()
        elif state == "CHANGED":
            known = self._info.get("known_fingerprints") or {}
            saved = "\n".join(f"   {k}  {v}" for k, v in known.items()) or "   (nenhuma)"
            self.title.setText("ATENCAO: a chave deste servidor mudou")
            self.details.setText(
                f"{where} apresentou uma chave diferente da que estava salva. "
                "Isso acontece quando o servidor foi reinstalado, mas tambem pode "
                "ser alguem no meio do caminho. A conexao foi bloqueada.\n\n"
                f"Chave agora:  {kind}  {fp}\nChaves salvas:\n{saved}\n\n"
                f"Para conferir no servidor: {check_cmd}"
            )
            self.setStyleSheet("#sshHostKeyBox { border: 1px solid #c0392b; border-radius: 6px; }")
            self.accept_btn.hide(); self.replace_btn.show(); self.cancel_btn.show()
        else:
            self.title.setText("Primeira conexao com este servidor")
            self.details.setText(
                f"Confira a impressao digital da chave de {where} antes de aceitar:\n\n"
                f"   {kind}  {fp}\n\n"
                f"Para conferir no servidor: {check_cmd}\n"
                "Depois de aceitar, ela fica salva em ~/.ssh/known_hosts e o "
                "CodeBridge passa a recusar qualquer chave diferente."
            )
            self.setStyleSheet("#sshHostKeyBox { border: 1px solid #d4a017; border-radius: 6px; }")
            self.accept_btn.show(); self.replace_btn.hide(); self.cancel_btn.show()
        self.accept_btn.setEnabled(True)
        self.replace_btn.setEnabled(True)
        self.show()

    def set_busy(self, busy):
        self.accept_btn.setEnabled(not busy)
        self.replace_btn.setEnabled(not busy)

    def _accept(self):
        if self._info:
            self.set_busy(True)
            self.accept_requested.emit(dict(self._info), False)

    def _replace(self):
        if not self._info:
            return
        if not self._confirm(self._info):
            return
        self.set_busy(True)
        self.accept_requested.emit(dict(self._info), True)

    def _ask(self, info):
        answer = QMessageBox.warning(
            self, "Substituir chave do servidor",
            "Substitua a chave apenas se voce reinstalou ou trocou o servidor "
            "e conferiu a nova impressao digital nele.\n\n"
            f"{info.get('key_type')}  {info.get('fingerprint')}\n\nSubstituir?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        return answer == QMessageBox.Yes