"""
ui/login.py — Pantalla de inicio de sesión
Primera ejecución: formulario de configuración inicial.
"""
import json
import hashlib
import secrets
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QFormLayout, QGroupBox, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QGuiApplication

DATA_DIR          = Path(__file__).parent.parent / "data"
CREDENCIALES_PATH = DATA_DIR / "credenciales.json"
LOGO_PATH         = DATA_DIR / "logo1.jpg"

_ventanas = []   # referencias globales para evitar GC


def _hash(password: str, salt: str = "") -> str:
    return hashlib.sha256((salt + password).encode()).hexdigest()


def _icon() -> QIcon:
    return QIcon(str(LOGO_PATH)) if LOGO_PATH.exists() else QIcon()


def _centrar(widget: QWidget, w: int, h: int):
    widget.resize(w, h)
    geo = QGuiApplication.primaryScreen().availableGeometry()
    widget.move(geo.center().x() - w // 2, geo.center().y() - h // 2)


# ──────────────────────────────────────────────────────────────
class VentanaPrimerUso(QWidget):
    """Configuración inicial: solo se muestra cuando no existe credenciales.json."""

    def __init__(self, on_complete):
        super().__init__()
        self.on_complete = on_complete
        self.setWindowTitle("Configuración inicial")
        self.setWindowIcon(_icon())
        _centrar(self, 420, 360)

        grp  = QGroupBox("Bienvenido — Primera configuración")
        form = QFormLayout()

        self.inp_estudio = QLineEdit()
        self.inp_estudio.setPlaceholderText("Ej: Estudio Contable García")
        form.addRow("Nombre del estudio:", self.inp_estudio)

        self.inp_usuario = QLineEdit()
        self.inp_usuario.setPlaceholderText("Ej: admin")
        form.addRow("Usuario:", self.inp_usuario)

        self.inp_pass1 = QLineEdit()
        self.inp_pass1.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Contraseña:", self.inp_pass1)

        self.inp_pass2 = QLineEdit()
        self.inp_pass2.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Repetir contraseña:", self.inp_pass2)

        grp.setLayout(form)

        lbl_info = QLabel(
            "Estos datos se guardan localmente en data/credenciales.json.\n"
            "Para cambiarlos, eliminá ese archivo y reiniciá la aplicación."
        )
        lbl_info.setStyleSheet("color: #555; font-size: 11px;")
        lbl_info.setWordWrap(True)

        btn = QPushButton("Guardar y continuar")
        btn.clicked.connect(self._guardar)

        lay = QVBoxLayout()
        lay.addWidget(grp)
        lay.addWidget(lbl_info)
        lay.addWidget(btn)
        lay.setContentsMargins(20, 16, 20, 20)
        self.setLayout(lay)

    def _guardar(self):
        estudio  = self.inp_estudio.text().strip()
        usuario  = self.inp_usuario.text().strip()
        password = self.inp_pass1.text()
        repetir  = self.inp_pass2.text()

        if not estudio or not usuario or not password:
            QMessageBox.warning(self, "Error", "Completá todos los campos.")
            return
        if password != repetir:
            QMessageBox.warning(self, "Error", "Las contraseñas no coinciden.")
            return

        salt  = secrets.token_hex(16)
        creds = {
            "nombre_estudio": estudio,
            "usuario":        usuario,
            "salt":           salt,
            "password_hash":  _hash(password, salt),
        }
        DATA_DIR.mkdir(exist_ok=True)
        with open(CREDENCIALES_PATH, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False, indent=2)

        self.close()
        self.on_complete()


# ──────────────────────────────────────────────────────────────
class VentanaLogin(QWidget):
    def __init__(self, on_success):
        super().__init__()
        self.on_success = on_success
        self.setWindowTitle("Iniciar sesión")
        self.setWindowIcon(_icon())
        _centrar(self, 380, 270)

        with open(CREDENCIALES_PATH, "r", encoding="utf-8") as f:
            self._creds = json.load(f)

        estudio = self._creds.get("nombre_estudio", "Software Contable")
        titulo  = QLabel(estudio)
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        titulo.setStyleSheet("font-weight: bold; font-size: 14px; padding: 8px 0;")

        grp  = QGroupBox("Acceso")
        form = QFormLayout()

        self.inp_usuario = QLineEdit()
        self.inp_usuario.setText(self._creds.get("usuario_recordado", ""))
        form.addRow("Usuario:", self.inp_usuario)

        self.inp_pass = QLineEdit()
        self.inp_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_pass.returnPressed.connect(self._login)
        form.addRow("Contraseña:", self.inp_pass)

        self.chk_recordar = QCheckBox("Recordar usuario")
        self.chk_recordar.setChecked(bool(self._creds.get("recordar", False)))
        form.addRow("", self.chk_recordar)

        grp.setLayout(form)

        self.lbl_error = QLabel("")
        self.lbl_error.setStyleSheet("color: #e74c3c; font-size: 11px;")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn = QPushButton("Ingresar")
        btn.clicked.connect(self._login)

        lay = QVBoxLayout()
        lay.addWidget(titulo)
        lay.addWidget(grp)
        lay.addWidget(self.lbl_error)
        lay.addWidget(btn)
        lay.setContentsMargins(20, 12, 20, 20)
        self.setLayout(lay)

    def _login(self):
        usuario  = self.inp_usuario.text().strip()
        password = self.inp_pass.text()
        salt     = self._creds.get("salt", "")
        stored   = self._creds.get("password_hash", "")

        if usuario != self._creds.get("usuario", "") or _hash(password, salt) != stored:
            self.lbl_error.setText("Usuario o contraseña incorrectos.")
            self.inp_pass.clear()
            return

        recordar = self.chk_recordar.isChecked()
        self._creds["recordar"] = recordar
        if recordar:
            self._creds["usuario_recordado"] = usuario
        else:
            self._creds.pop("recordar", None)
            self._creds.pop("usuario_recordado", None)
        DATA_DIR.mkdir(exist_ok=True)
        with open(CREDENCIALES_PATH, "w", encoding="utf-8") as f:
            json.dump(self._creds, f, ensure_ascii=False, indent=2)

        nombre_estudio = self._creds.get("nombre_estudio", "Software Contable")
        self.close()
        self.on_success(nombre_estudio)


# ──────────────────────────────────────────────────────────────
def lanzar_app():
    _ventanas.clear()
    if not CREDENCIALES_PATH.exists():
        v = VentanaPrimerUso(on_complete=lanzar_app)
        _ventanas.append(v)
        v.show()
    else:
        from db.connection import init_db
        init_db()

        def abrir_principal(nombre_estudio: str):
            from ui.main_window import VentanaPrincipal
            _ventanas.clear()
            w = VentanaPrincipal(nombre_estudio)
            _ventanas.append(w)
            w.show()

        v = VentanaLogin(on_success=abrir_principal)
        _ventanas.append(v)
        v.show()
