"""
ui/panels/panel_honorarios.py — Honorarios con actualización por índice INDEC
Registro de cobros · Resumen por cliente · Actualización masiva
[Fase 2]
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QFormLayout, QTextEdit, QComboBox,
    QMessageBox, QFrame, QAbstractItemView, QGroupBox,
    QDateEdit, QDoubleSpinBox, QDialogButtonBox, QSplitter,
    QScrollArea, QCheckBox, QProgressDialog
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
import urllib.request
import json
from datetime import datetime

from db.connection import conn_ctx

# ── Paleta Catppuccin Mocha (idéntica a panel_clientes) ──────
_BG          = "#24273a"
_BG2         = "#1e1e2e"
_BG3         = "#313244"
_ACCENT      = "#cba6f7"
_ACCENT2     = "#89b4fa"
_GREEN       = "#a6e3a1"
_RED         = "#f38ba8"
_YELLOW      = "#f9e2af"
_TEAL        = "#94e2d5"
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
    QCheckBox {{ color: {_TEXT}; spacing: 6px; }}
    QScrollArea {{ border: none; }}
    QLabel {{ color: {_TEXT}; }}
    QSplitter::handle {{ background: {_BORDER}; width: 1px; }}
"""


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════

def _btn(text: str, color: str = _ACCENT) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {color}; color: {_BG2}; border-radius: 5px; "
        f"padding: 6px 14px; font-weight: bold; font-size: 12px; border: none; }}"
        f"QPushButton:hover {{ background: {color}cc; }}"
    )
    return b


def _tabla(cols: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(cols))
    t.setHorizontalHeaderLabels(cols)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setAlternatingRowColors(True)
    t.setStyleSheet(f"QTableWidget {{ alternate-background-color: {_BG3}; }}")
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    return t


def _item(text: str, color: str | None = None, bold: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text) if text is not None else "")
    it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
    if color:
        it.setForeground(QColor(color))
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    return it


def _cargar_clientes_combo(combo: QComboBox, incluir_todos: bool = True):
    """Rellena un combo con todos los clientes (mono + RI)."""
    combo.clear()
    if incluir_todos:
        combo.addItem("— Todos los clientes —", userData=None)
    with conn_ctx() as conn:
        monos = conn.execute(
            "SELECT id, nombre FROM monotributistas WHERE condicion='Activo' ORDER BY nombre"
        ).fetchall()
        resp  = conn.execute(
            "SELECT id, razon_social FROM responsables_inscriptos WHERE condicion='Activo' ORDER BY razon_social"
        ).fetchall()
    for r in monos:
        combo.addItem(f"[M] {r['nombre']}", userData=("mono", r["id"]))
    for r in resp:
        combo.addItem(f"[RI] {r['razon_social']}", userData=("resp", r["id"]))


def _nombre_cliente(tipo: str, cid: int) -> str:
    with conn_ctx() as conn:
        if tipo == "mono":
            r = conn.execute("SELECT nombre FROM monotributistas WHERE id=?", (cid,)).fetchone()
            return r["nombre"] if r else "?"
        r = conn.execute("SELECT razon_social FROM responsables_inscriptos WHERE id=?", (cid,)).fetchone()
        return r["razon_social"] if r else "?"


# ══════════════════════════════════════════════════════════════
#  WORKER: consulta IPC INDEC en hilo aparte
# ══════════════════════════════════════════════════════════════

class IndecWorker(QThread):
    """Descarga el índice IPC INDEC de la API pública."""
    resultado = pyqtSignal(float, str)   # variacion_pct, periodo_label
    error     = pyqtSignal(str)

    def __init__(self, mes_base: str):
        super().__init__()
        self.mes_base = mes_base          # "YYYY-MM"

    def run(self):
        try:
            # API pública INDEC: series de tiempo
            url = (
                "https://apis.datos.gob.ar/series/api/series/"
                "?ids=148.3_INIVELNAL_DICI_M_26:percent_change"
                "&limit=2&sort=desc&format=json"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode())
            series = data["data"]          # [[fecha, valor], ...]
            if not series:
                self.error.emit("Sin datos en la respuesta INDEC.")
                return
            fecha, valor = series[0]       # más reciente
            self.resultado.emit(float(valor), fecha[:7])
        except Exception as e:
            self.error.emit(str(e))


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: NUEVO / EDITAR COBRO
# ══════════════════════════════════════════════════════════════

class DialogCobro(QDialog):
    def __init__(self, parent=None, datos: dict | None = None):
        super().__init__(parent)
        self.datos = datos
        self.setWindowTitle("Registrar cobro" if not datos else "Editar cobro")
        self.setMinimumWidth(460)
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)

        grp = QGroupBox("Datos del cobro")
        form = QFormLayout()

        # Cliente
        self.cmb_cliente = QComboBox()
        _cargar_clientes_combo(self.cmb_cliente, incluir_todos=False)
        form.addRow("Cliente:", self.cmb_cliente)

        # Fecha
        self.inp_fecha = QDateEdit(QDate.currentDate())
        self.inp_fecha.setDisplayFormat("dd/MM/yyyy")
        self.inp_fecha.setCalendarPopup(True)
        form.addRow("Fecha:", self.inp_fecha)

        # Descripción
        self.inp_desc = QLineEdit()
        self.inp_desc.setPlaceholderText("Ej: Honorarios mayo 2025")
        form.addRow("Descripción:", self.inp_desc)

        # Importes
        row_imp = QHBoxLayout()
        self.inp_debe = QDoubleSpinBox()
        self.inp_debe.setPrefix("$ "); self.inp_debe.setMaximum(9_999_999); self.inp_debe.setDecimals(2)
        self.inp_haber = QDoubleSpinBox()
        self.inp_haber.setPrefix("$ "); self.inp_haber.setMaximum(9_999_999); self.inp_haber.setDecimals(2)
        row_imp.addWidget(QLabel("Debe:"));  row_imp.addWidget(self.inp_debe)
        row_imp.addSpacing(12)
        row_imp.addWidget(QLabel("Haber:")); row_imp.addWidget(self.inp_haber)
        form.addRow("Importes:", row_imp)

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
        # Seleccionar cliente
        for i in range(self.cmb_cliente.count()):
            ud = self.cmb_cliente.itemData(i)
            if ud and ud[0] == d["tipo"] and ud[1] == d["cliente_id"]:
                self.cmb_cliente.setCurrentIndex(i)
                break
        fecha = QDate.fromString(d["fecha"], "yyyy-MM-dd")
        self.inp_fecha.setDate(fecha if fecha.isValid() else QDate.currentDate())
        self.inp_desc.setText(d.get("descripcion", ""))
        self.inp_debe.setValue(d.get("debe", 0))
        self.inp_haber.setValue(d.get("haber", 0))

    def _validar(self):
        if self.cmb_cliente.currentData() is None:
            QMessageBox.warning(self, "Error", "Seleccioná un cliente.")
            return
        if not self.inp_desc.text().strip():
            QMessageBox.warning(self, "Error", "Ingresá una descripción.")
            return
        self.accept()

    def get_data(self) -> dict:
        tipo, cid = self.cmb_cliente.currentData()
        return {
            "tipo":        tipo,
            "cliente_id":  cid,
            "fecha":       self.inp_fecha.date().toString("yyyy-MM-dd"),
            "descripcion": self.inp_desc.text().strip(),
            "debe":        self.inp_debe.value(),
            "haber":       self.inp_haber.value(),
        }


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: ACTUALIZACIÓN MASIVA POR ÍNDICE
# ══════════════════════════════════════════════════════════════

class DialogActualizacion(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Actualización de honorarios por índice")
        self.setMinimumWidth(520)
        self.setStyleSheet(STYLE_BASE)
        self._worker = None

        lay = QVBoxLayout(self)

        # ── Sección INDEC ─────────────────────────────────────
        grp_indec = QGroupBox("Índice INDEC (IPC Nacional — variación mensual)")
        gi = QVBoxLayout()

        row_fetch = QHBoxLayout()
        self.lbl_indec = QLabel("Variación: —")
        self.lbl_indec.setStyleSheet(f"color: {_YELLOW}; font-weight: bold;")
        self.btn_fetch = _btn("⬇  Obtener último IPC", _ACCENT2)
        self.btn_fetch.clicked.connect(self._fetch_indec)
        row_fetch.addWidget(self.lbl_indec)
        row_fetch.addStretch()
        row_fetch.addWidget(self.btn_fetch)
        gi.addLayout(row_fetch)

        row_manual = QHBoxLayout()
        row_manual.addWidget(QLabel("O ingresá manualmente (%):"))
        self.inp_pct = QDoubleSpinBox()
        self.inp_pct.setRange(-100, 1000); self.inp_pct.setDecimals(4)
        self.inp_pct.setSuffix(" %")
        row_manual.addWidget(self.inp_pct)
        row_manual.addStretch()
        gi.addLayout(row_manual)
        grp_indec.setLayout(gi)
        lay.addWidget(grp_indec)

        # ── Selección de clientes ─────────────────────────────
        grp_cli = QGroupBox("Clientes a actualizar")
        gc = QVBoxLayout()

        row_sel = QHBoxLayout()
        btn_todos    = QPushButton("Seleccionar todos")
        btn_ninguno  = QPushButton("Deseleccionar todos")
        btn_todos.clicked.connect(lambda: self._set_todos(True))
        btn_ninguno.clicked.connect(lambda: self._set_todos(False))
        row_sel.addWidget(btn_todos); row_sel.addWidget(btn_ninguno); row_sel.addStretch()
        gc.addLayout(row_sel)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        inner = QWidget()
        self._checks_layout = QVBoxLayout(inner)
        scroll.setWidget(inner)
        gc.addWidget(scroll)
        grp_cli.setLayout(gc)
        lay.addWidget(grp_cli)

        # ── Vista previa ──────────────────────────────────────
        grp_prev = QGroupBox("Vista previa")
        gp = QVBoxLayout()
        self.tabla_prev = _tabla(["Cliente", "Actual ($)", "Nuevo ($)", "Diferencia ($)"])
        self.tabla_prev.setMaximumHeight(160)
        gp.addWidget(self.tabla_prev)
        grp_prev.setLayout(gp)
        lay.addWidget(grp_prev)

        # ── Botones ───────────────────────────────────────────
        row_btns = QHBoxLayout()
        btn_prev = _btn("👁  Previsualizar", _ACCENT2)
        btn_prev.clicked.connect(self._previsualizar)
        btn_aplic = _btn("✅  Aplicar actualización", _GREEN)
        btn_aplic.clicked.connect(self._aplicar)
        btn_cer = QPushButton("Cancelar")
        btn_cer.clicked.connect(self.reject)
        row_btns.addWidget(btn_prev)
        row_btns.addWidget(btn_aplic)
        row_btns.addStretch()
        row_btns.addWidget(btn_cer)
        lay.addLayout(row_btns)

        self._clientes: list[dict] = []
        self._checks:  list[QCheckBox] = []
        self._cargar_clientes()

    def _cargar_clientes(self):
        # Limpiar checks anteriores
        while self._checks_layout.count():
            item = self._checks_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._checks.clear()
        self._clientes.clear()

        with conn_ctx() as conn:
            monos = conn.execute(
                "SELECT cd.cliente_id, m.nombre AS nombre, cd.honorarios, 'mono' AS tipo "
                "FROM clientes_detalle cd "
                "JOIN monotributistas m ON m.id=cd.cliente_id "
                "WHERE cd.tipo='mono' AND cd.honorarios > 0 ORDER BY m.nombre"
            ).fetchall()
            resp = conn.execute(
                "SELECT cd.cliente_id, r.razon_social AS nombre, cd.honorarios, 'resp' AS tipo "
                "FROM clientes_detalle cd "
                "JOIN responsables_inscriptos r ON r.id=cd.cliente_id "
                "WHERE cd.tipo='resp' AND cd.honorarios > 0 ORDER BY r.razon_social"
            ).fetchall()

        for r in list(monos) + list(resp):
            d = dict(r)
            self._clientes.append(d)
            prefix = "[M]" if d["tipo"] == "mono" else "[RI]"
            chk = QCheckBox(f"{prefix} {d['nombre']}  — actual: ${d['honorarios']:,.2f}")
            chk.setChecked(True)
            self._checks_layout.addWidget(chk)
            self._checks.append(chk)

        if not self._clientes:
            self._checks_layout.addWidget(
                QLabel("No hay clientes con honorario configurado.\n"
                       "Configurá el honorario en Clientes → Detalle.")
            )

    def _set_todos(self, estado: bool):
        for chk in self._checks:
            chk.setChecked(estado)

    def _fetch_indec(self):
        self.btn_fetch.setEnabled(False)
        self.lbl_indec.setText("Consultando INDEC...")
        self._worker = IndecWorker("auto")
        self._worker.resultado.connect(self._on_indec_ok)
        self._worker.error.connect(self._on_indec_err)
        self._worker.start()

    def _on_indec_ok(self, pct: float, periodo: str):
        self.inp_pct.setValue(pct)
        self.lbl_indec.setText(f"IPC {periodo}: {pct:.4f}%")
        self.btn_fetch.setEnabled(True)

    def _on_indec_err(self, msg: str):
        self.lbl_indec.setText("Error al consultar INDEC")
        QMessageBox.warning(self, "Error INDEC",
            f"No se pudo obtener el índice:\n{msg}\n\nIngresalo manualmente.")
        self.btn_fetch.setEnabled(True)

    def _seleccionados(self) -> list[dict]:
        return [c for c, chk in zip(self._clientes, self._checks) if chk.isChecked()]

    def _previsualizar(self):
        pct = self.inp_pct.value()
        selec = self._seleccionados()
        self.tabla_prev.setRowCount(0)
        for c in selec:
            nuevo = c["honorarios"] * (1 + pct / 100)
            diff  = nuevo - c["honorarios"]
            ri = self.tabla_prev.rowCount()
            self.tabla_prev.insertRow(ri)
            prefix = "[M]" if c["tipo"] == "mono" else "[RI]"
            self.tabla_prev.setItem(ri, 0, _item(f"{prefix} {c['nombre']}"))
            self.tabla_prev.setItem(ri, 1, _item(f"${c['honorarios']:,.2f}"))
            self.tabla_prev.setItem(ri, 2, _item(f"${nuevo:,.2f}", _GREEN))
            self.tabla_prev.setItem(ri, 3, _item(f"${diff:,.2f}", _ACCENT))

    def _aplicar(self):
        pct    = self.inp_pct.value()
        selec  = self._seleccionados()
        if not selec:
            QMessageBox.warning(self, "Sin selección", "No hay clientes seleccionados.")
            return
        if pct == 0:
            QMessageBox.warning(self, "Sin porcentaje", "El porcentaje de actualización es 0.")
            return
        if QMessageBox.question(
            self, "Confirmar",
            f"¿Actualizar {len(selec)} cliente(s) un {pct:.4f}%?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return

        with conn_ctx() as conn:
            for c in selec:
                nuevo = c["honorarios"] * (1 + pct / 100)
                conn.execute(
                    "UPDATE clientes_detalle SET honorarios=? WHERE tipo=? AND cliente_id=?",
                    (round(nuevo, 2), c["tipo"], c["cliente_id"])
                )
            conn.execute(
                "INSERT INTO historial_actualizaciones (fecha, porcentaje, clientes_afect, notas) "
                "VALUES (?, ?, ?, ?)",
                (datetime.now().strftime("%d/%m/%Y %H:%M"), pct, len(selec), "")
            )
        QMessageBox.information(self, "Listo", f"{len(selec)} honorario(s) actualizado(s).")
        self.accept()


# ══════════════════════════════════════════════════════════════
#  TAB: REGISTRO DE COBROS
# ══════════════════════════════════════════════════════════════

class TabRegistro(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Barra superior
        top = QHBoxLayout()
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setPlaceholderText("🔍  Buscar por descripción...")
        self.inp_buscar.textChanged.connect(self._buscar)

        self.cmb_cliente = QComboBox()
        _cargar_clientes_combo(self.cmb_cliente, incluir_todos=True)
        self.cmb_cliente.currentIndexChanged.connect(self._buscar)

        self.inp_desde = QDateEdit(QDate(QDate.currentDate().year(), 1, 1))
        self.inp_desde.setDisplayFormat("dd/MM/yyyy")
        self.inp_desde.setCalendarPopup(True)
        self.inp_desde.dateChanged.connect(self._buscar)

        self.inp_hasta = QDateEdit(QDate.currentDate())
        self.inp_hasta.setDisplayFormat("dd/MM/yyyy")
        self.inp_hasta.setCalendarPopup(True)
        self.inp_hasta.dateChanged.connect(self._buscar)

        btn_nuevo = _btn("＋ Cobro", _GREEN)
        btn_nuevo.clicked.connect(self._nuevo)

        top.addWidget(QLabel("Cliente:"))
        top.addWidget(self.cmb_cliente, 2)
        top.addWidget(QLabel("  Desde:"))
        top.addWidget(self.inp_desde)
        top.addWidget(QLabel("  Hasta:"))
        top.addWidget(self.inp_hasta)
        top.addWidget(self.inp_buscar, 2)
        top.addWidget(btn_nuevo)
        lay.addLayout(top)

        # Tabla
        self.tabla = _tabla(["ID", "Fecha", "Cliente", "Descripción", "Debe", "Haber"])
        self.tabla.setColumnWidth(0, 45)
        self.tabla.setColumnWidth(1, 100)
        self.tabla.setColumnWidth(2, 180)
        self.tabla.setColumnWidth(4, 110)
        self.tabla.setColumnWidth(5, 110)
        self.tabla.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tabla.doubleClicked.connect(self._editar)
        lay.addWidget(self.tabla)

        # Totales + botonera
        bot = QHBoxLayout()
        btn_edit = QPushButton("✏️  Editar")
        btn_del  = QPushButton("🗑️  Eliminar")
        btn_del.setStyleSheet(
            f"QPushButton {{ color: {_RED}; border: 1px solid {_RED}; border-radius: 5px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: {_RED}; color: {_BG2}; }}"
        )
        btn_edit.clicked.connect(self._editar)
        btn_del.clicked.connect(self._eliminar)

        self.lbl_totales = QLabel()
        self.lbl_totales.setStyleSheet(f"color: {_ACCENT}; font-weight: bold;")

        bot.addWidget(btn_edit)
        bot.addWidget(btn_del)
        bot.addStretch()
        bot.addWidget(self.lbl_totales)
        lay.addLayout(bot)

        self._rows: list = []
        self._ids:  list[int] = []
        self._cargar()

    def _cargar(self, filtro_desc: str = "", filtro_cli=None,
                desde: str = "2000-01-01", hasta: str = "2099-12-31"):
        self.tabla.setRowCount(0)
        self._rows.clear(); self._ids.clear()

        with conn_ctx() as conn:
            q = """
                SELECT h.id, h.fecha, h.tipo, h.cliente_id, h.descripcion, h.debe, h.haber
                FROM honorarios_cobrados h
                WHERE h.fecha BETWEEN ? AND ?
            """
            params: list = [desde, hasta]
            if filtro_cli:
                q += " AND h.tipo=? AND h.cliente_id=?"
                params += [filtro_cli[0], filtro_cli[1]]
            if filtro_desc:
                q += " AND h.descripcion LIKE ?"
                params.append(f"%{filtro_desc}%")
            q += " ORDER BY h.fecha DESC, h.id DESC"
            rows = conn.execute(q, params).fetchall()

        total_debe = total_haber = 0.0
        for r in rows:
            nombre = _nombre_cliente(r["tipo"], r["cliente_id"])
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            self.tabla.setItem(ri, 0, _item(r["id"]))
            self.tabla.setItem(ri, 1, _item(r["fecha"]))
            self.tabla.setItem(ri, 2, _item(nombre))
            self.tabla.setItem(ri, 3, _item(r["descripcion"]))
            self.tabla.setItem(ri, 4, _item(f"${r['debe']:,.2f}", _RED if r["debe"] else _TEXT_FAINT))
            self.tabla.setItem(ri, 5, _item(f"${r['haber']:,.2f}", _GREEN if r["haber"] else _TEXT_FAINT))
            total_debe  += r["debe"]
            total_haber += r["haber"]
            self._rows.append(dict(r))
            self._ids.append(r["id"])

        saldo = total_debe - total_haber
        color_saldo = _RED if saldo > 0 else _GREEN if saldo < 0 else _TEXT_DIM
        self.lbl_totales.setText(
            f"Debe: ${total_debe:,.2f}   Haber: ${total_haber:,.2f}   "
            f"<span style='color:{color_saldo}'>Saldo: ${saldo:,.2f}</span>"
        )

    def _buscar(self):
        desc     = self.inp_buscar.text().strip()
        cli_data = self.cmb_cliente.currentData()
        desde    = self.inp_desde.date().toString("yyyy-MM-dd")
        hasta    = self.inp_hasta.date().toString("yyyy-MM-dd")
        self._cargar(filtro_desc=desc, filtro_cli=cli_data, desde=desde, hasta=hasta)

    def _fila_actual(self) -> dict | None:
        row = self.tabla.currentRow()
        if row < 0 or row >= len(self._rows):
            QMessageBox.information(self, "Sin selección", "Seleccioná un registro.")
            return None
        return self._rows[row]

    def _nuevo(self):
        dlg = DialogCobro(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "INSERT INTO honorarios_cobrados (tipo, cliente_id, fecha, descripcion, debe, haber) "
                    "VALUES (?,?,?,?,?,?)",
                    (d["tipo"], d["cliente_id"], d["fecha"],
                     d["descripcion"], d["debe"], d["haber"])
                )
            self._buscar()

    def _editar(self):
        datos = self._fila_actual()
        if not datos:
            return
        dlg = DialogCobro(self, datos=datos)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_data()
            with conn_ctx() as conn:
                conn.execute(
                    "UPDATE honorarios_cobrados SET tipo=?, cliente_id=?, fecha=?, "
                    "descripcion=?, debe=?, haber=? WHERE id=?",
                    (d["tipo"], d["cliente_id"], d["fecha"],
                     d["descripcion"], d["debe"], d["haber"], datos["id"])
                )
            self._buscar()

    def _eliminar(self):
        datos = self._fila_actual()
        if not datos:
            return
        if QMessageBox.question(
            self, "Confirmar", "¿Eliminar este registro?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        with conn_ctx() as conn:
            conn.execute("DELETE FROM honorarios_cobrados WHERE id=?", (datos["id"],))
        self._buscar()


# ══════════════════════════════════════════════════════════════
#  TAB: RESUMEN POR CLIENTE
# ══════════════════════════════════════════════════════════════

class TabResumen(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        # Filtro año
        top = QHBoxLayout()
        top.addWidget(QLabel("Año:"))
        self.cmb_anio = QComboBox()
        anio_actual = QDate.currentDate().year()
        for a in range(anio_actual, anio_actual - 6, -1):
            self.cmb_anio.addItem(str(a))
        self.cmb_anio.currentTextChanged.connect(self._cargar)
        top.addWidget(self.cmb_anio)
        top.addStretch()

        btn_refresh = QPushButton("🔄  Actualizar")
        btn_refresh.clicked.connect(self._cargar)
        top.addWidget(btn_refresh)
        lay.addLayout(top)

        # Tabla resumen
        self.tabla = _tabla(["Cliente", "Tipo", "Honorario base", "Cobrado", "Adeudado"])
        self.tabla.setColumnWidth(1, 55)
        self.tabla.setColumnWidth(2, 130)
        self.tabla.setColumnWidth(3, 130)
        self.tabla.setColumnWidth(4, 130)
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.tabla)

        # Totales
        self.lbl_total = QLabel()
        self.lbl_total.setStyleSheet(f"color: {_ACCENT}; font-weight: bold; padding: 4px 0;")
        lay.addWidget(self.lbl_total)

        self._cargar()

    def _cargar(self):
        self.tabla.setRowCount(0)
        anio = self.cmb_anio.currentText()
        desde = f"{anio}-01-01"; hasta = f"{anio}-12-31"

        with conn_ctx() as conn:
            # Cobros agrupados por tipo+cliente_id
            cobros = conn.execute(
                """SELECT tipo, cliente_id,
                          SUM(haber) AS total_cobrado,
                          SUM(debe)  AS total_debe
                   FROM honorarios_cobrados
                   WHERE fecha BETWEEN ? AND ?
                   GROUP BY tipo, cliente_id""",
                (desde, hasta)
            ).fetchall()

            # Detalle honorarios base
            detalles = conn.execute(
                "SELECT tipo, cliente_id, honorarios FROM clientes_detalle"
            ).fetchall()
            hon_map = {(d["tipo"], d["cliente_id"]): d["honorarios"] for d in detalles}

            monos = conn.execute(
                "SELECT id, nombre FROM monotributistas WHERE condicion='Activo'"
            ).fetchall()
            resp  = conn.execute(
                "SELECT id, razon_social FROM responsables_inscriptos WHERE condicion='Activo'"
            ).fetchall()

        # Combinar: todos los clientes activos + sus cobros
        clientes: list[dict] = []
        for m in monos:
            clientes.append({"tipo": "mono", "id": m["id"], "nombre": m["nombre"]})
        for r in resp:
            clientes.append({"tipo": "resp", "id": r["id"], "nombre": r["razon_social"]})

        cobros_map = {(c["tipo"], c["cliente_id"]): c for c in cobros}

        total_cobrado = total_adeudado = 0.0

        for c in sorted(clientes, key=lambda x: x["nombre"]):
            k      = (c["tipo"], c["id"])
            cobro  = cobros_map.get(k)
            hon    = hon_map.get(k, 0.0)
            cob    = cobro["total_cobrado"] if cobro else 0.0
            adeud  = cobro["total_debe"] if cobro else 0.0

            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            prefix = "[M]" if c["tipo"] == "mono" else "[RI]"
            self.tabla.setItem(ri, 0, _item(f"{prefix} {c['nombre']}"))
            self.tabla.setItem(ri, 1, _item("Mono" if c["tipo"] == "mono" else "RI",
                                            _TEAL if c["tipo"] == "mono" else _ACCENT2))
            self.tabla.setItem(ri, 2, _item(f"${hon:,.2f}" if hon else "—", _TEXT_DIM))
            self.tabla.setItem(ri, 3, _item(f"${cob:,.2f}" if cob else "—",
                                            _GREEN if cob else _TEXT_FAINT))
            self.tabla.setItem(ri, 4, _item(f"${adeud:,.2f}" if adeud else "—",
                                            _RED if adeud else _TEXT_FAINT))
            total_cobrado  += cob
            total_adeudado += adeud

        self.lbl_total.setText(
            f"Total cobrado {anio}: ${total_cobrado:,.2f}   |   "
            f"Total adeudado: ${total_adeudado:,.2f}"
        )


# ══════════════════════════════════════════════════════════════
#  TAB: ACTUALIZACIÓN INDEC
# ══════════════════════════════════════════════════════════════

class TabActualizacion(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(16)

        # Info
        info = QLabel(
            "Actualizá los honorarios de todos o algunos clientes aplicando\n"
            "el índice IPC del INDEC (variación mensual) u otro porcentaje manual.\n\n"
            "La actualización modifica el campo 'Honorario base' en la ficha de cada cliente."
        )
        info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 13px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        # Tabla historial de actualizaciones (guardado en config)
        grp = QGroupBox("Historial de actualizaciones")
        gh  = QVBoxLayout()
        self.tabla_hist = _tabla(["Fecha", "Índice aplicado (%)", "Clientes afectados", "Notas"])
        self.tabla_hist.setMaximumHeight(180)
        gh.addWidget(self.tabla_hist)
        grp.setLayout(gh)
        lay.addWidget(grp)

        btn_abrir = _btn("🚀  Abrir asistente de actualización", _ACCENT)
        btn_abrir.setMinimumHeight(44)
        btn_abrir.clicked.connect(self._abrir_dialogo)
        lay.addWidget(btn_abrir)
        lay.addStretch()

        self._cargar_historial()

    def _cargar_historial(self):
        self.tabla_hist.setRowCount(0)
        with conn_ctx() as conn:
            rows = conn.execute(
                "SELECT fecha, porcentaje, clientes_afect, notas "
                "FROM historial_actualizaciones ORDER BY id DESC LIMIT 50"
            ).fetchall()
        for r in rows:
            ri = self.tabla_hist.rowCount()
            self.tabla_hist.insertRow(ri)
            self.tabla_hist.setItem(ri, 0, _item(r["fecha"]))
            self.tabla_hist.setItem(ri, 1, _item(f"{r['porcentaje']:.4f}%", _YELLOW))
            self.tabla_hist.setItem(ri, 2, _item(str(r["clientes_afect"])))
            self.tabla_hist.setItem(ri, 3, _item(r["notas"] or ""))

    def _abrir_dialogo(self):
        dlg = DialogActualizacion(self)
        dlg.exec()
        self._cargar_historial()


# ══════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════════

class PanelHonorarios(QWidget):
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
        lbl = QLabel("💰  Honorarios")
        lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Registro de cobros · Actualización por inflación INDEC")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        lay.addWidget(header)

        # Tabs
        tabs = QTabWidget()
        tabs.addTab(TabRegistro(),      "📒  Registro de cobros")
        tabs.addTab(TabResumen(),       "📊  Resumen por cliente")
        tabs.addTab(TabActualizacion(), "📈  Actualización INDEC")
        lay.addWidget(tabs)
