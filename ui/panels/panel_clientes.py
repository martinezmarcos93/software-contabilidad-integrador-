"""
ui/panels/panel_clientes.py — Clientes: Monotributistas y Responsables Inscriptos
ABM completo · Búsqueda · Detalle · Cuenta Corriente
[Fase 2]
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QFormLayout, QTextEdit, QComboBox,
    QMessageBox, QSplitter, QFrame, QAbstractItemView, QGroupBox,
    QDateEdit, QDoubleSpinBox, QDialogButtonBox, QScrollArea,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from db.connection import conn_ctx

# ── Paleta Catppuccin Mocha ──────────────────────────────────
_BG          = "#24273a"
_BG2         = "#1e1e2e"
_BG3         = "#313244"
_ACCENT      = "#cba6f7"
_ACCENT2     = "#89b4fa"
_GREEN       = "#a6e3a1"
_RED         = "#f38ba8"
_YELLOW      = "#f9e2af"
_TEXT        = "#cdd6f4"
_TEXT_DIM    = "#a6adc8"
_TEXT_FAINT  = "#585b70"
_BORDER      = "#45475a"

STYLE_BASE = f"""
    QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 13px; }}
    QLineEdit, QTextEdit, QComboBox, QDoubleSpinBox, QDateEdit {{
        background: {_BG2}; border: 1px solid {_BORDER};
        border-radius: 5px; padding: 5px 8px; color: {_TEXT};
    }}
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
        border: 1px solid {_ACCENT};
    }}
    QGroupBox {{
        border: 1px solid {_BORDER}; border-radius: 6px;
        margin-top: 10px; font-weight: bold; color: {_ACCENT};
    }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}
    QPushButton {{
        background: {_BG3}; color: {_TEXT}; border: 1px solid {_BORDER};
        border-radius: 5px; padding: 6px 14px; font-size: 12px;
    }}
    QPushButton:hover {{ background: {_ACCENT}; color: {_BG2}; border: 1px solid {_ACCENT}; }}
    QPushButton:pressed {{ background: #b4befe; }}
    QTableWidget {{
        background: {_BG2}; gridline-color: {_BORDER};
        border: 1px solid {_BORDER}; border-radius: 5px;
        selection-background-color: {_BG3};
    }}
    QHeaderView::section {{
        background: {_BG3}; color: {_ACCENT}; border: none;
        padding: 6px; font-weight: bold; font-size: 12px;
    }}
    QTabWidget::pane {{ border: 1px solid {_BORDER}; border-radius: 6px; }}
    QTabBar::tab {{
        background: {_BG2}; color: {_TEXT_DIM}; padding: 8px 20px;
        border: 1px solid {_BORDER}; border-bottom: none;
        border-top-left-radius: 5px; border-top-right-radius: 5px;
    }}
    QTabBar::tab:selected {{ background: {_BG3}; color: {_ACCENT}; font-weight: bold; }}
    QSplitter::handle {{ background: {_BORDER}; }}
    QScrollArea {{ border: none; }}
    QLabel {{ color: {_TEXT}; }}
"""

CATEGORIAS_MONO = [
    "A","B","C","D","E","F","G","H","I","J","K","T","AK","BK","CK",
    "DK","EK","FK","GK","HK","IK","JK","KK","TK"
]


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _btn(text: str, color: str = _ACCENT) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {color}; color: {_BG2}; border-radius: 5px; "
        f"padding: 6px 14px; font-weight: bold; font-size: 12px; border: none; }}"
        f"QPushButton:hover {{ opacity: 0.85; }}"
    )
    return b


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet(f"color: {_BORDER};")
    return f


def _tabla(cols: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.setStyleSheet(
        f"QTableWidget {{ alternate-background-color: {_BG3}; }}"
    )
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(True)
    return t


def _item(text: str, color: str | None = None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text) if text is not None else "")
    it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
    if color:
        it.setForeground(QColor(color))
    return it


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: CUENTA CORRIENTE
# ══════════════════════════════════════════════════════════════

class DialogCuentaCorriente(QDialog):
    def __init__(self, tipo: str, cliente_id: int, nombre: str, parent=None):
        super().__init__(parent)
        self.tipo       = tipo
        self.cliente_id = cliente_id
        self.setWindowTitle(f"Cuenta Corriente — {nombre}")
        self.setMinimumSize(700, 500)
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)

        # Tabla de movimientos
        self.tabla = _tabla(["Fecha", "Descripción", "Debe", "Haber", "Saldo"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tabla)

        # Formulario nuevo movimiento
        grp = QGroupBox("Agregar movimiento")
        form = QFormLayout()

        self.inp_fecha = QDateEdit(QDate.currentDate())
        self.inp_fecha.setDisplayFormat("dd/MM/yyyy")
        self.inp_fecha.setCalendarPopup(True)
        form.addRow("Fecha:", self.inp_fecha)

        self.inp_desc = QLineEdit()
        self.inp_desc.setPlaceholderText("Descripción del movimiento")
        form.addRow("Descripción:", self.inp_desc)

        row_imp = QHBoxLayout()
        self.inp_debe = QDoubleSpinBox()
        self.inp_debe.setPrefix("$ ")
        self.inp_debe.setMaximum(9_999_999)
        self.inp_debe.setDecimals(2)
        row_imp.addWidget(QLabel("Debe:"))
        row_imp.addWidget(self.inp_debe)
        row_imp.addWidget(QLabel("   Haber:"))
        self.inp_haber = QDoubleSpinBox()
        self.inp_haber.setPrefix("$ ")
        self.inp_haber.setMaximum(9_999_999)
        self.inp_haber.setDecimals(2)
        row_imp.addWidget(self.inp_haber)
        form.addRow("Importes:", row_imp)

        grp.setLayout(form)
        lay.addWidget(grp)

        row_btns = QHBoxLayout()
        btn_add = _btn("＋ Agregar", _GREEN)
        btn_add.clicked.connect(self._agregar)
        btn_del = _btn("✕ Eliminar seleccionado", _RED)
        btn_del.clicked.connect(self._eliminar)
        btn_cer = QPushButton("Cerrar")
        btn_cer.clicked.connect(self.accept)
        row_btns.addWidget(btn_add)
        row_btns.addWidget(btn_del)
        row_btns.addStretch()
        row_btns.addWidget(btn_cer)
        lay.addLayout(row_btns)

        self._cargar()

    def _cargar(self):
        self.tabla.setRowCount(0)
        with conn_ctx() as conn:
            rows = conn.execute(
                "SELECT id, fecha, descripcion, debe, haber FROM cuenta_corriente "
                "WHERE tipo=? AND cliente_id=? ORDER BY fecha, id",
                (self.tipo, self.cliente_id)
            ).fetchall()

        saldo = 0.0
        self._ids = []
        for r in rows:
            saldo += r["debe"] - r["haber"]
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            self.tabla.setItem(ri, 0, _item(r["fecha"]))
            self.tabla.setItem(ri, 1, _item(r["descripcion"]))
            self.tabla.setItem(ri, 2, _item(f"${r['debe']:,.2f}", _RED if r["debe"] else None))
            self.tabla.setItem(ri, 3, _item(f"${r['haber']:,.2f}", _GREEN if r["haber"] else None))
            color = _RED if saldo > 0 else _GREEN if saldo < 0 else None
            self.tabla.setItem(ri, 4, _item(f"${saldo:,.2f}", color))
            self._ids.append(r["id"])

    def _agregar(self):
        desc  = self.inp_desc.text().strip()
        if not desc:
            QMessageBox.warning(self, "Error", "Ingresá una descripción.")
            return
        fecha = self.inp_fecha.date().toString("yyyy-MM-dd")
        debe  = self.inp_debe.value()
        haber = self.inp_haber.value()
        with conn_ctx() as conn:
            conn.execute(
                "INSERT INTO cuenta_corriente (tipo, cliente_id, fecha, descripcion, debe, haber) "
                "VALUES (?,?,?,?,?,?)",
                (self.tipo, self.cliente_id, fecha, desc, debe, haber)
            )
        self.inp_desc.clear()
        self.inp_debe.setValue(0)
        self.inp_haber.setValue(0)
        self._cargar()

    def _eliminar(self):
        row = self.tabla.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, "Confirmar", "¿Eliminar este movimiento?",
           QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        rec_id = self._ids[row]
        with conn_ctx() as conn:
            conn.execute("DELETE FROM cuenta_corriente WHERE id=?", (rec_id,))
        self._cargar()


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: DETALLE DEL CLIENTE
# ══════════════════════════════════════════════════════════════

class DialogDetalle(QDialog):
    def __init__(self, tipo: str, cliente_id: int, nombre: str, parent=None):
        super().__init__(parent)
        self.tipo       = tipo
        self.cliente_id = cliente_id
        self.setWindowTitle(f"Detalle — {nombre}")
        self.setMinimumSize(420, 400)
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)

        grp = QGroupBox("Datos de contacto y configuración")
        form = QFormLayout()

        self.inp_cel  = QLineEdit(); self.inp_cel.setPlaceholderText("Ej: 11-1234-5678")
        self.inp_mail = QLineEdit(); self.inp_mail.setPlaceholderText("Ej: cliente@mail.com")
        self.inp_banco = QLineEdit(); self.inp_banco.setPlaceholderText("Ej: Banco Nación")
        self.inp_cbu  = QLineEdit(); self.inp_cbu.setPlaceholderText("22 dígitos")
        self.inp_hon  = QDoubleSpinBox()
        self.inp_hon.setPrefix("$ "); self.inp_hon.setMaximum(9_999_999); self.inp_hon.setDecimals(2)
        self.txt_notas = QTextEdit(); self.txt_notas.setMaximumHeight(80)

        form.addRow("Celular:", self.inp_cel)
        form.addRow("E-mail:", self.inp_mail)
        form.addRow("Banco:", self.inp_banco)
        form.addRow("CBU:", self.inp_cbu)
        form.addRow("Honorario ($):", self.inp_hon)
        form.addRow("Notas:", self.txt_notas)
        grp.setLayout(form)
        lay.addWidget(grp)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._guardar)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        self._cargar()

    def _cargar(self):
        with conn_ctx() as conn:
            row = conn.execute(
                "SELECT * FROM clientes_detalle WHERE tipo=? AND cliente_id=?",
                (self.tipo, self.cliente_id)
            ).fetchone()
        if row:
            self.inp_cel.setText(row["cel"] or "")
            self.inp_mail.setText(row["mail"] or "")
            self.inp_banco.setText(row["banco"] or "")
            self.inp_cbu.setText(row["cbu"] or "")
            self.inp_hon.setValue(row["honorarios"] or 0)
            self.txt_notas.setPlainText(row["notas"] or "")

    def _guardar(self):
        with conn_ctx() as conn:
            conn.execute(
                """INSERT INTO clientes_detalle (tipo, cliente_id, cel, mail, banco, cbu, honorarios, notas)
                   VALUES (?,?,?,?,?,?,?,?)
                   ON CONFLICT(tipo, cliente_id) DO UPDATE SET
                     cel=excluded.cel, mail=excluded.mail, banco=excluded.banco,
                     cbu=excluded.cbu, honorarios=excluded.honorarios, notas=excluded.notas""",
                (self.tipo, self.cliente_id,
                 self.inp_cel.text().strip(), self.inp_mail.text().strip(),
                 self.inp_banco.text().strip(), self.inp_cbu.text().strip(),
                 self.inp_hon.value(), self.txt_notas.toPlainText().strip())
            )
        self.accept()


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: FORMULARIO MONOTRIBUTISTA
# ══════════════════════════════════════════════════════════════

class DialogMono(QDialog):
    def __init__(self, parent=None, datos: dict | None = None):
        super().__init__(parent)
        self.datos = datos  # None = nuevo, dict = editar
        self.setWindowTitle("Nuevo monotributista" if not datos else "Editar monotributista")
        self.setMinimumWidth(440)
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)
        grp = QGroupBox("Datos del cliente")
        form = QFormLayout()

        self.inp_nombre   = QLineEdit()
        self.inp_nombre.setPlaceholderText("Nombre y apellido o razón social")
        self.cmb_cat      = QComboBox()
        self.cmb_cat.addItems(CATEGORIAS_MONO)
        self.inp_actividad = QLineEdit()
        self.inp_cuit     = QLineEdit(); self.inp_cuit.setPlaceholderText("XX-XXXXXXXX-X")
        self.inp_afip     = QLineEdit(); self.inp_afip.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_agip     = QLineEdit(); self.inp_agip.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_iibb     = QLineEdit(); self.inp_iibb.setPlaceholderText("Nro IIBB")
        self.inp_obs      = QTextEdit(); self.inp_obs.setMaximumHeight(70)
        self.cmb_cond     = QComboBox()
        self.cmb_cond.addItems(["Activo", "Inactivo", "Baja"])

        form.addRow("Nombre / Razón social:", self.inp_nombre)
        form.addRow("Categoría:", self.cmb_cat)
        form.addRow("Actividad:", self.inp_actividad)
        form.addRow("CUIT:", self.inp_cuit)
        form.addRow("Clave AFIP/ARCA:", self.inp_afip)
        form.addRow("Clave AGIP/ARBA:", self.inp_agip)
        form.addRow("Nro IIBB:", self.inp_iibb)
        form.addRow("Observaciones:", self.inp_obs)
        form.addRow("Condición:", self.cmb_cond)
        grp.setLayout(form)
        lay.addWidget(grp)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validar)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        if datos:
            self._rellenar(datos)

    def _rellenar(self, d: dict):
        self.inp_nombre.setText(d.get("nombre", ""))
        idx = self.cmb_cat.findText(d.get("categoria", "A"))
        self.cmb_cat.setCurrentIndex(max(idx, 0))
        self.inp_actividad.setText(d.get("actividad", ""))
        self.inp_cuit.setText(d.get("cuit", ""))
        self.inp_afip.setText(d.get("clave_afip", ""))
        self.inp_agip.setText(d.get("clave_agip_arba", ""))
        self.inp_iibb.setText(d.get("iibb", ""))
        self.inp_obs.setPlainText(d.get("observaciones", ""))
        idx2 = self.cmb_cond.findText(d.get("condicion", "Activo"))
        self.cmb_cond.setCurrentIndex(max(idx2, 0))

    def _validar(self):
        if not self.inp_nombre.text().strip():
            QMessageBox.warning(self, "Error", "El nombre es obligatorio.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "nombre":          self.inp_nombre.text().strip(),
            "categoria":       self.cmb_cat.currentText(),
            "actividad":       self.inp_actividad.text().strip(),
            "cuit":            self.inp_cuit.text().strip(),
            "clave_afip":      self.inp_afip.text(),
            "clave_agip_arba": self.inp_agip.text(),
            "iibb":            self.inp_iibb.text().strip(),
            "observaciones":   self.inp_obs.toPlainText().strip(),
            "condicion":       self.cmb_cond.currentText(),
        }


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: FORMULARIO RESPONSABLE INSCRIPTO
# ══════════════════════════════════════════════════════════════

class DialogRI(QDialog):
    def __init__(self, parent=None, datos: dict | None = None):
        super().__init__(parent)
        self.datos = datos
        self.setWindowTitle("Nuevo RI" if not datos else "Editar Responsable Inscripto")
        self.setMinimumWidth(440)
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)
        grp = QGroupBox("Datos del cliente")
        form = QFormLayout()

        self.inp_razon   = QLineEdit(); self.inp_razon.setPlaceholderText("Razón social")
        self.inp_cuit    = QLineEdit(); self.inp_cuit.setPlaceholderText("XX-XXXXXXXX-X")
        self.inp_arca    = QLineEdit(); self.inp_arca.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_arba    = QLineEdit(); self.inp_arba.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_agip    = QLineEdit(); self.inp_agip.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_iibb    = QLineEdit(); self.inp_iibb.setPlaceholderText("Condición IIBB")
        self.inp_obs     = QTextEdit(); self.inp_obs.setMaximumHeight(70)
        self.cmb_cond    = QComboBox()
        self.cmb_cond.addItems(["Activo", "Inactivo", "Baja"])

        form.addRow("Razón social:", self.inp_razon)
        form.addRow("CUIT:", self.inp_cuit)
        form.addRow("Clave ARCA:", self.inp_arca)
        form.addRow("Clave ARBA:", self.inp_arba)
        form.addRow("Clave AGIP:", self.inp_agip)
        form.addRow("Cond. IIBB:", self.inp_iibb)
        form.addRow("Observaciones:", self.inp_obs)
        form.addRow("Condición:", self.cmb_cond)
        grp.setLayout(form)
        lay.addWidget(grp)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validar)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

        if datos:
            self._rellenar(datos)

    def _rellenar(self, d: dict):
        self.inp_razon.setText(d.get("razon_social", ""))
        self.inp_cuit.setText(d.get("cuit", ""))
        self.inp_arca.setText(d.get("clave_arca", ""))
        self.inp_arba.setText(d.get("clave_arba", ""))
        self.inp_agip.setText(d.get("clave_agip", ""))
        self.inp_iibb.setText(d.get("condicion_iibb", ""))
        self.inp_obs.setPlainText(d.get("observaciones", ""))
        idx = self.cmb_cond.findText(d.get("condicion", "Activo"))
        self.cmb_cond.setCurrentIndex(max(idx, 0))

    def _validar(self):
        if not self.inp_razon.text().strip():
            QMessageBox.warning(self, "Error", "La razón social es obligatoria.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "razon_social":   self.inp_razon.text().strip(),
            "cuit":           self.inp_cuit.text().strip(),
            "clave_arca":     self.inp_arca.text(),
            "clave_arba":     self.inp_arba.text(),
            "clave_agip":     self.inp_agip.text(),
            "condicion_iibb": self.inp_iibb.text().strip(),
            "observaciones":  self.inp_obs.toPlainText().strip(),
            "condicion":      self.cmb_cond.currentText(),
        }


# ══════════════════════════════════════════════════════════════
#  TAB: MONOTRIBUTISTAS
# ══════════════════════════════════════════════════════════════

class TabMonotributistas(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Barra superior
        top = QHBoxLayout()
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("🔍  Buscar por nombre, CUIT, categoría...")
        self.inp_buscar.textChanged.connect(self._buscar)
        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItems(["Todos", "Activo", "Inactivo", "Baja"])
        self.cmb_filtro.currentTextChanged.connect(self._buscar)

        btn_nuevo = _btn("＋ Nuevo", _GREEN)
        btn_nuevo.clicked.connect(self._nuevo)

        top.addWidget(self.inp_buscar, 3)
        top.addWidget(self.cmb_filtro, 1)
        top.addWidget(btn_nuevo)
        lay.addLayout(top)

        # Tabla
        self.tabla = _tabla(["ID", "Nombre", "Cat.", "CUIT", "Actividad", "Condición"])
        self.tabla.setColumnWidth(0, 45)
        self.tabla.setColumnWidth(2, 50)
        self.tabla.setColumnWidth(3, 130)
        self.tabla.setColumnWidth(5, 80)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabla.doubleClicked.connect(self._editar)
        lay.addWidget(self.tabla)

        # Botonera inferior
        bot = QHBoxLayout()
        btn_edit    = QPushButton("✏️  Editar")
        btn_detalle = QPushButton("📋  Detalle")
        btn_cc      = QPushButton("📒  Cuenta Corriente")
        btn_del     = QPushButton("🗑️  Eliminar")
        btn_del.setStyleSheet(
            f"QPushButton {{ color: {_RED}; border: 1px solid {_RED}; border-radius: 5px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: {_RED}; color: {_BG2}; }}"
        )
        btn_edit.clicked.connect(self._editar)
        btn_detalle.clicked.connect(self._detalle)
        btn_cc.clicked.connect(self._cuenta_corriente)
        btn_del.clicked.connect(self._eliminar)

        bot.addWidget(btn_edit)
        bot.addWidget(btn_detalle)
        bot.addWidget(btn_cc)
        bot.addStretch()
        bot.addWidget(btn_del)
        lay.addLayout(bot)

        self._cargar()

    # ── DB ────────────────────────────────────────────────────
    def _cargar(self, filtro: str = "", condicion: str = "Todos"):
        self.tabla.setRowCount(0)
        with conn_ctx() as conn:
            q = "SELECT * FROM monotributistas WHERE 1=1"
            params: list = []
            if filtro:
                q += " AND (nombre LIKE ? OR cuit LIKE ? OR categoria LIKE ?)"
                p = f"%{filtro}%"
                params += [p, p, p]
            if condicion != "Todos":
                q += " AND condicion=?"
                params.append(condicion)
            q += " ORDER BY nombre"
            rows = conn.execute(q, params).fetchall()

        self._rows = rows
        for r in rows:
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            self.tabla.setItem(ri, 0, _item(r["id"]))
            self.tabla.setItem(ri, 1, _item(r["nombre"]))
            self.tabla.setItem(ri, 2, _item(r["categoria"], _ACCENT))
            self.tabla.setItem(ri, 3, _item(r["cuit"]))
            self.tabla.setItem(ri, 4, _item(r["actividad"]))
            cond_color = {
                "Activo": _GREEN, "Inactivo": _YELLOW, "Baja": _RED
            }.get(r["condicion"], _TEXT_DIM)
            self.tabla.setItem(ri, 5, _item(r["condicion"], cond_color))

    def _buscar(self):
        self._cargar(self.inp_buscar.text().strip(), self.cmb_filtro.currentText())

    def _fila_actual(self) -> dict | None:
        row = self.tabla.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "Sin selección", "Seleccioná un cliente primero.")
            return None
        return dict(self._rows[row])

    # ── Acciones ──────────────────────────────────────────────
    def _nuevo(self):
        dlg = DialogMono(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "INSERT INTO monotributistas (nombre,categoria,actividad,cuit,clave_afip,"
                    "clave_agip_arba,iibb,observaciones,condicion) VALUES (?,?,?,?,?,?,?,?,?)",
                    (d["nombre"], d["categoria"], d["actividad"], d["cuit"],
                     d["clave_afip"], d["clave_agip_arba"], d["iibb"],
                     d["observaciones"], d["condicion"])
                )
            self._buscar()

    def _editar(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogMono(self, datos=datos)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "UPDATE monotributistas SET nombre=?,categoria=?,actividad=?,cuit=?,"
                    "clave_afip=?,clave_agip_arba=?,iibb=?,observaciones=?,condicion=? WHERE id=?",
                    (d["nombre"], d["categoria"], d["actividad"], d["cuit"],
                     d["clave_afip"], d["clave_agip_arba"], d["iibb"],
                     d["observaciones"], d["condicion"], datos["id"])
                )
            self._buscar()

    def _detalle(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogDetalle("mono", datos["id"], datos["nombre"], self)
        dlg.exec()

    def _cuenta_corriente(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogCuentaCorriente("mono", datos["id"], datos["nombre"], self)
        dlg.exec()

    def _eliminar(self):
        datos = self._fila_actual()
        if not datos:
            return
        if QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar a '{datos['nombre']}'?\nSe eliminarán también su detalle y cuenta corriente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        with conn_ctx() as conn:
            cid = datos["id"]
            conn.execute("DELETE FROM cuenta_corriente WHERE tipo='mono' AND cliente_id=?", (cid,))
            conn.execute("DELETE FROM clientes_detalle WHERE tipo='mono' AND cliente_id=?", (cid,))
            conn.execute("DELETE FROM monotributistas WHERE id=?", (cid,))
        self._buscar()


# ══════════════════════════════════════════════════════════════
#  TAB: RESPONSABLES INSCRIPTOS
# ══════════════════════════════════════════════════════════════

class TabResponsables(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Barra superior
        top = QHBoxLayout()
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("🔍  Buscar por razón social, CUIT...")
        self.inp_buscar.textChanged.connect(self._buscar)
        self.cmb_filtro = QComboBox()
        self.cmb_filtro.addItems(["Todos", "Activo", "Inactivo", "Baja"])
        self.cmb_filtro.currentTextChanged.connect(self._buscar)

        btn_nuevo = _btn("＋ Nuevo", _GREEN)
        btn_nuevo.clicked.connect(self._nuevo)

        top.addWidget(self.inp_buscar, 3)
        top.addWidget(self.cmb_filtro, 1)
        top.addWidget(btn_nuevo)
        lay.addLayout(top)

        # Tabla
        self.tabla = _tabla(["ID", "Razón Social", "CUIT", "Cond. IIBB", "Condición"])
        self.tabla.setColumnWidth(0, 45)
        self.tabla.setColumnWidth(2, 130)
        self.tabla.setColumnWidth(3, 160)
        self.tabla.setColumnWidth(4, 80)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.doubleClicked.connect(self._editar)
        lay.addWidget(self.tabla)

        # Botonera inferior
        bot = QHBoxLayout()
        btn_edit    = QPushButton("✏️  Editar")
        btn_detalle = QPushButton("📋  Detalle")
        btn_cc      = QPushButton("📒  Cuenta Corriente")
        btn_del     = QPushButton("🗑️  Eliminar")
        btn_del.setStyleSheet(
            f"QPushButton {{ color: {_RED}; border: 1px solid {_RED}; border-radius: 5px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: {_RED}; color: {_BG2}; }}"
        )
        btn_edit.clicked.connect(self._editar)
        btn_detalle.clicked.connect(self._detalle)
        btn_cc.clicked.connect(self._cuenta_corriente)
        btn_del.clicked.connect(self._eliminar)

        bot.addWidget(btn_edit)
        bot.addWidget(btn_detalle)
        bot.addWidget(btn_cc)
        bot.addStretch()
        bot.addWidget(btn_del)
        lay.addLayout(bot)

        self._cargar()

    def _cargar(self, filtro: str = "", condicion: str = "Todos"):
        self.tabla.setRowCount(0)
        with conn_ctx() as conn:
            q = "SELECT * FROM responsables_inscriptos WHERE 1=1"
            params: list = []
            if filtro:
                q += " AND (razon_social LIKE ? OR cuit LIKE ?)"
                p = f"%{filtro}%"
                params += [p, p]
            if condicion != "Todos":
                q += " AND condicion=?"
                params.append(condicion)
            q += " ORDER BY razon_social"
            rows = conn.execute(q, params).fetchall()

        self._rows = rows
        for r in rows:
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            self.tabla.setItem(ri, 0, _item(r["id"]))
            self.tabla.setItem(ri, 1, _item(r["razon_social"]))
            self.tabla.setItem(ri, 2, _item(r["cuit"]))
            self.tabla.setItem(ri, 3, _item(r["condicion_iibb"]))
            cond_color = {
                "Activo": _GREEN, "Inactivo": _YELLOW, "Baja": _RED
            }.get(r["condicion"], _TEXT_DIM)
            self.tabla.setItem(ri, 4, _item(r["condicion"], cond_color))

    def _buscar(self):
        self._cargar(self.inp_buscar.text().strip(), self.cmb_filtro.currentText())

    def _fila_actual(self) -> dict | None:
        row = self.tabla.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "Sin selección", "Seleccioná un cliente primero.")
            return None
        return dict(self._rows[row])

    def _nuevo(self):
        dlg = DialogRI(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "INSERT INTO responsables_inscriptos (razon_social,cuit,clave_arca,clave_arba,"
                    "clave_agip,condicion_iibb,observaciones,condicion) VALUES (?,?,?,?,?,?,?,?)",
                    (d["razon_social"], d["cuit"], d["clave_arca"], d["clave_arba"],
                     d["clave_agip"], d["condicion_iibb"], d["observaciones"], d["condicion"])
                )
            self._buscar()

    def _editar(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogRI(self, datos=datos)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "UPDATE responsables_inscriptos SET razon_social=?,cuit=?,clave_arca=?,"
                    "clave_arba=?,clave_agip=?,condicion_iibb=?,observaciones=?,condicion=? WHERE id=?",
                    (d["razon_social"], d["cuit"], d["clave_arca"], d["clave_arba"],
                     d["clave_agip"], d["condicion_iibb"], d["observaciones"],
                     d["condicion"], datos["id"])
                )
            self._buscar()

    def _detalle(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogDetalle("resp", datos["id"], datos["razon_social"], self)
        dlg.exec()

    def _cuenta_corriente(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogCuentaCorriente("resp", datos["id"], datos["razon_social"], self)
        dlg.exec()

    def _eliminar(self):
        datos = self._fila_actual()
        if not datos:
            return
        if QMessageBox.question(
            self, "Confirmar",
            f"¿Eliminar '{datos['razon_social']}'?\nSe eliminarán también su detalle y cuenta corriente.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        with conn_ctx() as conn:
            cid = datos["id"]
            conn.execute("DELETE FROM cuenta_corriente WHERE tipo='resp' AND cliente_id=?", (cid,))
            conn.execute("DELETE FROM clientes_detalle WHERE tipo='resp' AND cliente_id=?", (cid,))
            conn.execute("DELETE FROM responsables_inscriptos WHERE id=?", (cid,))
        self._buscar()


# ══════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════════

class PanelClientes(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {_BG2}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("👥  Clientes")
        lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Monotributistas · Responsables Inscriptos")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        lay.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(TabMonotributistas(), "🟢  Monotributistas")
        tabs.addTab(TabResponsables(),    "🔵  Responsables Inscriptos")
        lay.addWidget(tabs)
