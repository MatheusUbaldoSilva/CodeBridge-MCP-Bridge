import queue
import threading

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QTimer

from constants import APP_NAME
from terminal_widget import TerminalWidget
from telemetry import TelemetryService
from telemetry_widget import TelemetryPanel


class MainWindow(QMainWindow):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.setWindowTitle(APP_NAME)
        self.resize(980, 720)
        self._last_logs = {}
        self._ui_events = queue.Queue()
        self._ssh_busy = False
        self.telemetry = TelemetryService(
            self.runtime.terminals.config, self.runtime.terminals.credentials
        )
        self.telemetry.start()
        self.telemetry_panels = {}

        root = QWidget(self)
        layout = QVBoxLayout(root)
        self.title = QLabel("CodeBridge 2.0 — MCP Bridge")
        self.subtitle = QLabel("MCP estruturado • comandos visiveis antes do Enter")
        self.overall = QLabel()
        self.author_mcp = QLabel()
        self.secure_tunnel = QLabel()
        self.api = QLabel()
        self.active = QLabel()
        for widget in (self.title, self.subtitle, self.overall, self.author_mcp, self.secure_tunnel, self.api, self.active):
            layout.addWidget(widget)
        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Atualizar estado")
        self.stop_button = QPushButton("Parar comando ativo")
        self.auto_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        self.stop_button.clicked.connect(self.stop_active)
        self.auto_button.clicked.connect(self.toggle_auto)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.auto_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.terminal_views = {}
        self.terminal_status = {}
        for target, title in (
            ("POWERSHELL5.1", "PowerShell"),
            ("CMD", "CMD"),
            ("SSH", "SSH"),
        ):
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 0, 0, 0)
            tab_layout.setSpacing(4)
            status = QLabel()
            status.setContentsMargins(4, 4, 4, 0)
            view = TerminalWidget(self.runtime.terminals, target, tab)
            telemetry_kind = "linux" if target == "SSH" else "windows"
            telemetry_panel = TelemetryPanel(self.telemetry, telemetry_kind, tab)
            content = QHBoxLayout()
            content.setContentsMargins(0, 0, 0, 0)
            content.addWidget(view, 1)
            content.addWidget(telemetry_panel)
            tab_layout.addWidget(status)
            tab_layout.addLayout(content, 1)
            self.terminal_status[target] = status
            self.terminal_views[target] = view
            self.telemetry_panels[target] = telemetry_panel
            self.tabs.addTab(tab, title)

        self.ssh_tab = QWidget()
        ssh_layout = QVBoxLayout(self.ssh_tab)
        form = QFormLayout()
        self.ssh_host = QLineEdit()
        self.ssh_port = QSpinBox()
        self.ssh_port.setRange(1, 65535)
        self.ssh_port.setValue(22)
        self.ssh_user = QLineEdit()
        self.ssh_password = QLineEdit()
        self.ssh_password.setEchoMode(QLineEdit.Password)
        form.addRow("IP / Host:", self.ssh_host)
        form.addRow("Porta:", self.ssh_port)
        form.addRow("Login:", self.ssh_user)
        form.addRow("Senha:", self.ssh_password)
        ssh_layout.addLayout(form)

        ssh_buttons = QHBoxLayout()
        self.ssh_test_button = QPushButton("Testar conexao")
        self.ssh_save_button = QPushButton("Salvar e conectar")
        self.ssh_test_button.clicked.connect(self.test_ssh)
        self.ssh_save_button.clicked.connect(self.save_ssh)
        ssh_buttons.addWidget(self.ssh_test_button)
        ssh_buttons.addWidget(self.ssh_save_button)
        ssh_buttons.addStretch(1)
        ssh_layout.addLayout(ssh_buttons)
        self.ssh_config_status = QLabel()
        ssh_layout.addWidget(self.ssh_config_status)
        ssh_layout.addStretch(1)
        self.tabs.addTab(self.ssh_tab, "Configuracao SSH")

        self.setCentralWidget(root)
        self.auto_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.auto_shortcut.activated.connect(self.toggle_auto)
        self.stop_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.stop_shortcut.activated.connect(self.stop_active)
        self._update_auto_button()
        self._load_ssh_settings()
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.refresh_live)
        self.live_timer.start(75)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(350)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.refresh_telemetry)
        self.telemetry_timer.start(1000)
        self.refresh()
        self.refresh_telemetry()
    def _update_auto_button(self):
        enabled = bool(self.runtime.auto_execute)
        self.auto_button.setText("Auto: ON" if enabled else "Auto: OFF")
        if enabled:
            self.auto_button.setStyleSheet("background:#1f7a3d; color:white; font-weight:bold;")
        else:
            self.auto_button.setStyleSheet("background:#7a2f2f; color:white; font-weight:bold;")

    def toggle_auto(self):
        self.runtime.set_auto_execute(not self.runtime.auto_execute)
        self._update_auto_button()

    def refresh_telemetry(self):
        for panel in self.telemetry_panels.values():
            panel.refresh()

    def _load_ssh_settings(self):
        settings = self.runtime.terminals.ssh_settings()
        self.ssh_host.setText(settings.get("host", ""))
        self.ssh_port.setValue(int(settings.get("port", 22)))
        self.ssh_user.setText(settings.get("username", ""))
        if settings.get("password_saved"):
            self.ssh_password.setPlaceholderText("Senha salva no Windows")
        state = "ONLINE" if settings.get("online") else "OFFLINE"
        self.ssh_config_status.setText(f"SSH: {state}")

    def _resolved_password(self):
        password = self.ssh_password.text()
        if password:
            return password
        credentials = self.runtime.terminals.credentials.load() or {}
        if credentials.get("username") == self.ssh_user.text().strip():
            return credentials.get("password", "")
        return ""

    def _set_ssh_busy(self, busy):
        self._ssh_busy = bool(busy)
        self.ssh_test_button.setEnabled(not busy)
        self.ssh_save_button.setEnabled(not busy)

    def _ssh_values(self):
        return (
            self.ssh_host.text().strip(),
            int(self.ssh_port.value()),
            self.ssh_user.text().strip(),
            self._resolved_password(),
        )

    def test_ssh(self):
        if self._ssh_busy:
            return
        host, port, user, password = self._ssh_values()
        self._set_ssh_busy(True)
        self.ssh_config_status.setText("Testando conexao SSH...")
        threading.Thread(
            target=self._ssh_test_worker,
            args=(host, port, user, password), daemon=True,
        ).start()
    def _ssh_test_worker(self, host, port, user, password):
        try:
            ok = self.runtime.terminals.test_ssh(host, port, user, password)
            self._ui_events.put(("ssh_test", True, "Conexao SSH OK" if ok else "Falha no teste SSH"))
        except Exception as exc:
            self._ui_events.put(("ssh_test", False, f"{type(exc).__name__}: {exc}"))

    def save_ssh(self):
        if self._ssh_busy:
            return
        host, port, user, password = self._ssh_values()
        self._set_ssh_busy(True)
        self.ssh_config_status.setText("Salvando e conectando...")
        threading.Thread(
            target=self._ssh_save_worker,
            args=(host, port, user, password), daemon=True,
        ).start()

    def _ssh_save_worker(self, host, port, user, password):
        try:
            result = self.runtime.terminals.configure_ssh(host, port, user, password)
            self._ui_events.put(("ssh_save", True, result))
        except Exception as exc:
            self._ui_events.put(("ssh_save", False, f"{type(exc).__name__}: {exc}"))

    def _drain_ui_events(self):
        while True:
            try:
                kind, ok, payload = self._ui_events.get_nowait()
            except queue.Empty:
                break
            self._set_ssh_busy(False)
            if kind == "ssh_test":
                self.ssh_config_status.setText(payload)
            elif ok:
                self.ssh_password.clear()
                self.ssh_password.setPlaceholderText("Senha salva no Windows")
                self.ssh_config_status.setText("SSH salvo e ONLINE")
            else:
                self.ssh_config_status.setText(payload)
    def _update_terminal_view(self, target):
        self.terminal_views[target].drain()

    def _ack_pending_job_visibility(self, jobs):
        for job in jobs:
            try:
                if not job.get("visible_at"):
                    self.runtime.store.mark_visible(job["id"])
                if job["state"] == "PREPARED" and not job.get("prepared_visible_at"):
                    self.runtime.store.mark_prepared_visible(job["id"])
            except Exception:
                pass

    def refresh_live(self):
        self._drain_ui_events()
        for target in ("POWERSHELL5.1", "CMD", "SSH"):
            self._update_terminal_view(target)

    def refresh_status(self):
        s = self.runtime.snapshot()
        self._update_auto_button()
        t = s["terminals"]
        author_mcp = s.get("author_mcp") or {}
        secure_tunnel = s.get("secure_tunnel") or {}
        self.overall.setText(f"Estado geral: {s['overall']}")
        managed = "  gerenciado pelo CodeBridge" if author_mcp.get("managed_by_codebridge") else ""
        error = f"  erro: {author_mcp.get('last_error')}" if author_mcp.get("last_error") else ""
        self.author_mcp.setText(
            "MCP Autoral: " + str(author_mcp.get("state") or "OFFLINE") + managed +
            (f"  PID {author_mcp.get('adapter_pid')}" if author_mcp.get("adapter_pid") else "") + error
        )
        tunnel_managed = "  gerenciado pelo CodeBridge" if secure_tunnel.get("managed_by_codebridge") else ""
        tunnel_error = f"  erro: {secure_tunnel.get('last_error')}" if secure_tunnel.get("last_error") else ""
        self.secure_tunnel.setText(
            "Secure Tunnel: " + str(secure_tunnel.get("state") or "OFFLINE") + tunnel_managed +
            (f"  PID {secure_tunnel.get('managed_pid')}" if secure_tunnel.get("managed_pid") else "") + tunnel_error
        )
        self.api.setText(
            f"API local: {'ONLINE' if s['api']['online'] else 'OFFLINE'}  "
            f"{s['api']['host']}:{s['api']['port']}"
        )
        active_id = s["executor"]["active_job_id"]
        if active_id:
            try:
                job = self.runtime.store.get(active_id)
                self.active.setText(
                    f"Job ativo: {job['state']} | {job['target']} | {job['command']}"
                )
            except Exception:
                self.active.setText(f"Job ativo: {active_id}")
        else:
            self.active.setText("Job ativo: nenhum")

        self.terminal_status["POWERSHELL5.1"].setText(
            f"PowerShell 5.1: {'ONLINE' if t['powershell']['online'] else 'OFFLINE'}"
        )
        self.terminal_status["CMD"].setText(
            f"CMD: {'ONLINE' if t['cmd']['online'] else 'OFFLINE'}"
        )
        ssh_state = "ONLINE" if t["ssh"]["online"] else (
            "CONFIGURADO" if t["ssh"]["configured"] else "NAO CONFIGURADO"
        )
        self.terminal_status["SSH"].setText(f"SSH: {ssh_state}")

        visibility_jobs = self.runtime.store.list_visibility_pending(100)
        self._ack_pending_job_visibility(visibility_jobs)

    def refresh(self):
        self.refresh_live()
        self.refresh_status()

    def stop_active(self):
        if not self.runtime.stop_active():
            QMessageBox.information(self, APP_NAME, "Nenhum comando ativo para parar.")

    def closeEvent(self, event):
        try:
            self.telemetry.stop()
        finally:
            super().closeEvent(event)


def run_ui(runtime):
    app = QApplication.instance() or QApplication([])
    window = MainWindow(runtime)
    window.show()
    return app.exec()
