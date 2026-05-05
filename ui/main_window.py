"""
ui/main_window.py — Ventana principal con sidebar de navegación
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStackedWidget, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QGuiApplication
from pathlib import Path

LOGO_PATH = Path(__file__).parent.parent / "data" / "logo1.jpg"

# Paleta Catppuccin Mocha
_BG_SIDEBAR  = "#1e1e2e"
_BG_MAIN     = "#24273a"
_BTN_HOVER   = "#313244"
_BTN_ACTIVE  = "#45475a"
_TEXT_DIM    = "#a6adc8"
_TEXT_ACCENT = "#cba6f7"

SIDEBAR_STYLE = f"""
    QPushButton {{
        text-align: left;
        padding: 10px 16px;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        color: {_TEXT_DIM};
        background: transparent;
    }}
    QPushButton:hover {{
        background: {_BTN_HOVER};
        color: white;
    }}
    QPushButton:checked {{
        background: {_BTN_ACTIVE};
        color: {_TEXT_ACCENT};
        font-weight: bold;
    }}
"""

SECCIONES = [
    ("👥  Clientes",        "ui.panels.panel_clientes",     "PanelClientes"),
    ("💰  Honorarios",      "ui.panels.panel_honorarios",   "PanelHonorarios"),
    ("📋  Liquidador",      "ui.panels.panel_liquidador",   "PanelLiquidador"),
    ("📁  Archivos",        "ui.panels.panel_archivos",     "PanelArchivos"),
    ("🧮  Calculadoras",    "ui.panels.panel_calculadoras", "PanelCalculadoras"),
    ("🤖  Asistente IA",    "ui.panels.panel_asistente",    "PanelAsistente"),
]


class VentanaPrincipal(QMainWindow):
    def __init__(self, nombre_estudio: str = "Software Contable"):
        super().__init__()
        self.setWindowTitle(nombre_estudio)
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))
        self.resize(1150, 700)
        self._centrar()

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar(nombre_estudio))
        root.addWidget(self._build_stack())

        self._cambiar_panel(0)

    # ── Sidebar ──────────────────────────────────────────────────
    def _build_sidebar(self, nombre_estudio: str) -> QFrame:
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setStyleSheet(f"background: {_BG_SIDEBAR};")

        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(10, 20, 10, 20)
        lay.setSpacing(4)

        lbl = QLabel(nombre_estudio)
        lbl.setWordWrap(True)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color: {_TEXT_ACCENT}; font-weight: bold; font-size: 12px;"
            "padding: 0 4px 20px;"
        )
        lay.addWidget(lbl)

        self._botones = []
        for i, (nombre, *_) in enumerate(SECCIONES):
            btn = QPushButton(nombre)
            btn.setCheckable(True)
            btn.setStyleSheet(SIDEBAR_STYLE)
            btn.clicked.connect(lambda _checked, idx=i: self._cambiar_panel(idx))
            lay.addWidget(btn)
            self._botones.append(btn)

        lay.addStretch()
        return sidebar

    # ── Stack de paneles ─────────────────────────────────────────
    def _build_stack(self) -> QStackedWidget:
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {_BG_MAIN};")

        for _, modulo, clase in SECCIONES:
            mod  = __import__(modulo, fromlist=[clase])
            panel = getattr(mod, clase)()
            self.stack.addWidget(panel)

        return self.stack

    # ── Navegación ───────────────────────────────────────────────
    def _cambiar_panel(self, idx: int):
        self.stack.setCurrentIndex(idx)
        for i, btn in enumerate(self._botones):
            btn.setChecked(i == idx)

    def _centrar(self):
        geo = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            geo.center().x() - self.width() // 2,
            geo.center().y() - self.height() // 2,
        )
