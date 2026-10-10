from pathlib import Path
import queue
import threading

from PySide6.QtGui import QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QSizePolicy, QSpinBox,
    QStackedWidget, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt, QTimer

from constants import APP_NAME
from terminal_widget import TerminalWidget
from telemetry import TelemetryService
from telemetry_widget import TelemetryPanel
from rag_panel import RagPanel
from theme import apply_dark_theme


class MainWindow(QMainWindow):
    def __init__(self, runtime):
        super().__init__()
        self.runtime = runtime
        self.setWindowTitle(APP_NAME)
        self.resize(980, 720)
        self._ui_events = queue.Queue()
        self._ssh_busy = False
        self._last_chatgpt_timer_state = None
        self._last_auto_swap_generation = None
        self.telemetry = TelemetryService(
            self.runtime.terminals.config, self.runtime.terminals.credentials
        )
        self.telemetry.start()
        self.telemetry_panels = {}

        root = QWidget(self)
        layout = QHBoxLayout(root)
        layout.setSpacing(8)

        left_panel = QWidget(root)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        layout.addWidget(left_panel, 1)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(14)

        info_panel = QWidget(left_panel)
        info_layout = QVBoxLayout(info_panel)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        self.brand = QLabel()
        self.brand.setStyleSheet("background: transparent; border: 0;")
        self.brand.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        brand_path = (
            Path(__file__).resolve().parent.parent
            / "assets"
            / "codebridge_brand_header.png"
        )
        if brand_path.exists():
            brand_pixmap = QPixmap(str(brand_path))
            if not brand_pixmap.isNull():
                self.brand.setPixmap(
                    brand_pixmap.scaledToHeight(72, Qt.SmoothTransformation)
                )
                self.brand.setFixedHeight(80)
        info_layout.addWidget(self.brand)

        self.overall = QLabel()
        self.author_mcp = QLabel()
        self.secure_tunnel = QLabel()
        self.api = QLabel()
        self.active = QLabel()
        for widget in (
            self.overall, self.author_mcp, self.secure_tunnel, self.api, self.active
        ):
            info_layout.addWidget(widget)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Atualizar estado")
        self.stop_button = QPushButton("Parar comando ativo")
        self.sound_button = QPushButton()
        self.sound_button.setToolTip(
            "Som ao finalizar comando"
        )
        self.auto_button = QPushButton()
        self.refresh_button.clicked.connect(self.refresh)
        self.stop_button.clicked.connect(self.stop_active)
        self.sound_button.clicked.connect(
            self.toggle_completion_sound
        )
        self.auto_button.clicked.connect(self.toggle_auto)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.stop_button)
        buttons.addWidget(self.sound_button)
        buttons.addWidget(self.auto_button)
        buttons.addStretch(1)
        info_layout.addLayout(buttons)

        header.addWidget(info_panel, 0)
        header.addStretch(1)

        self.chatgpt_timer_box = QFrame(left_panel)
        self.chatgpt_timer_box.setObjectName("chatgptTimerBox")
        self.chatgpt_timer_box.setMinimumWidth(420)
        self.chatgpt_timer_box.setMaximumWidth(620)
        self.chatgpt_timer_box.setFixedHeight(145)
        self.chatgpt_timer_box.setStyleSheet(
            "QFrame#chatgptTimerBox{"
            "background:#0a1015;"
            "border:1px solid #33414d;"
            "border-radius:10px;"
            "}"
        )
        timer_layout = QVBoxLayout(self.chatgpt_timer_box)
        timer_layout.setContentsMargins(20, 12, 20, 12)
        timer_layout.setSpacing(2)

        self.chatgpt_timer_label = QLabel("00:00")
        self.chatgpt_timer_label.setAlignment(Qt.AlignCenter)
        self.chatgpt_timer_label.setStyleSheet(
            "color:#eef3f6;"
            "font-family:Consolas,'Courier New',monospace;"
            "font-size:52px;"
            "font-weight:700;"
            "letter-spacing:2px;"
            "background:transparent;"
            "border:0;"
        )
        self.chatgpt_timer_status = QLabel("AGUARDANDO")
        self.chatgpt_timer_status.setAlignment(Qt.AlignCenter)
        self.chatgpt_timer_status.setStyleSheet(
            "color:#7f93a3;"
            "font-size:13px;"
            "font-weight:600;"
            "letter-spacing:1px;"
            "background:transparent;"
            "border:0;"
        )
        timer_layout.addStretch(1)
        timer_layout.addWidget(self.chatgpt_timer_label)
        timer_layout.addWidget(self.chatgpt_timer_status)
        timer_layout.addStretch(1)

        header.addWidget(
            self.chatgpt_timer_box,
            0,
            Qt.AlignVCenter,
        )
        header.addStretch(1)
        left_layout.addLayout(header)

        self.telemetry_stack = QStackedWidget(root)
        self.telemetry_stack.setMinimumWidth(270)
        self.telemetry_stack.setMaximumWidth(300)
        self.telemetry_stack.setSizePolicy(
            QSizePolicy.Fixed,
            QSizePolicy.Expanding,
        )

        self.telemetry_windows = TelemetryPanel(
            self.telemetry,
            "windows",
            self.telemetry_stack,
        )
        self.telemetry_linux = TelemetryPanel(
            self.telemetry,
            "linux",
            self.telemetry_stack,
        )
        self.telemetry_stack.addWidget(
            self.telemetry_windows
        )
        self.telemetry_stack.addWidget(
            self.telemetry_linux
        )
        self.telemetry_panels = {
            "windows": self.telemetry_windows,
            "linux": self.telemetry_linux,
        }

        layout.addWidget(
            self.telemetry_stack,
            0,
        )

        self.tabs = QTabWidget()
        left_layout.addWidget(self.tabs, 1)
        self.terminal_views = {}
        self.terminal_status = {}
        self.terminal_tab_indices = {}
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
            tab_layout.addWidget(status)
            tab_layout.addWidget(view, 1)
            self.terminal_status[target] = status
            self.terminal_views[target] = view
            tab_index = self.tabs.addTab(tab, title)
            self.terminal_tab_indices[target] = tab_index

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
        self.rag_tab = RagPanel(self.tabs)
        self.tabs.addTab(self.rag_tab, "Central RAG")
        self.tabs.currentChanged.connect(
            self._sync_telemetry_panel
        )
        self._sync_telemetry_panel(
            self.tabs.currentIndex()
        )

        self.setCentralWidget(root)
        self.auto_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        self.auto_shortcut.activated.connect(self.toggle_auto)
        self.stop_shortcut = QShortcut(QKeySequence("Ctrl+Shift+P"), self)
        self.stop_shortcut.activated.connect(self.stop_active)
        self._update_auto_button()
        self._update_sound_button()
        self._load_ssh_settings()
        self.live_timer = QTimer(self)
        self.live_timer.timeout.connect(self.refresh_live)
        self.live_timer.start(75)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(350)
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.refresh_telemetry)
        self.telemetry_timer.start(500)
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

    def _update_sound_button(self):
        enabled = bool(
            self.runtime.completion_sound.enabled
        )
        self.sound_button.setText(
            "🔔" if enabled else "🔕"
        )
        self.sound_button.setToolTip(
            "Som de conclusão: "
            + ("ligado" if enabled else "desligado")
        )
        if enabled:
            self.sound_button.setStyleSheet(
                "background:#1f7a3d;"
                "color:white;"
                "font-weight:bold;"
            )
        else:
            self.sound_button.setStyleSheet(
                "background:#39434c;"
                "color:#d7e0e7;"
                "font-weight:bold;"
            )

        auto_size = self.auto_button.sizeHint()
        self.sound_button.setFixedSize(auto_size)

    def toggle_completion_sound(self):
        self.runtime.toggle_completion_sound()
        self._update_sound_button()

    def _sync_telemetry_panel(self, index):
        if index in (self.terminal_tab_indices["SSH"], self.tabs.indexOf(self.ssh_tab)):
            self.telemetry_stack.setCurrentWidget(
                self.telemetry_linux
            )
        else:
            self.telemetry_stack.setCurrentWidget(
                self.telemetry_windows
            )

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

    @staticmethod
    def _format_chatgpt_elapsed(seconds):
        total_seconds = int(
            max(0.0, float(seconds or 0.0))
        )
        minutes, whole_seconds = divmod(
            total_seconds,
            60,
        )
        return (
            f"{minutes:02d}:"
            f"{whole_seconds:02d}"
        )

    def _refresh_chatgpt_timer(self):
        timer = self.runtime.chatgpt_timer.snapshot()
        control = self.runtime.chatgpt_timer.turn_control()
        claimed = bool(
            timer.get("claimed_by_codebridge")
        )
        state = (
            str(
                timer.get("state") or "IDLE"
            ).upper()
            if claimed
            else "IDLE"
        )
        control_stage = str(
            control.get("stage") or "INACTIVE"
        ).upper()

        self.chatgpt_timer_label.setText(
            self._format_chatgpt_elapsed(
                timer.get("elapsed_seconds")
                if claimed
                else 0.0
            )
        )

        visual_state = state
        if state == "RUNNING":
            if control_stage == "PREPARE_WRAP_UP":
                visual_state = "PREPARE_WRAP_UP"
            elif control_stage == "WRAP_UP_NOW":
                visual_state = "WRAP_UP_NOW"

        if visual_state == self._last_chatgpt_timer_state:
            return

        self._last_chatgpt_timer_state = visual_state

        labels = {
            "IDLE": (
                "AGUARDANDO",
                "#7f93a3",
            ),
            "RUNNING": (
                "PROCESSANDO",
                "#4fd1c5",
            ),
            "PREPARE_WRAP_UP": (
                "FINALIZANDO EM BREVE",
                "#e5b45f",
            ),
            "WRAP_UP_NOW": (
                "ENCERRAR TURNO",
                "#e58484",
            ),
            "FINISHED": (
                "CONCLUÍDO",
                "#6dd56d",
            ),
            "CANCELLED": (
                "INTERROMPIDO",
                "#e5b45f",
            ),
        }
        text, color = labels.get(
            visual_state,
            (
                visual_state,
                "#7f93a3",
            ),
        )
        self.chatgpt_timer_status.setText(
            text
        )
        self.chatgpt_timer_status.setStyleSheet(
            "color:"
            + color
            + ";font-size:13px;"
            "font-weight:600;"
            "letter-spacing:1px;"
            "background:transparent;"
            "border:0;"
        )

    def refresh_live(self):
        self._drain_ui_events()
        self._refresh_chatgpt_timer()
        for target in ("POWERSHELL5.1", "CMD", "SSH"):
            self._update_terminal_view(target)

    def _auto_swap_terminal_tab(self, terminals):
        generation = int(
            terminals.get("execution_generation")
            or 0
        )
        target = str(
            terminals.get("last_execution_target")
            or ""
        ).upper()

        if self._last_auto_swap_generation is None:
            self._last_auto_swap_generation = generation
            currently_executing = any(
                bool(
                    (terminals.get(name) or {}).get(
                        "executing"
                    )
                )
                for name in (
                    "powershell",
                    "cmd",
                    "ssh",
                )
            )
            if not currently_executing:
                return
        elif generation == self._last_auto_swap_generation:
            return
        else:
            self._last_auto_swap_generation = generation

        tab_index = self.terminal_tab_indices.get(
            target
        )
        if tab_index is None:
            return

        if self.tabs.currentIndex() != tab_index:
            self.tabs.setCurrentIndex(tab_index)

    def refresh_status(self):
        s = self.runtime.snapshot()
        self._update_auto_button()
        self._update_sound_button()
        t = s["terminals"]
        self._auto_swap_terminal_tab(t)
        author_mcp = s.get("author_mcp") or {}
        secure_tunnel = s.get("secure_tunnel") or {}
        self.overall.setText(f"Estado geral: {s['overall']}")
        managed = "  gerenciado pelo CodeBridge" if author_mcp.get("managed_by_codebridge") else ""
        error = f"  erro: {author_mcp.get('last_error')}" if author_mcp.get("last_error") else ""
        self.author_mcp.setText(
            "MCP Autoral: " + str(author_mcp.get("state") or "OFFLINE") + managed +
            (f"  PID {author_mcp.get('adapter_pid')}" if author_mcp.get("adapter_pid") else "") + error
        )
        tunnel_state = str(
            secure_tunnel.get("state") or "OFFLINE"
        )
        tunnel_managed = (
            "  gerenciado pelo CodeBridge"
            if secure_tunnel.get("managed_by_codebridge")
            else ""
        )
        tunnel_error = (
            f"  erro: {secure_tunnel.get('last_error')}"
            if secure_tunnel.get("last_error")
            and not secure_tunnel.get("health_online")
            else ""
        )
        tunnel_note = (
            "  (processo externo)"
            if secure_tunnel.get("external_process")
            else ""
        )
        tunnel_pid = (
            secure_tunnel.get("managed_pid")
            or secure_tunnel.get("external_pid")
        )
        self.secure_tunnel.setText(
            "Secure Tunnel: "
            + tunnel_state
            + (
                f"  PID {tunnel_pid}"
                if tunnel_pid
                else ""
            )
            + tunnel_note
            + tunnel_managed
            + tunnel_error
        )
        self.api.setText(
            f"API local: {'ONLINE' if s['api']['online'] else 'OFFLINE'}  "
            f"{s['api']['host']}:{s['api']['port']}"
        )
        active_execution = s.get("active_execution")
        active_id = s["executor"]["active_job_id"]
        turn_control = s.get("turn_control") or {}
        manual_stop_requested = bool(
            turn_control.get("manual_request")
        )
        active_command = bool(
            active_execution
            or active_id
            or t.get("active_target")
            or t.get("prepared_target")
            or any(
                bool(
                    (t.get(name) or {}).get(
                        "executing"
                    )
                )
                for name in (
                    "powershell",
                    "cmd",
                    "ssh",
                )
            )
        )

        if active_execution:
            self.active.setText(
                "Job ativo: "
                + str(active_execution["state"])
                + " | "
                + str(active_execution["target"])
                + " | "
                + str(active_execution["execution_id"])
            )
        elif active_id:
            try:
                job = self.runtime.store.get(active_id)
                self.active.setText(
                    f"Job ativo: {job['state']} | {job['target']} | {job['command']}"
                )
            except Exception:
                self.active.setText(f"Job ativo: {active_id}")
        else:
            self.active.setText("Job ativo: nenhum")

        if manual_stop_requested:
            if active_command:
                self.stop_button.setText(
                    "Forçar parada"
                )
                self.stop_button.setEnabled(
                    True
                )
                self.active.setText(
                    self.active.text()
                    + " | PARADA SOLICITADA"
                )
            else:
                self.stop_button.setText(
                    "Parada solicitada"
                )
                self.stop_button.setEnabled(
                    False
                )
        else:
            self.stop_button.setText(
                "Parar comando ativo"
            )
            self.stop_button.setEnabled(
                active_command
            )

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
        control = (
            self.runtime.chatgpt_timer.turn_control()
        )

        if control.get("manual_request"):
            if not self.runtime.force_stop_active():
                QMessageBox.information(
                    self,
                    APP_NAME,
                    "Nenhum comando ativo para forcar.",
                )
        else:
            result = (
                self.runtime.request_graceful_stop()
            )
            if not result.get("requested"):
                QMessageBox.information(
                    self,
                    APP_NAME,
                    "Nenhum comando ativo para parar.",
                )

        self.refresh()

    def closeEvent(self, event):
        try:
            self.telemetry.stop()
        finally:
            super().closeEvent(event)


def run_ui(runtime):
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    icon_path = (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "codebridge.ico"
    )
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    window = MainWindow(runtime)
    if icon_path.exists():
        window.setWindowIcon(QIcon(str(icon_path)))
    window.show()
    return app.exec()
