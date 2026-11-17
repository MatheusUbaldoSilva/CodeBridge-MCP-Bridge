"""Painel de sincronizacao automatica: gerencia os pares servidor->Windows.

Lista os pares salvos em project-sync.json, liga/desliga o 'auto' de cada um,
roda sync sob demanda (em thread, sem travar a UI) e mostra o status do
agendador. Reaproveita o motor project_sync e o agendador ja existentes.
"""
import threading
import time

import project_sync as ps

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QProgressBar,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)


def _fmt_ts(ts):
    if not ts:
        return "nunca"
    try:
        return time.strftime("%d/%m %H:%M", time.localtime(float(ts)))
    except Exception:
        return str(ts)


def _fmt_result(r):
    if not isinstance(r, dict):
        return ""
    a = r.get("added", 0)
    u = r.get("updated", 0)
    s = r.get("skipped", 0)
    return "+%s ~%s %s%s" % (a, u, "\u23ed", s)


class _Bridge(QObject):
    one_done = Signal(str, object, object)
    batch_done = Signal(object, object)


class AddPairDialog(QDialog):
    def __init__(self, parent=None, remote="", local="", project_id="",
                 interval_min=10, auto=True, index=False):
        super().__init__(parent)
        self.setWindowTitle("Adicionar par de sincroniza\u00e7\u00e3o")
        form = QFormLayout(self)
        self.remote = QLineEdit(remote)
        self.remote.setPlaceholderText("/caminho/no/servidor")
        self.local = QLineEdit(local)
        self.local.setPlaceholderText("C:\\Users\\...\\pasta")
        self.project = QLineEdit(project_id)
        self.project.setPlaceholderText("nome no RAG (opcional)")
        self.interval = QSpinBox()
        self.interval.setRange(1, 1440)
        self.interval.setValue(int(interval_min or 10))
        self.interval.setSuffix(" min")
        self.auto = QCheckBox("Sincronizar automaticamente")
        self.auto.setChecked(bool(auto))
        self.index = QCheckBox("Indexar no RAG apos sincronizar")
        self.index.setChecked(bool(index))
        form.addRow("Servidor (Linux):", self.remote)
        form.addRow("Windows:", self.local)
        form.addRow("Projeto RAG:", self.project)
        form.addRow("Intervalo:", self.interval)
        form.addRow("", self.auto)
        form.addRow("", self.index)
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self):
        return {
            "remote": self.remote.text().strip(),
            "local": self.local.text().strip(),
            "project_id": self.project.text().strip() or None,
            "interval_min": self.interval.value(),
            "auto": self.auto.isChecked(),
            "index": self.index.isChecked(),
        }


class SyncPanel(QWidget):
    def __init__(self, runtime=None, go_to_rag=None, parent=None):
        super().__init__(parent)
        self._runtime = runtime
        self._go_to_rag = go_to_rag
        self._busy = False
        self._bridge = _Bridge()
        self._bridge.one_done.connect(self._on_one_done)
        self._bridge.batch_done.connect(self._on_batch_done)

        layout = QVBoxLayout(self)
        header = QLabel("Pastas sincronizadas do servidor")
        header.setStyleSheet("font-weight: 600; font-size: 13px;")
        layout.addWidget(header)
        hint = QLabel(
            "Baixa o que mudou no servidor para a pasta do Windows. Ligue "
            "'Auto' para sincronizar sozinho de tempos em tempos.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #8a94a6;")
        layout.addWidget(hint)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "Servidor (Linux)", "Windows", "Intervalo", "Auto",
            "\u00daltima sync", "A\u00e7\u00f5es"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        self.add_btn = QPushButton("+ Adicionar manual")
        self.add_btn.clicked.connect(self._add_manual)
        self.sync_all_btn = QPushButton("Sincronizar todos")
        self.sync_all_btn.clicked.connect(self._sync_all)
        self.sched_label = QLabel("")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        bottom.addWidget(self.add_btn)
        bottom.addWidget(self.sync_all_btn)
        bottom.addStretch(1)
        bottom.addWidget(self.sched_label)
        layout.addLayout(bottom)
        self.status = QLabel("")
        self.status.setStyleSheet("color: #8a94a6;")
        layout.addWidget(self.status)
        layout.addWidget(self.progress)

        self.refresh()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(5000)

    def _pairs(self):
        try:
            return ps.list_pairs()
        except Exception as exc:
            self.status.setText("Erro ao ler configuracao: %s" % exc)
            return []

    def refresh(self):
        pairs = self._pairs()
        self.table.setRowCount(len(pairs))
        for row, pair in enumerate(pairs):
            self._fill_row(row, pair)
        self._update_sched()

    def _fill_row(self, row, pair):
        pid = pair.get("id")
        self.table.setItem(row, 0, QTableWidgetItem(str(pair.get("remote", ""))))
        self.table.setItem(row, 1, QTableWidgetItem(str(pair.get("local", ""))))
        self.table.setItem(
            row, 2, QTableWidgetItem("%s min" % pair.get("interval_min", 10)))

        auto = QCheckBox()
        auto.setChecked(bool(pair.get("auto")))
        auto.toggled.connect(lambda v, i=pid: self._set_auto(i, v))
        cell = QWidget()
        al = QHBoxLayout(cell)
        al.setContentsMargins(0, 0, 0, 0)
        al.addStretch(1)
        al.addWidget(auto)
        al.addStretch(1)
        self.table.setCellWidget(row, 3, cell)

        last = _fmt_ts(pair.get("last_sync"))
        res = _fmt_result(pair.get("last_result"))
        self.table.setItem(
            row, 4, QTableWidgetItem((last + "  " + res).strip()))

        actions = QWidget()
        hl = QHBoxLayout(actions)
        hl.setContentsMargins(4, 2, 4, 2)
        hl.setSpacing(4)
        b_sync = QPushButton("Sincronizar")
        b_sync.clicked.connect(lambda _=False, i=pid: self._sync_one(i))
        b_rag = QPushButton("RAG")
        b_rag.setToolTip(
            "Marca para RAG e abre a Central RAG para indexar/aprovar")
        b_rag.clicked.connect(lambda _=False, p=pair: self._rag(p))
        b_rem = QPushButton("Remover")
        b_rem.clicked.connect(lambda _=False, i=pid, p=pair: self._remove(i, p))
        hl.addWidget(b_sync)
        hl.addWidget(b_rag)
        hl.addWidget(b_rem)
        self.table.setCellWidget(row, 5, actions)

    def _set_auto(self, pair_id, value):
        try:
            ps.set_auto(pair_id, bool(value))
            self._update_sched()
        except Exception as exc:
            QMessageBox.warning(self, "Sync", "Nao foi possivel alterar: %s" % exc)

    def _add_manual(self):
        dlg = AddPairDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        self._add_from_values(dlg.values())

    def add_pair_from_paths(self, local, remote):
        base = (remote or "").rstrip("/").split("/")[-1]
        dlg = AddPairDialog(
            self, remote=remote or "", local=local or "",
            project_id=base, interval_min=10, auto=True, index=False)
        if dlg.exec() != QDialog.Accepted:
            return
        self._add_from_values(dlg.values())

    def _add_from_values(self, v):
        if not v.get("remote") or not v.get("local"):
            QMessageBox.warning(
                self, "Sync", "Informe a pasta do servidor e a do Windows.")
            return
        try:
            ps.add_pair(
                v["remote"], v["local"], project_id=v.get("project_id"),
                interval_min=v.get("interval_min") or 10,
                auto=bool(v.get("auto")), index=bool(v.get("index")))
        except Exception as exc:
            QMessageBox.warning(self, "Sync", "Nao foi possivel adicionar: %s" % exc)
            return
        self.refresh()

    def _remove(self, pair_id, pair):
        name = pair.get("remote", pair_id)
        if QMessageBox.question(
                self, "Remover", "Remover o par?\n%s" % name) != QMessageBox.Yes:
            return
        try:
            ps.remove_pair(pair_id)
        except Exception as exc:
            QMessageBox.warning(self, "Sync", "Nao foi possivel remover: %s" % exc)
        self.refresh()

    def _rag(self, pair):
        try:
            ps.set_index(pair.get("id"), True)
        except Exception:
            pass
        if callable(self._go_to_rag):
            self._go_to_rag(pair)
        self.status.setText(
            "Par marcado para RAG. Rode o preview e a aprovacao na Central RAG.")
        self.refresh()

    def _set_busy(self, busy, msg=""):
        self._busy = busy
        self.sync_all_btn.setEnabled(not busy)
        self.add_btn.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.progress.setVisible(busy)
        if msg:
            self.status.setText(msg)

    def _sync_one(self, pair_id):
        if self._busy or not pair_id:
            return
        self._set_busy(True, "Sincronizando...")

        def work():
            try:
                res = ps.sync_by_id(pair_id)
                self._bridge.one_done.emit(pair_id, res, None)
            except Exception as exc:
                self._bridge.one_done.emit(pair_id, None, str(exc))

        threading.Thread(target=work, daemon=True).start()

    def _on_one_done(self, pair_id, res, error):
        self._set_busy(False)
        if error:
            self.status.setText("Falha: %s" % error)
        elif res is None:
            self.status.setText("Par nao encontrado.")
        else:
            self.status.setText("Pronto: %s" % _fmt_result(res))
        self.refresh()

    def _sync_all(self):
        if self._busy:
            return
        pairs = self._pairs()
        if not pairs:
            self.status.setText("Nenhum par configurado.")
            return
        ids = [p.get("id") for p in pairs if p.get("id")]
        self._set_busy(True, "Sincronizando %d pares..." % len(ids))

        def work():
            results = []
            err = None
            try:
                for i in ids:
                    try:
                        results.append(ps.sync_by_id(i))
                    except Exception as exc:
                        results.append({"id": i, "error": str(exc)})
            except Exception as exc:
                err = str(exc)
            self._bridge.batch_done.emit(results, err)

        threading.Thread(target=work, daemon=True).start()

    def _on_batch_done(self, results, error):
        self._set_busy(False)
        if error:
            self.status.setText("Falha: %s" % error)
        else:
            self.status.setText(
                "Concluido: %d pares sincronizados." % len(results or []))
        self.refresh()

    def _scheduler(self):
        return getattr(self._runtime, "_sync_scheduler", None)

    def _next_due_secs(self):
        pairs = self._pairs()
        now = time.time()
        best = None
        for p in pairs:
            if not p.get("auto"):
                continue
            interval = float(p.get("interval_min", 10)) * 60.0
            last = p.get("last_sync")
            due = (float(last) + interval) if last else now
            eta = due - now
            if best is None or eta < best:
                best = eta
        return best

    def _update_sched(self):
        sched = self._scheduler()
        on = bool(sched and sched.is_running())
        text = "Agendador: ON" if on else "Agendador: OFF"
        if on:
            eta = self._next_due_secs()
            if eta is not None:
                eta = max(0, int(eta))
                text += "  \u00b7 prox ~%dm%02ds" % (eta // 60, eta % 60)
            else:
                text += "  \u00b7 sem pares auto"
        self.sched_label.setText(text)

    def _tick(self):
        if not self._busy:
            self.refresh()
