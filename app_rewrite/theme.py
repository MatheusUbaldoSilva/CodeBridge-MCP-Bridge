from PySide6.QtGui import QColor, QPalette

DARK_STYLESHEET = """
QWidget {
    background-color: #0b1117;
    color: #e8eef4;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QMainWindow, QDialog, QWizard, QWizardPage {
    background-color: #0b1117;
}
QLabel {
    color: #dce6ee;
    background: transparent;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #111922;
    color: #f3f7fa;
    border: 1px solid #2a3a49;
    border-radius: 5px;
    padding: 5px 7px;
    selection-background-color: #117a8b;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #22b8cf;
}
QPushButton {
    background-color: #18232e;
    color: #f1f6f9;
    border: 1px solid #304354;
    border-radius: 5px;
    padding: 6px 12px;
}
QPushButton:hover {
    background-color: #20303e;
    border-color: #3e5a6e;
}
QPushButton:pressed {
    background-color: #111922;
}
QPushButton:disabled {
    color: #6f7f8c;
    background-color: #141c24;
    border-color: #26333f;
}
QTabWidget::pane {
    border: 1px solid #2a3a49;
    background: #0b1117;
}
QTabBar::tab {
    background: #131c25;
    color: #cfd9e1;
    border: 1px solid #2a3a49;
    padding: 7px 14px;
}
QTabBar::tab:selected {
    background: #1c2a35;
    color: #ffffff;
    border-bottom-color: #1c2a35;
}
QScrollArea, QScrollArea > QWidget > QWidget {
    background-color: #11171d;
}
QScrollBar:vertical {
    background: #0f151b;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #344754;
    min-height: 24px;
    border-radius: 5px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QProgressBar {
    border: 1px solid #334450;
    background: #080d11;
    color: #f0f4f7;
    text-align: center;
    min-height: 16px;
}
QProgressBar::chunk {
    background-color: #278b55;
}
QCheckBox {
    color: #dce6ee;
}
QMessageBox {
    background-color: #0b1117;
}
QToolTip {
    color: #f3f7fa;
    background-color: #111922;
    border: 1px solid #304354;
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
