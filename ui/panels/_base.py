"""
ui/panels/_base.py — Widget base para paneles en construcción
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt

_TEXT_ACCENT = "#cba6f7"
_TEXT_DIM    = "#a6adc8"
_TEXT_FAINT  = "#585b70"


class PanelBase(QWidget):
    titulo    = ""
    subtitulo = ""
    fase      = 0

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        lbl_titulo = QLabel(self.titulo)
        lbl_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_titulo.setStyleSheet(
            f"color: {_TEXT_ACCENT}; font-size: 26px; font-weight: bold;"
        )

        lbl_sub = QLabel(self.subtitulo)
        lbl_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_sub.setWordWrap(True)
        lbl_sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 14px;")

        lbl_fase = QLabel(f"En construcción · Fase {self.fase}")
        lbl_fase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_fase.setStyleSheet(
            f"color: {_TEXT_FAINT}; font-size: 11px; margin-top: 24px;"
        )

        lay.addWidget(lbl_titulo)
        lay.addWidget(lbl_sub)
        lay.addWidget(lbl_fase)
