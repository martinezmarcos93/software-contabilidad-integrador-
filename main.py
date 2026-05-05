"""
main.py — Punto de entrada del Software de Contabilidad Integrador
"""
import sys
from PyQt6.QtWidgets import QApplication
from ui.login import lanzar_app

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    lanzar_app()
    sys.exit(app.exec())
