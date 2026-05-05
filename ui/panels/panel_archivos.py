"""
ui/panels/panel_archivos.py — Gestión de archivos y carpetas de clientes
Imprimir carpeta · Renombrado en lote · Duplicados · Archivos huérfanos
[Fase 3]
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QListWidget,
    QFileDialog, QMessageBox, QCheckBox, QSpinBox,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QGroupBox, QRadioButton, QButtonGroup,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from db.connection import conn_ctx

# ── Paleta Catppuccin Mocha ──────────────────────────────────
_BG         = "#24273a"
_BG2        = "#1e1e2e"
_BG3        = "#313244"
_ACCENT     = "#cba6f7"
_ACCENT2    = "#89b4fa"
_GREEN      = "#a6e3a1"
_RED        = "#f38ba8"
_YELLOW     = "#f9e2af"
_TEXT       = "#cdd6f4"
_TEXT_DIM   = "#a6adc8"
_BORDER     = "#45475a"

STYLE_BASE = f"""
    QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 13px; }}
    QLineEdit, QSpinBox {{
        background: {_BG2}; border: 1px solid {_BORDER};
        border-radius: 5px; padding: 5px 8px; color: {_TEXT};
    }}
    QLineEdit:focus {{ border: 1px solid {_ACCENT}; }}
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
    QTableWidget, QListWidget {{
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
    QCheckBox, QRadioButton {{ color: {_TEXT}; spacing: 6px; }}
    QProgressBar {{
        border: 1px solid {_BORDER}; border-radius: 4px;
        background: {_BG2}; text-align: center; color: {_TEXT};
    }}
    QProgressBar::chunk {{ background: {_ACCENT}; border-radius: 3px; }}
    QLabel {{ color: {_TEXT}; }}
"""

EXTENSIONES_IMPRIMIBLES = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".xlsm",
    ".txt", ".rtf", ".odt", ".ods", ".jpg", ".jpeg",
    ".png", ".bmp", ".tif", ".tiff",
}


# ── Helpers ──────────────────────────────────────────────────

def _btn(text: str, color: str = _ACCENT) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {color}; color: {_BG2}; border-radius: 5px; "
        f"padding: 6px 14px; font-weight: bold; font-size: 12px; border: none; }}"
        f"QPushButton:hover {{ background: {color}cc; }}"
    )
    return b


def _item(text: str, color: str | None = None) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text))
    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
    if color:
        it.setForeground(QColor(color))
    return it


def _pick_folder(parent, titulo: str = "Seleccionar carpeta") -> str | None:
    path = QFileDialog.getExistingDirectory(parent, titulo)
    return path or None


# ══════════════════════════════════════════════════════════════
#  WORKER: IMPRESIÓN
# ══════════════════════════════════════════════════════════════

class WorkerImpresion(QThread):
    progreso   = pyqtSignal(int, int, str)
    finalizado = pyqtSignal()
    error_arch = pyqtSignal(str)

    def __init__(self, archivos: list[str], delay: int):
        super().__init__()
        self._archivos = archivos
        self._delay    = delay
        self._cancelar = False

    def cancelar(self):
        self._cancelar = True

    def run(self):
        total = len(self._archivos)
        for i, path in enumerate(self._archivos):
            if self._cancelar:
                break
            self.progreso.emit(i + 1, total, Path(path).name)
            try:
                os.startfile(path, "print")
            except Exception as e:
                self.error_arch.emit(f"{Path(path).name}: {e}")
            if i < total - 1 and not self._cancelar:
                time.sleep(self._delay)
        self.finalizado.emit()


# ══════════════════════════════════════════════════════════════
#  TAB 1: IMPRIMIR CARPETA
# ══════════════════════════════════════════════════════════════

class TabImpresion(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._archivos: list[str] = []
        self._worker: WorkerImpresion | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Carpeta
        grp_c = QGroupBox("Carpeta a imprimir")
        gc = QHBoxLayout()
        self.inp_carpeta = QLineEdit()
        self.inp_carpeta.setPlaceholderText("Seleccioná una carpeta...")
        self.inp_carpeta.setReadOnly(True)
        btn_examinar = QPushButton("📂  Examinar")
        btn_examinar.clicked.connect(self._examinar)
        gc.addWidget(self.inp_carpeta)
        gc.addWidget(btn_examinar)
        grp_c.setLayout(gc)
        lay.addWidget(grp_c)

        # Opciones
        grp_opts = QGroupBox("Opciones")
        go = QHBoxLayout()
        go.addWidget(QLabel("Delay entre archivos (segundos):"))
        self.spn_delay = QSpinBox()
        self.spn_delay.setRange(1, 30)
        self.spn_delay.setValue(5)
        self.spn_delay.setFixedWidth(70)
        go.addWidget(self.spn_delay)
        go.addSpacing(20)
        self.chk_subdir = QCheckBox("Incluir subcarpetas")
        go.addWidget(self.chk_subdir)
        go.addStretch()
        grp_opts.setLayout(go)
        lay.addWidget(grp_opts)

        # Lista de archivos
        grp_lista = QGroupBox("Archivos encontrados (orden de impresión)")
        gl = QVBoxLayout()
        self.lista = QListWidget()
        self.lista.setAlternatingRowColors(True)
        self.lbl_cuenta = QLabel("Sin carpeta seleccionada")
        self.lbl_cuenta.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        gl.addWidget(self.lista)
        gl.addWidget(self.lbl_cuenta)
        grp_lista.setLayout(gl)
        lay.addWidget(grp_lista)

        # Progreso
        self.barra = QProgressBar()
        self.barra.setVisible(False)
        lay.addWidget(self.barra)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
        lay.addWidget(self.lbl_estado)

        # Botones
        row_btns = QHBoxLayout()
        self.btn_imprimir = _btn("🖨️  Imprimir todo", _ACCENT)
        self.btn_imprimir.clicked.connect(self._iniciar_impresion)
        self.btn_cancelar = QPushButton("⛔  Cancelar impresión")
        self.btn_cancelar.setVisible(False)
        self.btn_cancelar.clicked.connect(self._cancelar)
        row_btns.addWidget(self.btn_imprimir)
        row_btns.addWidget(self.btn_cancelar)
        row_btns.addStretch()
        lay.addLayout(row_btns)

        self.chk_subdir.toggled.connect(self._recargar_lista)

    def _examinar(self):
        path = _pick_folder(self, "Seleccionar carpeta a imprimir")
        if path:
            self.inp_carpeta.setText(path)
            self._recargar_lista()

    def _recargar_lista(self):
        carpeta = self.inp_carpeta.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            return
        p = Path(carpeta)
        if self.chk_subdir.isChecked():
            archivos = sorted(
                f for f in p.rglob("*")
                if f.is_file() and f.suffix.lower() in EXTENSIONES_IMPRIMIBLES
            )
        else:
            archivos = sorted(
                f for f in p.iterdir()
                if f.is_file() and f.suffix.lower() in EXTENSIONES_IMPRIMIBLES
            )
        self._archivos = [str(f) for f in archivos]
        self.lista.clear()
        for f in archivos:
            label = str(f.relative_to(p)) if self.chk_subdir.isChecked() else f.name
            self.lista.addItem(label)
        n = len(self._archivos)
        self.lbl_cuenta.setText(f"{n} archivo(s) imprimible(s) encontrado(s)")

    def _iniciar_impresion(self):
        if not self._archivos:
            QMessageBox.warning(self, "Sin archivos",
                "No hay archivos imprimibles en la carpeta seleccionada.")
            return
        delay = self.spn_delay.value()
        ok = QMessageBox.question(
            self, "Confirmar impresión",
            f"Se mandarán a imprimir {len(self._archivos)} archivo(s)\n"
            f"con un delay de {delay} segundo(s) entre cada uno.\n\n¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return

        self._worker = WorkerImpresion(self._archivos, delay)
        self._worker.progreso.connect(self._on_progreso)
        self._worker.finalizado.connect(self._on_finalizado)
        self._worker.error_arch.connect(self._on_error)
        self._worker.start()

        self.barra.setMaximum(len(self._archivos))
        self.barra.setValue(0)
        self.barra.setVisible(True)
        self.btn_imprimir.setEnabled(False)
        self.btn_cancelar.setVisible(True)
        self.lbl_estado.setText("Iniciando impresión...")

    def _on_progreso(self, actual: int, total: int, nombre: str):
        self.barra.setValue(actual)
        self.lbl_estado.setText(f"Imprimiendo {actual}/{total}: {nombre}")
        if actual - 1 < self.lista.count():
            self.lista.setCurrentRow(actual - 1)

    def _on_finalizado(self):
        self.btn_imprimir.setEnabled(True)
        self.btn_cancelar.setVisible(False)
        self.barra.setVisible(False)
        self.lbl_estado.setText("✅  Impresión finalizada.")

    def _on_error(self, msg: str):
        QMessageBox.warning(self, "Error al imprimir", msg)

    def _cancelar(self):
        if self._worker:
            self._worker.cancelar()
        self.lbl_estado.setText("⛔  Impresión cancelada.")
        self.btn_cancelar.setVisible(False)
        self.btn_imprimir.setEnabled(True)
        self.barra.setVisible(False)


# ══════════════════════════════════════════════════════════════
#  TAB 2: RENOMBRADO EN LOTE
# ══════════════════════════════════════════════════════════════

class TabRenombrado(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._archivos: list[Path] = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Carpeta
        grp_c = QGroupBox("Carpeta")
        gc = QHBoxLayout()
        self.inp_carpeta = QLineEdit()
        self.inp_carpeta.setPlaceholderText("Seleccioná una carpeta...")
        self.inp_carpeta.setReadOnly(True)
        btn_examinar = QPushButton("📂  Examinar")
        btn_examinar.clicked.connect(self._examinar)
        gc.addWidget(self.inp_carpeta)
        gc.addWidget(btn_examinar)
        grp_c.setLayout(gc)
        lay.addWidget(grp_c)

        # Modo
        grp_modo = QGroupBox("Modo de renombrado")
        gm = QVBoxLayout()
        self.rb_prefijo   = QRadioButton("Prefijo + número incremental")
        self.rb_reemplaz  = QRadioButton("Buscar y reemplazar texto")
        self.rb_prefijo.setChecked(True)
        grp_btn = QButtonGroup(self)
        grp_btn.addButton(self.rb_prefijo)
        grp_btn.addButton(self.rb_reemplaz)
        gm.addWidget(self.rb_prefijo)

        # Sub-formulario prefijo
        self.frm_prefijo = QWidget()
        fp = QHBoxLayout(self.frm_prefijo)
        fp.setContentsMargins(20, 0, 0, 0)
        fp.addWidget(QLabel("Prefijo:"))
        self.inp_prefijo = QLineEdit()
        self.inp_prefijo.setPlaceholderText("Ej: DOC_")
        self.inp_prefijo.setMaximumWidth(180)
        fp.addWidget(self.inp_prefijo)
        fp.addWidget(QLabel("Inicio:"))
        self.spn_inicio = QSpinBox()
        self.spn_inicio.setRange(1, 9999)
        self.spn_inicio.setValue(1)
        self.spn_inicio.setFixedWidth(70)
        fp.addWidget(self.spn_inicio)
        fp.addWidget(QLabel("Dígitos:"))
        self.spn_digitos = QSpinBox()
        self.spn_digitos.setRange(1, 6)
        self.spn_digitos.setValue(3)
        self.spn_digitos.setFixedWidth(60)
        fp.addWidget(self.spn_digitos)
        fp.addStretch()
        gm.addWidget(self.frm_prefijo)

        # Sub-formulario buscar/reemplazar
        gm.addWidget(self.rb_reemplaz)
        self.frm_reemplaz = QWidget()
        fr = QHBoxLayout(self.frm_reemplaz)
        fr.setContentsMargins(20, 0, 0, 0)
        fr.addWidget(QLabel("Buscar:"))
        self.inp_buscar = QLineEdit()
        self.inp_buscar.setMaximumWidth(200)
        fr.addWidget(self.inp_buscar)
        fr.addWidget(QLabel("Reemplazar por:"))
        self.inp_reemplazar = QLineEdit()
        self.inp_reemplazar.setMaximumWidth(200)
        fr.addWidget(self.inp_reemplazar)
        fr.addStretch()
        gm.addWidget(self.frm_reemplaz)
        self.frm_reemplaz.setVisible(False)

        self.rb_prefijo.toggled.connect(
            lambda checked: (
                self.frm_prefijo.setVisible(checked),
                self.frm_reemplaz.setVisible(not checked),
            )
        )
        grp_modo.setLayout(gm)
        lay.addWidget(grp_modo)

        # Filtro de extensión
        row_ext = QHBoxLayout()
        row_ext.addWidget(QLabel("Filtrar por extensión (vacío = todas):"))
        self.inp_ext = QLineEdit()
        self.inp_ext.setPlaceholderText(".pdf  .docx  .jpg")
        self.inp_ext.setMaximumWidth(220)
        row_ext.addWidget(self.inp_ext)
        row_ext.addStretch()
        lay.addLayout(row_ext)

        # Preview
        btn_prev = _btn("👁  Previsualizar", _ACCENT2)
        btn_prev.clicked.connect(self._previsualizar)
        lay.addWidget(btn_prev)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Nombre actual", "Nombre nuevo"])
        self.tabla.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        lay.addWidget(self.tabla)

        btn_aplicar = _btn("✅  Renombrar", _GREEN)
        btn_aplicar.clicked.connect(self._aplicar)
        lay.addWidget(btn_aplicar)

    def _examinar(self):
        path = _pick_folder(self, "Seleccionar carpeta")
        if path:
            self.inp_carpeta.setText(path)

    def _cargar_archivos(self):
        carpeta = self.inp_carpeta.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            return
        exts_raw = self.inp_ext.text().strip().lower()
        exts = {e.strip() for e in exts_raw.split() if e.strip()} if exts_raw else None
        p = Path(carpeta)
        self._archivos = sorted(
            f for f in p.iterdir()
            if f.is_file() and (exts is None or f.suffix.lower() in exts)
        )

    def _calcular_nuevos(self) -> list[tuple[Path, str]]:
        pares: list[tuple[Path, str]] = []
        if self.rb_prefijo.isChecked():
            prefijo  = self.inp_prefijo.text()
            inicio   = self.spn_inicio.value()
            digitos  = self.spn_digitos.value()
            for i, f in enumerate(self._archivos):
                num   = str(inicio + i).zfill(digitos)
                nuevo = f"{prefijo}{num}{f.suffix}"
                pares.append((f, nuevo))
        else:
            buscar     = self.inp_buscar.text()
            reemplazar = self.inp_reemplazar.text()
            for f in self._archivos:
                nuevo = f.name.replace(buscar, reemplazar) if buscar else f.name
                pares.append((f, nuevo))
        return pares

    def _previsualizar(self):
        self._cargar_archivos()
        if not self._archivos:
            QMessageBox.information(self, "Sin archivos",
                "No se encontraron archivos con los filtros actuales.")
            return
        pares = self._calcular_nuevos()
        self.tabla.setRowCount(len(pares))
        for ri, (f, nuevo) in enumerate(pares):
            self.tabla.setItem(ri, 0, _item(f.name))
            color = _GREEN if nuevo != f.name else None
            self.tabla.setItem(ri, 1, _item(nuevo, color))

    def _aplicar(self):
        self._cargar_archivos()
        if not self._archivos:
            QMessageBox.warning(self, "Sin archivos", "Seleccioná una carpeta con archivos.")
            return
        pares   = self._calcular_nuevos()
        cambios = [(f, n) for f, n in pares if f.name != n]
        if not cambios:
            QMessageBox.information(self, "Sin cambios",
                "Ningún archivo cambiaría de nombre con la configuración actual.")
            return
        ok = QMessageBox.question(
            self, "Confirmar renombrado",
            f"¿Renombrar {len(cambios)} archivo(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        errores = []
        for f, nuevo in cambios:
            try:
                f.rename(f.parent / nuevo)
            except Exception as e:
                errores.append(f"{f.name}: {e}")
        if errores:
            QMessageBox.warning(self, "Errores al renombrar", "\n".join(errores))
        else:
            QMessageBox.information(self, "Listo",
                f"{len(cambios)} archivo(s) renombrado(s) correctamente.")
        self._previsualizar()


# ══════════════════════════════════════════════════════════════
#  WORKER: SCAN DE DUPLICADOS
# ══════════════════════════════════════════════════════════════

class WorkerDuplicados(QThread):
    finalizado = pyqtSignal(dict)
    progreso   = pyqtSignal(int, int)

    def __init__(self, carpeta: str, subdir: bool):
        super().__init__()
        self._carpeta = carpeta
        self._subdir  = subdir

    def run(self):
        p        = Path(self._carpeta)
        archivos = list(p.rglob("*") if self._subdir else p.iterdir())
        archivos = [f for f in archivos if f.is_file()]
        total    = len(archivos)
        hashes: dict[str, list[str]] = {}
        for i, f in enumerate(archivos):
            self.progreso.emit(i + 1, total)
            try:
                h = hashlib.md5(f.read_bytes()).hexdigest()
                hashes.setdefault(h, []).append(str(f))
            except Exception:
                pass
        self.finalizado.emit({h: v for h, v in hashes.items() if len(v) > 1})


# ══════════════════════════════════════════════════════════════
#  TAB 3: DUPLICADOS
# ══════════════════════════════════════════════════════════════

class TabDuplicados(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._worker: WorkerDuplicados | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        grp_c = QGroupBox("Carpeta a analizar")
        gc = QHBoxLayout()
        self.inp_carpeta = QLineEdit()
        self.inp_carpeta.setPlaceholderText("Seleccioná una carpeta...")
        self.inp_carpeta.setReadOnly(True)
        btn_examinar = QPushButton("📂  Examinar")
        btn_examinar.clicked.connect(self._examinar)
        self.chk_sub = QCheckBox("Incluir subcarpetas")
        gc.addWidget(self.inp_carpeta)
        gc.addWidget(btn_examinar)
        gc.addWidget(self.chk_sub)
        grp_c.setLayout(gc)
        lay.addWidget(grp_c)

        btn_scan = _btn("🔍  Buscar duplicados", _ACCENT)
        btn_scan.clicked.connect(self._escanear)
        lay.addWidget(btn_scan)

        self.barra = QProgressBar()
        self.barra.setVisible(False)
        lay.addWidget(self.barra)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_estado)

        self.tabla = QTableWidget(0, 3)
        self.tabla.setHorizontalHeaderLabels(["Archivo", "Carpeta", "Tamaño"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabla.setAlternatingRowColors(True)
        lay.addWidget(self.tabla)

        btn_del = _btn("🗑️  Eliminar seleccionados", _RED)
        btn_del.clicked.connect(self._eliminar_seleccionados)
        lay.addWidget(btn_del)

    def _examinar(self):
        path = _pick_folder(self, "Seleccionar carpeta")
        if path:
            self.inp_carpeta.setText(path)

    def _escanear(self):
        carpeta = self.inp_carpeta.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            QMessageBox.warning(self, "Carpeta inválida", "Seleccioná una carpeta válida.")
            return
        self.tabla.setRowCount(0)
        self.barra.setVisible(True)
        self.barra.setValue(0)
        self.lbl_estado.setText("Escaneando archivos...")
        self._worker = WorkerDuplicados(carpeta, self.chk_sub.isChecked())
        self._worker.progreso.connect(self._on_progreso)
        self._worker.finalizado.connect(self._on_finalizado)
        self._worker.start()

    def _on_progreso(self, actual: int, total: int):
        self.barra.setMaximum(total)
        self.barra.setValue(actual)
        self.lbl_estado.setText(f"Analizando {actual}/{total} archivos...")

    def _on_finalizado(self, grupos: dict):
        self.barra.setVisible(False)
        if not grupos:
            self.lbl_estado.setText("✅  No se encontraron archivos duplicados.")
            return
        total_dupl = sum(len(v) for v in grupos.values()) - len(grupos)
        self.lbl_estado.setText(
            f"⚠  {len(grupos)} grupo(s) de duplicados — {total_dupl} archivo(s) extra."
        )
        self.tabla.setRowCount(0)
        for paths in grupos.values():
            # Fila separadora de grupo
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            sep = QTableWidgetItem(f"── {len(paths)} archivos idénticos ──")
            sep.setBackground(QColor(_BG3))
            sep.setForeground(QColor(_YELLOW))
            self.tabla.setItem(ri, 0, sep)
            self.tabla.setSpan(ri, 0, 1, 3)

            for path in paths:
                p  = Path(path)
                ri = self.tabla.rowCount()
                self.tabla.insertRow(ri)
                nombre_item = _item(p.name)
                nombre_item.setData(Qt.ItemDataRole.UserRole, path)
                self.tabla.setItem(ri, 0, nombre_item)
                self.tabla.setItem(ri, 1, _item(str(p.parent)))
                size = p.stat().st_size if p.exists() else 0
                self.tabla.setItem(ri, 2, _item(f"{size / 1024:.1f} KB"))

    def _eliminar_seleccionados(self):
        filas = {idx.row() for idx in self.tabla.selectedIndexes()}
        paths = []
        for ri in filas:
            item = self.tabla.item(ri, 0)
            if item:
                path = item.data(Qt.ItemDataRole.UserRole)
                if path:
                    paths.append(path)
        if not paths:
            QMessageBox.information(self, "Sin selección",
                "Seleccioná los archivos a eliminar (no los separadores de grupo).")
            return
        ok = QMessageBox.question(
            self, "Confirmar eliminación",
            f"¿Eliminar permanentemente {len(paths)} archivo(s)?\n"
            "Esta acción no se puede deshacer.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        errores = []
        for path in paths:
            try:
                Path(path).unlink()
            except Exception as e:
                errores.append(f"{Path(path).name}: {e}")
        if errores:
            QMessageBox.warning(self, "Errores al eliminar", "\n".join(errores))
        else:
            QMessageBox.information(self, "Listo",
                f"{len(paths)} archivo(s) eliminado(s).")
        self._escanear()


# ══════════════════════════════════════════════════════════════
#  TAB 4: ARCHIVOS HUÉRFANOS
# ══════════════════════════════════════════════════════════════

class TabHuerfanos(QWidget):
    """Subcarpetas sin cliente asociado en la DB."""

    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        info = QLabel(
            "Compara las subcarpetas de una carpeta raíz contra los nombres de clientes "
            "registrados en la base de datos.\n"
            "Las subcarpetas sin coincidencia son 'huérfanas' (sin cliente asociado)."
        )
        info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 13px;")
        info.setWordWrap(True)
        lay.addWidget(info)

        grp_c = QGroupBox("Carpeta raíz de clientes")
        gc = QHBoxLayout()
        self.inp_carpeta = QLineEdit()
        self.inp_carpeta.setPlaceholderText("Carpeta donde están las carpetas de cada cliente...")
        self.inp_carpeta.setReadOnly(True)
        btn_examinar = QPushButton("📂  Examinar")
        btn_examinar.clicked.connect(self._examinar)
        gc.addWidget(self.inp_carpeta)
        gc.addWidget(btn_examinar)
        grp_c.setLayout(gc)
        lay.addWidget(grp_c)

        btn_analizar = _btn("🔍  Analizar", _ACCENT)
        btn_analizar.clicked.connect(self._analizar)
        lay.addWidget(btn_analizar)

        self.lbl_estado = QLabel("")
        self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        lay.addWidget(self.lbl_estado)

        self.tabla = QTableWidget(0, 2)
        self.tabla.setHorizontalHeaderLabels(["Subcarpeta", "Estado"])
        self.tabla.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabla.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabla.setAlternatingRowColors(True)
        lay.addWidget(self.tabla)

    def _examinar(self):
        path = _pick_folder(self, "Seleccionar carpeta raíz de clientes")
        if path:
            self.inp_carpeta.setText(path)

    def _analizar(self):
        carpeta = self.inp_carpeta.text().strip()
        if not carpeta or not Path(carpeta).is_dir():
            QMessageBox.warning(self, "Carpeta inválida", "Seleccioná una carpeta válida.")
            return

        with conn_ctx() as conn:
            monos = [r["nombre"].strip().lower() for r in
                     conn.execute(
                         "SELECT nombre FROM monotributistas WHERE condicion='Activo'"
                     ).fetchall()]
            resps = [r["razon_social"].strip().lower() for r in
                     conn.execute(
                         "SELECT razon_social FROM responsables_inscriptos WHERE condicion='Activo'"
                     ).fetchall()]
        nombres_db = set(monos + resps)

        subcarpetas = sorted(p for p in Path(carpeta).iterdir() if p.is_dir())
        self.tabla.setRowCount(0)
        huerfanos = 0

        for sub in subcarpetas:
            nombre_norm = sub.name.strip().lower()
            coincide = any(
                nombre_norm == nc or nc in nombre_norm or nombre_norm in nc
                for nc in nombres_db
            )
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            self.tabla.setItem(ri, 0, _item(sub.name))
            if coincide:
                est = QTableWidgetItem("✅  Con cliente")
                est.setForeground(QColor(_GREEN))
            else:
                est = QTableWidgetItem("⚠  Sin cliente asociado")
                est.setForeground(QColor(_RED))
                huerfanos += 1
            est.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.tabla.setItem(ri, 1, est)

        self.lbl_estado.setText(
            f"{len(subcarpetas)} subcarpeta(s) analizadas — "
            f"{huerfanos} huérfana(s) sin cliente en DB."
        )


# ══════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════════

class PanelArchivos(QWidget):
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
        lbl = QLabel("📁  Archivos")
        lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Imprimir carpeta · Renombrado en lote · Duplicados · Archivos huérfanos")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        lay.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(TabImpresion(),  "🖨️  Imprimir carpeta")
        tabs.addTab(TabRenombrado(), "✏️  Renombrado en lote")
        tabs.addTab(TabDuplicados(), "🔁  Duplicados")
        tabs.addTab(TabHuerfanos(),  "👻  Archivos huérfanos")
        lay.addWidget(tabs)
