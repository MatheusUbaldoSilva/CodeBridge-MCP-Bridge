from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)


def _bytes(value):
    value = float(value or 0)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.1f} {unit}"
        value /= 1024.0


def _rate(value):
    return _bytes(value) + "/s"


def _uptime(seconds):
    seconds = int(seconds or 0)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes = seconds // 60
    return (f"{days}d " if days else "") + f"{hours:02d}h {minutes:02d}m"


def _spark(values):
    blocks = "▁▂▃▄▅▆▇█"
    if not values:
        return ""
    result = []
    for value in values[-60:]:
        level = int(max(0.0, min(100.0, float(value))) / 100.0 * (len(blocks) - 1))
        result.append(blocks[level])
    return "".join(result)


class TelemetryPanel(QFrame):
    def __init__(self, service, kind, parent=None):
        super().__init__(parent)
        self.service = service
        self.kind = kind
        self._collapsed = False
        self.setObjectName("telemetryPanel")
        self.setMinimumWidth(270)
        self.setMaximumWidth(300)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(
            "QFrame#telemetryPanel{background:#171717;border:1px solid #333;}"
            "QLabel{color:#ddd;} QProgressBar{border:1px solid #444;background:#0d0d0d;"
            "height:16px;text-align:center;color:#eee;} QProgressBar::chunk{background:#3a8f4b;}"
        )
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        header = QHBoxLayout()
        self.toggle_button = QPushButton("TELEMETRIA ◀")
        self.toggle_button.clicked.connect(self.toggle)
        self.live_label = QLabel("● AO VIVO")
        self.live_label.setStyleSheet("color:#6dd56d;font-weight:600;")
        header.addWidget(self.toggle_button)
        header.addStretch(1)
        header.addWidget(self.live_label)
        outer.addLayout(header)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Atualização:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1s", "2s", "5s"])
        self.interval_combo.currentTextChanged.connect(self._change_interval)
        controls.addWidget(self.interval_combo)
        controls.addStretch(1)
        outer.addLayout(controls)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setSizeAdjustPolicy(QScrollArea.AdjustIgnored)
        scroll.setFrameShape(QFrame.NoFrame)
        self.body = QWidget()
        self.body.setMinimumWidth(0)
        self.body.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 4, 0, 4)
        self.body_layout.setSpacing(7)
        scroll.setWidget(self.body)
        outer.addWidget(scroll, 1)

        self.machine_label = QLabel("WINDOWS" if kind == "windows" else "SERVIDOR LINUX")
        self.machine_label.setStyleSheet("font-weight:700;font-size:13px;color:#fff;")
        self.body_layout.addWidget(self.machine_label)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#e58484;")
        self.body_layout.addWidget(self.error_label)

        self.cpu_bar = self._metric("CPU")
        self.cpu_detail = QLabel()
        self.cpu_spark = QLabel()
        self.cpu_spark.setMinimumWidth(0)
        self.cpu_spark.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.cpu_spark.setStyleSheet("color:#7ad67a;font-family:Consolas;")
        self.body_layout.addWidget(self.cpu_detail)
        self.body_layout.addWidget(self.cpu_spark)
        self.ram_bar = self._metric("RAM")
        self.ram_detail = QLabel()
        self.ram_spark = QLabel()
        self.ram_spark.setMinimumWidth(0)
        self.ram_spark.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.ram_spark.setStyleSheet("color:#65a9ff;font-family:Consolas;")
        self.body_layout.addWidget(self.ram_detail)
        self.body_layout.addWidget(self.ram_spark)

        self.extra_label = QLabel()
        self.extra_label.setWordWrap(True)
        self.body_layout.addWidget(self.extra_label)
        self.gpu_bar = self._metric("GPU")
        self.gpu_detail = QLabel()
        self.body_layout.addWidget(self.gpu_detail)
        self.disk_bar = self._metric("DISCO")
        self.disk_detail = QLabel()
        self.body_layout.addWidget(self.disk_detail)
        self.net_label = QLabel()
        self.net_label.setWordWrap(True)
        self.body_layout.addWidget(self.net_label)
        self.process_label = QLabel()
        self.process_label.setWordWrap(True)
        self.body_layout.addWidget(self.process_label)
        self.uptime_label = QLabel()
        self.body_layout.addWidget(self.uptime_label)
        self.body_layout.addStretch(1)

    def _metric(self, title):
        self.body_layout.addWidget(QLabel(title))
        bar = QProgressBar()
        bar.setRange(0, 100)
        self.body_layout.addWidget(bar)
        return bar
    def _change_interval(self, text):
        try:
            self.service.set_interval(float(text.rstrip("s")))
        except Exception:
            pass

    def toggle(self):
        self._collapsed = not self._collapsed
        self.body.setVisible(not self._collapsed)
        self.interval_combo.setVisible(not self._collapsed)
        self.live_label.setVisible(not self._collapsed)
        if self._collapsed:
            self.toggle_button.setText("▶")
            self.setMinimumWidth(36)
            self.setMaximumWidth(44)
        else:
            self.toggle_button.setText("TELEMETRIA ◀")
            self.setMinimumWidth(270)
            self.setMaximumWidth(300)

    @staticmethod
    def _set_bar(bar, value):
        value = int(round(max(0.0, min(100.0, float(value or 0)))))
        bar.setValue(value)
        bar.setFormat(f"{value}%")

    def refresh(self):
        data = self.service.snapshot(self.kind)
        online = bool(data.get("online"))
        self.live_label.setText("● AO VIVO" if online else "● OFFLINE")
        self.live_label.setStyleSheet(
            "color:#6dd56d;font-weight:600;" if online
            else "color:#e58484;font-weight:600;"
        )
        self.error_label.setText(data.get("error") or "")
        if not online:
            return
        self._set_bar(self.cpu_bar, data.get("cpu_percent", 0))
        self._set_bar(self.ram_bar, data.get("ram_percent", 0))
        self.cpu_spark.setText(_spark(data.get("cpu_history", [])))
        self.ram_spark.setText(_spark(data.get("ram_history", [])))
        self.ram_detail.setText(
            f"{_bytes(data.get('ram_used'))} / {_bytes(data.get('ram_total'))}"
        )
        self._set_bar(self.disk_bar, data.get("disk_percent", 0))
        self.disk_detail.setText(
            f"{_bytes(data.get('disk_used'))} / {_bytes(data.get('disk_total'))}"
        )
        self.net_label.setText(
            "REDE\n"
            f"↓ {_rate(data.get('net_down_bps'))}\n"
            f"↑ {_rate(data.get('net_up_bps'))}"
        )
        self.uptime_label.setText("Uptime  " + _uptime(data.get("uptime")))

        if self.kind == "windows":
            self.cpu_detail.setText(
                f"{data.get('cpu_cores', 0)} threads"
                + (f"  •  {data.get('cpu_ghz'):.2f} GHz" if data.get("cpu_ghz") else "")
            )
            self.extra_label.setText("")
            gpu = data.get("gpu") or {}
            self.gpu_bar.setVisible(bool(gpu))
            self.gpu_detail.setVisible(bool(gpu))
            if gpu:
                self._set_bar(self.gpu_bar, gpu.get("percent", 0))
                self.gpu_detail.setText(
                    f"{gpu.get('name','GPU')}\n"
                    f"VRAM {_bytes((gpu.get('used_mb') or 0) * 1024**2)} / "
                    f"{_bytes((gpu.get('total_mb') or 0) * 1024**2)}  •  "
                    f"{gpu.get('temp_c', 0):.0f} °C"
                )
            self.process_label.setText("")
        else:
            self.gpu_bar.setVisible(False)
            self.gpu_detail.setVisible(False)
            self.cpu_detail.setText(
                f"Load  {data.get('load1',0):.2f}  {data.get('load5',0):.2f}  {data.get('load15',0):.2f}"
            )
            swap_total = data.get("swap_total", 0) or 0
            self.extra_label.setText(
                "SWAP\n"
                f"{_bytes(data.get('swap_used'))} / {_bytes(swap_total)}"
            )
            top_cpu = ", ".join(
                f"{p['name']} {p['value']:.1f}%" for p in data.get("top_cpu", [])
            )
            top_mem = ", ".join(
                f"{p['name']} {_bytes(p['value'])}" for p in data.get("top_mem", [])
            )
            self.process_label.setText(
                f"PROCESSOS  {data.get('process_count',0)}\n"
                f"CPU: {top_cpu or '-'}\nRAM: {top_mem or '-'}"
            )
