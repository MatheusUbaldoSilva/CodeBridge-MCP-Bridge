"""Central RAG - aba Pesquisar.

Mostra a pesquisa como cartoes agrupados por arquivo, com o trecho encontrado
em destaque e uma pre-visualizacao com numeros de linha ao lado. So le o
conhecimento: nada nesta aba altera o indice.
"""
from __future__ import annotations

import html
import importlib
import queue
import re
import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QTextBrowser,
    QVBoxLayout, QWidget,
)

from rag_deletion_review_panel import PANEL

BLUE = "#2b6cb0"
MUTED = "#8b9aa7"
TEXT = "#e6f0f7"
LINE_NO = "#5d6b78"
MARK = "background:#6b5512;color:#fff3c4;"
ELL = chr(0x2026)
DASH = chr(0x2013)
SEP = " " + chr(0xB7) + " "
TOP_K = 20
MONO = "font-family:Consolas,'Cascadia Mono','Courier New',monospace;font-size:12px;"
FILTERS = (("ALL", "Tudo"), ("CODE", "C" + chr(0xF3) + "digo"), ("DOC", "Texto"))
BADGE = {"CODE": ("C" + chr(0xD3) + "DIGO", "#1f4f7a", "#cfe6ff"),
         "DOC": ("TEXTO", "#4a4420", "#f3e7b0")}
STOPWORDS = frozenset(
    "a o as os de da do das dos e em no na nos nas um uma uns umas para por com "
    "sem que qual quais como onde quando eu voce isso esse essa este esta tem ser "
    "the of and to in is for on with".split())


def _default_search(query, project_id, top_k):
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    bridge = importlib.import_module("author_mcp.rag_bridge")
    return bridge.search_rag_context(query=query, project_id=project_id, top_k=top_k)


def hit_meta(hit):
    meta = hit.get("metadata")
    return meta if isinstance(meta, dict) else {}


def hit_path(hit):
    meta = hit_meta(hit)
    return str(hit.get("path") or hit.get("source_path") or meta.get("path")
               or meta.get("source_path") or hit.get("document_path")
               or "Documento sem nome")


def hit_text(hit):
    return str(hit.get("content") or hit.get("text") or hit.get("snippet") or "")


def hit_kind(hit):
    kind = str(hit_meta(hit).get("source_type") or hit.get("source_type") or "").upper()
    return "CODE" if kind.startswith("CODE") else "DOC"


def _int(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def hit_lines(hit):
    meta = hit_meta(hit)
    start = _int(meta.get("line_start"))
    return start, max(_int(meta.get("line_end")), start)


def lines_label(hit):
    start, end = hit_lines(hit)
    if not start:
        return ""
    return f"linha {start}" if end == start else f"linhas {start}{DASH}{end}"


def hit_stale(hit):
    if hit.get("stale"):
        return True
    check = hit.get("source_verification")
    return isinstance(check, dict) and str(check.get("status") or "FRESH").upper() != "FRESH"


def modes_label(hit):
    modes = " ".join(str(m).lower() for m in (hit.get("retrieval_modes") or []))
    words = any(k in modes for k in ("lex", "fts", "bm25", "keyword"))
    meaning = any(k in modes for k in ("vec", "dense", "sem", "embed"))
    if words and meaning:
        return "palavras + significado"
    if meaning:
        return "por significado"
    if words:
        return "por palavras"
    return ""


def split_path(path):
    norm = str(path).replace(chr(92), "/")
    folder, _, name = norm.rpartition("/")
    return name or norm, folder


def plural(count, one, many):
    return f"{count} {one if count == 1 else many}"

def query_terms(query):
    terms = []
    for word in re.findall(r"[\w.\-]+", str(query).lower()):
        word = word.strip(".-")
        if len(word) >= 3 and word not in STOPWORDS and word not in terms:
            terms.append(word)
    return terms


def mark_html(text, terms):
    text = str(text)
    if not terms:
        return html.escape(text, quote=False)
    pattern = re.compile("|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)),
                         re.IGNORECASE)
    parts, last = [], 0
    for match in pattern.finditer(text):
        parts.append(html.escape(text[last:match.start()], quote=False))
        parts.append('<span style="' + MARK + '">'
                     + html.escape(match.group(0), quote=False) + "</span>")
        last = match.end()
    parts.append(html.escape(text[last:], quote=False))
    return "".join(parts)


def _clip(line, terms, width):
    if len(line) <= width:
        return line
    low = line.lower()
    found = [low.find(t) for t in terms if t in low]
    pos = min(found) if found else 0
    start = max(0, min(pos - width // 3, len(line) - width))
    piece = line[start:start + width]
    return (ELL if start else "") + piece + (ELL if start + width < len(line) else "")


def snippet_lines(text, terms, count=3, width=140):
    lines = [ln.rstrip() for ln in str(text).replace("\r", "").split("\n")]
    filled = [i for i, ln in enumerate(lines) if ln.strip()]
    if not filled:
        return []
    first = next((n for n, i in enumerate(filled)
                  if any(t in lines[i].lower() for t in terms)), 0)
    low = max(0, first - 1)
    return [_clip(lines[i].strip(), terms, width) for i in filled[low:low + count]]


def group_hits(hits):
    groups, index = [], {}
    for rank, hit in enumerate(hits, 1):
        path = hit_path(hit)
        if path not in index:
            index[path] = len(groups)
            groups.append({"path": path, "kind": hit_kind(hit), "hits": []})
        groups[index[path]]["hits"].append((rank, hit))
    return groups


def relevance_scale(hits):
    scores = [h.get("score") for h in hits]
    if not hits or not all(isinstance(s, (int, float)) and not isinstance(s, bool)
                           for s in scores):
        total = max(len(hits), 1)
        return lambda hit, rank: max(0.25, 1.0 - (rank - 1) / total * 0.75)
    high, low = max(scores), min(scores)
    if high - low <= 1e-12:
        return lambda hit, rank: 1.0
    return lambda hit, rank: 0.25 + 0.75 * (float(hit["score"]) - low) / (high - low)


def _muted(widget, size=11):
    widget.setStyleSheet(f"color:{MUTED};font-size:{size}px;border:0;background:transparent;")
    return widget


def _chip(text, bg, fg):
    label = QLabel(text)
    label.setStyleSheet(f"background:{bg};color:{fg};border:0;border-radius:3px;"
                        "padding:1px 6px;font-size:10px;font-weight:700;")
    return label


class ResultCard(QFrame):
    """Um arquivo encontrado: nome, pasta, tipo, relevancia e o melhor trecho."""

    def __init__(self, group, terms, relevance, on_click, parent=None):
        super().__init__(parent)
        self.group = group
        self._on_click = on_click
        self.setObjectName("resultCard")
        self.setCursor(Qt.PointingHandCursor)
        self.set_selected(False)
        rank, best = group["hits"][0]
        name, folder = split_path(group["path"])
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.title = QLabel(f"<b>{html.escape(name)}</b>")
        self.title.setStyleSheet(f"color:{TEXT};font-size:13px;border:0;background:transparent;")
        top.addWidget(self.title)
        badge, bg, fg = BADGE[group["kind"]]
        top.addWidget(_chip(badge, bg, fg))
        if any(hit_stale(h) for _, h in group["hits"]):
            stale = _chip("desatualizado", "#5a2f12", "#ffd2b0")
            stale.setToolTip("O arquivo mudou depois de indexado; reindexe para atualizar.")
            top.addWidget(stale)
        top.addStretch(1)
        self.count = _muted(QLabel(plural(len(group["hits"]), "trecho", "trechos")))
        top.addWidget(self.count)
        lay.addLayout(top)
        if folder:
            where = _muted(QLabel(folder))
            where.setTextFormat(Qt.PlainText)
            where.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            lay.addWidget(where)
        meter = QHBoxLayout()
        meter.setSpacing(8)
        self.relevance = QProgressBar()
        self.relevance.setRange(0, 100)
        self.relevance.setValue(int(round(relevance(best, rank) * 100)))
        self.relevance.setTextVisible(False)
        self.relevance.setFixedSize(90, 5)
        self.relevance.setToolTip(f"Posi{chr(0xE7)}{chr(0xE3)}o #{rank} na pesquisa")
        self.relevance.setStyleSheet(
            "QProgressBar{background:#24313d;border:0;border-radius:2px;}"
            f"QProgressBar::chunk{{background:{BLUE};border-radius:2px;}}")
        meter.addWidget(self.relevance)
        info = [x for x in (lines_label(best), modes_label(best)) if x]
        meter.addWidget(_muted(QLabel(SEP.join(info))))
        meter.addStretch(1)
        lay.addLayout(meter)
        lines = snippet_lines(hit_text(best), terms)
        self.snippet = QLabel("<br>".join(mark_html(ln, terms) for ln in lines)
                              or "<i>(trecho vazio)</i>")
        self.snippet.setTextFormat(Qt.RichText)
        self.snippet.setWordWrap(True)
        self.snippet.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        font = MONO if group["kind"] == "CODE" else "font-size:12px;"
        self.snippet.setStyleSheet(f"color:#c9d6e0;border:0;background:transparent;{font}")
        lay.addWidget(self.snippet)

    def set_selected(self, selected):
        border = BLUE if selected else "#2a3a48"
        bg = "#16283a" if selected else "#101922"
        self.setStyleSheet(f"QFrame#resultCard{{background:{bg};border:1px solid {border};"
                           "border-radius:6px;}")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click(self)
        super().mousePressEvent(event)

class KnowledgeSearchPanel(QWidget):
    """Pesquisa no projeto selecionado; resultado em cartoes por arquivo."""

    result_selected = Signal(str)
    searched = Signal(str)

    def __init__(self, parent=None, search_fn=None):
        super().__init__(parent)
        self._search_fn = search_fn or _default_search
        self._events = queue.Queue()
        self._seq = 0
        self._busy = False
        self._started = 0.0
        self._searched = False
        self._relevance = relevance_scale([])
        self.project_id = ""
        self.query_text = ""
        self.terms = []
        self.hits = []
        self.groups = []
        self.cards = []
        self.selected = None
        self.filter = "ALL"
        self.fallback = ""
        self.elapsed = 0.0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)
        row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText(
            f"O que voc{chr(0xEA)} quer encontrar? Ex.: como desfazer uma exclus{chr(0xE3)}o")
        self.query.setClearButtonEnabled(True)
        self.query.setMinimumHeight(30)
        self.query.returnPressed.connect(self.search)
        self.search_button = QPushButton("Pesquisar")
        self.search_button.setMinimumHeight(30)
        self.search_button.setStyleSheet(
            f"QPushButton{{background:{BLUE};color:white;font-weight:700;padding:4px 16px;}}"
            "QPushButton:disabled{background:#2a3440;color:#7f8a94;}")
        self.search_button.clicked.connect(lambda: self.search())
        row.addWidget(self.query, 1)
        row.addWidget(self.search_button)
        root.addLayout(row)

        bar = QHBoxLayout()
        bar.setSpacing(4)
        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)
        self.filter_buttons = {}
        for key, text in FILTERS:
            button = QPushButton(text)
            button.setCheckable(True)
            button.setStyleSheet(
                "QPushButton{background:#101922;color:#9fb0bd;border:1px solid #2a3a48;"
                "border-radius:11px;padding:2px 12px;}"
                f"QPushButton:checked{{background:#16283a;color:{TEXT};border-color:{BLUE};}}")
            button.clicked.connect(lambda _=False, k=key: self.set_filter(k))
            self.filter_group.addButton(button)
            self.filter_buttons[key] = button
            bar.addWidget(button)
        self.filter_buttons["ALL"].setChecked(True)
        bar.addSpacing(10)
        self.summary = _muted(QLabel(""), 12)
        bar.addWidget(self.summary, 1)
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setTextVisible(False)
        self.busy.setFixedSize(120, 6)
        self.busy.hide()
        bar.addWidget(self.busy)
        root.addLayout(bar)

        self.notice = QLabel("")
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet("background:#2f2a12;color:#f3e7b0;border:1px solid #5a4f1f;"
                                  "border-radius:6px;padding:6px 10px;")
        self.notice.hide()
        root.addWidget(self.notice)

        split = QSplitter(Qt.Horizontal)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 6, 0)
        self.list_layout.setSpacing(6)
        self.empty = QLabel("")
        self.empty.setWordWrap(True)
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet("QLabel{" + PANEL + f"color:{MUTED};padding:28px 16px;}}")
        self.list_layout.addWidget(self.empty)
        self.list_layout.addStretch(1)
        scroll.setWidget(self.list_host)
        split.addWidget(scroll)

        side = QFrame()
        side.setObjectName("searchPreview")
        side.setStyleSheet("QFrame#searchPreview{" + PANEL + "}")
        side_lay = QVBoxLayout(side)
        side_lay.setContentsMargins(10, 8, 10, 8)
        self.preview_title = QLabel("")
        self.preview_title.setStyleSheet(f"color:{TEXT};font-size:14px;border:0;")
        self.preview_path = _muted(QLabel(""))
        self.preview_path.setTextFormat(Qt.PlainText)
        self.preview_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.preview_path.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.preview = QTextBrowser()
        self.preview.setOpenLinks(False)
        self.preview.setStyleSheet("QTextBrowser{background:#0a1015;border:1px solid #24313d;"
                                   "border-radius:4px;padding:4px;}")
        actions = QHBoxLayout()
        self.copy_button = QPushButton("Copiar trecho")
        self.copy_button.clicked.connect(self.copy_snippet)
        self.copy_path_button = QPushButton("Copiar caminho")
        self.copy_path_button.clicked.connect(self.copy_path)
        self.copied = _muted(QLabel(""))
        actions.addWidget(self.copy_button)
        actions.addWidget(self.copy_path_button)
        actions.addWidget(self.copied)
        actions.addStretch(1)
        side_lay.addWidget(self.preview_title)
        side_lay.addWidget(self.preview_path)
        side_lay.addWidget(self.preview, 1)
        side_lay.addLayout(actions)
        split.addWidget(side)
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 6)
        root.addWidget(split, 1)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(100)
        self._render()
    # ----- estado -------------------------------------------------------
    def set_project(self, project_id):
        project_id = str(project_id or "")
        if project_id == self.project_id:
            return
        self.project_id = project_id
        self._seq += 1
        self._set_busy(False)
        self._searched = False
        self.query_text = ""
        self.hits, self.groups, self.fallback = [], [], ""
        self._set_notice("")
        self._render()

    def set_filter(self, key):
        if key not in self.filter_buttons:
            return
        self.filter = key
        self.filter_buttons[key].setChecked(True)
        self._render()

    def visible_groups(self):
        if self.filter == "ALL":
            return list(self.groups)
        return [g for g in self.groups if g["kind"] == self.filter]

    # ----- pesquisa -----------------------------------------------------
    def search(self, query=None):
        text = (self.query.text() if query is None else str(query)).strip()
        if not text or self._busy:
            return False
        if not self.project_id:
            self._set_notice("Escolha um projeto antes de pesquisar.")
            return False
        self._seq += 1
        seq, project, search_fn = self._seq, self.project_id, self._search_fn
        self.query_text = text
        self.terms = query_terms(text)
        self._started = time.monotonic()
        self._set_busy(True)
        self.searched.emit(text)

        def worker():
            try:
                data, error = search_fn(text, project, TOP_K), None
            except Exception as exc:  # mostrado ao usuario, sem derrubar a tela
                data, error = None, str(exc) or exc.__class__.__name__
            self._events.put((seq, data, error))

        self._start(worker)
        return True

    def _start(self, worker):
        threading.Thread(target=worker, name="CodeBridgeSearchPanel", daemon=True).start()

    def _drain(self):
        while True:
            try:
                seq, data, error = self._events.get_nowait()
            except queue.Empty:
                return
            if seq == self._seq:
                self._finish(data, error)

    def _finish(self, data, error):
        self.elapsed = time.monotonic() - self._started
        self._set_busy(False)
        self._searched = True
        if error:
            self.hits, self.groups, self.fallback = [], [], ""
            self._render()
            self._set_notice("A pesquisa falhou: " + error)
            return
        data = data if isinstance(data, dict) else {}
        self.hits = [h for h in (data.get("results") or []) if isinstance(h, dict)]
        self.groups = group_hits(self.hits)
        self._relevance = relevance_scale(self.hits)
        self.fallback = str(data.get("fallback_reason") or "")
        self._render()
        if self.fallback:
            self._set_notice(
                "Pesquisa s" + chr(0xF3) + " por palavras: a busca por significado ainda n"
                + chr(0xE3) + "o est" + chr(0xE1) + " dispon" + chr(0xED) + "vel neste projeto.")
        else:
            self._set_notice("")

    def _set_busy(self, busy):
        self._busy = busy
        self.search_button.setEnabled(not busy)
        self.search_button.setText(("Pesquisando" + ELL) if busy else "Pesquisar")
        self.busy.setVisible(busy)
        if busy:
            self._set_notice("")
            self.summary.setText(f"Pesquisando em {self.project_id}{ELL} leva alguns segundos")

    def _set_notice(self, text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    # ----- desenho ------------------------------------------------------
    def _render(self):
        for card in self.cards:
            self.list_layout.removeWidget(card)
            card.deleteLater()
        self.cards, self.selected = [], None
        for key, button in self.filter_buttons.items():
            total = len(self.groups) if key == "ALL" else sum(
                1 for g in self.groups if g["kind"] == key)
            name = dict(FILTERS)[key]
            button.setText(f"{name} ({total})" if self._searched else name)
        groups = self.visible_groups()
        if not self._busy:
            self.summary.setText(self._summary_text(groups))
        if not groups:
            self.empty.setText(self._empty_text())
            self.empty.show()
            self._show_preview(None)
            return
        self.empty.hide()
        for group in groups:
            card = ResultCard(group, self.terms, self._relevance, self._select, self.list_host)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)
            self.cards.append(card)
        self._select(self.cards[0])

    def _summary_text(self, groups):
        if not self._searched:
            return ""
        seconds = f"{self.elapsed:.1f}".replace(".", ",") + " s"
        pieces = sum(len(g["hits"]) for g in groups)
        return SEP.join((plural(pieces, "trecho", "trechos") + " em "
                         + plural(len(groups), "arquivo", "arquivos"), seconds))

    def _empty_text(self):
        project = html.escape(self.project_id)
        if not self.project_id:
            return "Escolha um projeto para pesquisar."
        if self._searched and self.groups:
            return ("Nenhum resultado deste tipo nesta pesquisa.<br>"
                    "Escolha <b>Tudo</b> para ver os outros.")
        if self._searched:
            quoted = chr(0x201C) + html.escape(self.query_text) + chr(0x201D)
            return (f"Nada encontrado para {quoted} em <b>{project}</b>.<br>"
                    "Tente outras palavras, ou um nome do c" + chr(0xF3)
                    + "digo (fun" + chr(0xE7) + chr(0xE3) + "o, classe, arquivo).")
        return ("Digite o que procura e pressione <b>Enter</b>.<br>"
                f"A pesquisa olha somente o projeto selecionado: <b>{project}</b>.")

    def _select(self, card):
        for other in self.cards:
            other.set_selected(other is card)
        self.selected = card
        self._show_preview(card.group if card else None)
        if card:
            self.result_selected.emit(card.group["path"])

    def _show_preview(self, group):
        self.copied.setText("")
        self.copy_button.setEnabled(bool(group))
        self.copy_path_button.setEnabled(bool(group))
        if not group:
            self.preview_title.setText("")
            self.preview_path.setText("")
            self.preview.setHtml(f'<p style="color:{MUTED};">Selecione um resultado '
                                 "para ler o trecho encontrado.</p>")
            return
        name, _ = split_path(group["path"])
        self.preview_title.setText(f"<b>{html.escape(name)}</b>")
        self.preview_path.setText(group["path"])
        self.preview.setHtml(self.preview_html(group))

    def preview_html(self, group):
        font = MONO if group["kind"] == "CODE" else "font-size:13px;"
        blocks = []
        for rank, hit in group["hits"]:
            start, _ = hit_lines(hit)
            head = SEP.join(x for x in (f"#{rank}", lines_label(hit), modes_label(hit)) if x)
            rows = []
            for offset, line in enumerate(hit_text(hit).replace("\r", "").split("\n")):
                number = str(start + offset) if start else ""
                rows.append(
                    f'<tr><td style="color:{LINE_NO};{MONO}padding-right:10px;" align="right">'
                    f"{number}</td>"
                    f'<td style="color:#d7e2ea;white-space:pre-wrap;{font}">'
                    f"{mark_html(line, self.terms) or '&nbsp;'}</td></tr>")
            blocks.append(f'<p style="color:{MUTED};margin:6px 0 2px 0;">{html.escape(head)}</p>'
                          f'<table cellspacing="0" cellpadding="0">{"".join(rows)}</table>')
        return '<hr style="border:0;background:#24313d;height:1px;">'.join(blocks)

    # ----- copiar -------------------------------------------------------
    def selected_text(self):
        if not self.selected:
            return ""
        return "\n\n".join(hit_text(h).strip("\n") for _, h in self.selected.group["hits"])

    def copy_snippet(self):
        text = self.selected_text()
        if text:
            QGuiApplication.clipboard().setText(text)
            self.copied.setText("Trecho copiado.")
        return text

    def copy_path(self):
        path = self.selected.group["path"] if self.selected else ""
        if path:
            QGuiApplication.clipboard().setText(path)
            self.copied.setText("Caminho copiado.")
        return path