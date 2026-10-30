"""RAG-DEL review-only Qt surface. No destructive controls are exposed."""
from __future__ import annotations
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QPlainTextEdit,QMessageBox
from rag_deletion_selector import KnowledgeRemovalSelector
from rag.runtime.knowledge_deletion_review import build_deletion_review

class KnowledgeRemovalReviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.project_id=""
        self.selector=KnowledgeRemovalSelector(self)
        self.details=QPlainTextEdit(self)
        self.details.setReadOnly(True)
        self.details.setPlaceholderText("Selecione os arquivos e confira a prévia.")
        self.last_review=None
        root=QVBoxLayout(self)
        root.addWidget(self.selector)
        root.addWidget(self.details)
        self.selector.preview_requested.connect(self.review_selected)

    def set_project_files(self, project_id: str, filenames: list[str]):
        self.project_id=project_id
        self.last_review=None
        self.details.clear()
        self.selector.set_files(filenames)
        if project_id=="codebridge":
            self.selector.preview_button.setEnabled(False)
            self.details.setPlainText("Exclusão do índice público não é permitida.")

    def review_selected(self, selected: list[str]):
        self.last_review=None
        self.details.clear()
        if not selected or self.project_id=="codebridge":
            return
        try:
            review=build_deletion_review(self.project_id,selected)
        except (ValueError, OSError, RuntimeError) as error:
            self.details.setPlainText("Prévia bloqueada: "+str(error))
            return
        self.last_review=review
        self.details.setPlainText(review["display_text"])
