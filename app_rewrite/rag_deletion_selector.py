"""RAG-DEL-01.05: selection-only Qt widget, NO deletion capability.

This component collects checked source paths and emits a preview request
signal; backend integration requires separate safety review.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QListWidget,QListWidgetItem,QPushButton

class KnowledgeRemovalSelector(QWidget):
    preview_requested=Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout=QVBoxLayout(self)
        layout.addWidget(QLabel("Selecione os conhecimentos para revisar a exclusão."))
        self.items=QListWidget()
        layout.addWidget(self.items)
        self.status=QLabel("Nenhum conhecimento selecionado")
        layout.addWidget(self.status)
        self.preview_button=QPushButton("Conferir exclusão (sem executar)")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._request_preview)
        layout.addWidget(self.preview_button)
        self.items.itemChanged.connect(self._update)

    def set_files(self, filenames: list[str]):
        if (not isinstance(filenames,list)
                or any(not isinstance(f,str) or not f or "\\" in f for f in filenames)
                or len(set(filenames))!=len(filenames)):
            raise ValueError("inventário de arquivos inválido")
        self.items.blockSignals(True)
        try:
            self.items.clear()
            for filename in sorted(filenames):
                item=QListWidgetItem(filename)
                item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                self.items.addItem(item)
        finally:
            self.items.blockSignals(False)
        self._update()

    def selected_paths(self):
        return [self.items.item(i).text() for i in range(self.items.count())
                if self.items.item(i).checkState()==Qt.CheckState.Checked]

    def _update(self,*_):
        count=len(self.selected_paths())
        self.status.setText(f"{count} conhecimento(s) selecionado(s)")
        self.preview_button.setEnabled(count>0)

    def _request_preview(self):
        selected=self.selected_paths()
        if selected:
            self.preview_requested.emit(selected)
