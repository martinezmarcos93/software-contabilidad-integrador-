"""
ui/panels/panel_liquidador.py — Liquidador CCT 130/75 + Libro de Sueldos Digital
Nómina · Cálculo · PDF · Exportación TXT ARCA
[Fase 2]

Portado desde M7LiquidadorSueldos.py, M8LSDConfig.py y M9LSDExport.py.
Usa la DB unificada (db/connection.py) en lugar de lsd.db separado.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QFormLayout, QComboBox,
    QMessageBox, QFrame, QAbstractItemView, QGroupBox,
    QGridLayout, QScrollArea, QFileDialog, QCheckBox,
    QDialogButtonBox, QDoubleSpinBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

from db.connection import conn_ctx

# ── Paleta Catppuccin Mocha ──────────────────────────────────
_BG       = "#24273a"
_BG2      = "#1e1e2e"
_BG3      = "#313244"
_ACCENT   = "#cba6f7"
_ACCENT2  = "#89b4fa"
_GREEN    = "#a6e3a1"
_RED      = "#f38ba8"
_YELLOW   = "#f9e2af"
_TEAL     = "#94e2d5"
_TEXT     = "#cdd6f4"
_TEXT_DIM = "#a6adc8"
_TEXT_FAINT = "#585b70"
_BORDER   = "#45475a"

STYLE_BASE = f"""
    QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 13px; }}
    QLineEdit, QComboBox, QDoubleSpinBox {{
        background: {_BG2}; border: 1px solid {_BORDER};
        border-radius: 5px; padding: 5px 8px; color: {_TEXT};
    }}
    QLineEdit:focus, QComboBox:focus {{ border: 1px solid {_ACCENT}; }}
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
        alternate-background-color: {_BG3};
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
    QFrame[frameShape="4"] {{ color: {_BORDER}; }}
"""

# ── Constantes CCT 130/75 ────────────────────────────────────
CATEGORIAS_CCT = [
    "Administrativo A", "Administrativo B", "Administrativo C",
    "Cajero A", "Cajero B", "Repositor", "Maestranza", "Otro"
]
JORNADAS       = ["4", "5", "6", "7", "8"]
MESES          = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
MESES_MM       = {m: f"{i+1:02d}" for i, m in enumerate(MESES)}
TIPO_EMP_OPTS  = [
    ("1", "Decreto 814/01 Art.2 Inc.B (Comercio)"),
    ("0", "Administración Pública"),
    ("2", "Servicios Eventuales Inc.B"),
    ("4", "Decreto 814/01 Art.2 Inc.A"),
    ("5", "Servicios Eventuales Inc.A"),
    ("7", "Enseñanza Privada"),
    ("8", "Decreto 1212/03 – AFA Clubes"),
]
FORMA_PAGO_OPTS = [
    ("1", "Efectivo"),
    ("2", "Cheque"),
    ("3", "Acreditación en cuenta"),
    ("4", "Pago externo"),
]
PARAMETROS_DEFAULT = [
    ("BASICO",   "Sueldo Básico",                   "110000", "REM",  "C"),
    ("ANTIG",    "Antigüedad",                       "160001", "REM",  "C"),
    ("ASIST_R",  "Asistencia y Puntualidad (Rem.)",  "170001", "REM",  "C"),
    ("ASIST_NR", "Asistencia y Puntualidad (No R.)", "540000", "NR",   "C"),
    ("NO_REM",   "No Remunerativo (Acuerdo)",         "540000", "NR",   "C"),
    ("HEX50",    "Horas Extra 50%",                  "130001", "REM",  "C"),
    ("HEX100",   "Horas Extra 100%",                 "130002", "REM",  "C"),
    ("SAC",      "Sueldo Anual Complementario",      "120001", "REM",  "C"),
    ("JUB",      "Jubilación 11%",                   "810000", "DESC", "D"),
    ("LEY19032", "Ley 19.032 – PAMI 3%",            "810001", "DESC", "D"),
    ("OSSOCIAL", "Obra Social 3%",                   "810002", "DESC", "D"),
    ("SEC100",   "S.E.C. Art.100 CCT 130/75 2%",     "810004", "DESC", "D"),
    ("SEC101",   "S.E.C. Art.101 CCT 130/75 2%",     "810004", "DESC", "D"),
    ("SIND",     "Cuota Sindical",                   "810004", "DESC", "D"),
    ("CECLAC",   "Aporte Caja CECLAC",               "820000", "DESC", "D"),
]


# ══════════════════════════════════════════════════════════════
#  HELPERS UI
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
    t.horizontalHeader().setStretchLastSection(True)
    t.verticalHeader().setVisible(False)
    return t


def _item(text, color: str | None = None, bold: bool = False) -> QTableWidgetItem:
    it = QTableWidgetItem(str(text) if text is not None else "")
    it.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
    if color:
        it.setForeground(QColor(color))
    if bold:
        f = it.font(); f.setBold(True); it.setFont(f)
    return it


def _sep_h() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    return f


def _f(text: str, default: float = 0.0) -> float:
    try:
        return float(text.strip().replace(",", "."))
    except (ValueError, AttributeError):
        return default


# ══════════════════════════════════════════════════════════════
#  HELPERS DB (usa la DB unificada)
# ══════════════════════════════════════════════════════════════

def _init_parametros():
    """Inserta parámetros ARCA por defecto si la tabla está vacía."""
    with conn_ctx() as conn:
        if conn.execute("SELECT COUNT(*) FROM parametros_arca").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO parametros_arca VALUES (?,?,?,?,?)",
                PARAMETROS_DEFAULT
            )
        conn.execute("INSERT OR IGNORE INTO empleador_lsd (id) VALUES (1)")


def _leer_empleador() -> dict:
    with conn_ctx() as conn:
        r = conn.execute("SELECT * FROM empleador_lsd WHERE id=1").fetchone()
    return dict(r) if r else {}


def _leer_nomina(solo_activos: bool = True) -> list[dict]:
    q = "SELECT * FROM nomina_lsd"
    if solo_activos:
        q += " WHERE activo=1"
    q += " ORDER BY apellido_nombre"
    with conn_ctx() as conn:
        rows = conn.execute(q).fetchall()
    return [dict(r) for r in rows]


def _leer_parametros() -> list[dict]:
    with conn_ctx() as conn:
        rows = conn.execute(
            "SELECT * FROM parametros_arca ORDER BY tipo, cod_empleador"
        ).fetchall()
    return [dict(r) for r in rows]


def _leer_tope(periodo: str) -> float | None:
    with conn_ctx() as conn:
        r = conn.execute(
            "SELECT tope FROM tope_anses WHERE periodo=?", (periodo,)
        ).fetchone()
    return float(r["tope"]) if r else None


def _guardar_historial(cuil, periodo, nro_liq, path_txt, fecha):
    with conn_ctx() as conn:
        conn.execute(
            "INSERT INTO historial_lsd (cuil,periodo,nro_liquidacion,path_txt,fecha_generacion)"
            " VALUES (?,?,?,?,?)",
            (cuil, periodo, nro_liq, path_txt, fecha)
        )


# ══════════════════════════════════════════════════════════════
#  MOTOR TXT LSD (portado de M9LSDExport.py)
# ══════════════════════════════════════════════════════════════

def _pad_left(s, length, ch="0") -> str:
    s = "" if s is None else str(s)
    return (s[:length]).zfill(length) if ch == "0" else s[:length].rjust(length, ch)


def _pad_right(s, length, ch=" ") -> str:
    s = "" if s is None else str(s)
    return s[:length].ljust(length, ch)


def _fmt_decimal(valor_str, total_len: int) -> str:
    try:
        s = str(valor_str).strip().replace(",", ".")
        if "." in s:
            partes   = s.split(".")
            entero   = partes[0].lstrip("0") or "0"
            centavos = (partes[1] + "00")[:2]
        else:
            entero   = s.lstrip("0") or "0"
            centavos = "00"
        return _pad_left(entero + centavos, total_len, "0")
    except Exception:
        return "0" * total_len


def _is_digits(s, n) -> bool:
    return bool(s) and str(s).isdigit() and len(str(s)) == n


def make_registro_01(cuit, periodo, ident_envio, tipo_liq, nro_liq, cant_reg_04) -> str:
    if not _is_digits(cuit, 11):
        raise ValueError("CUIT empresa: debe tener 11 dígitos.")
    if not _is_digits(periodo, 6):
        raise ValueError("Período: debe tener 6 dígitos (AAAAMM).")
    if ident_envio not in ("SJ", "RE"):
        raise ValueError("Identificación de envío debe ser 'SJ' o 'RE'.")
    if ident_envio == "RE":
        tipo_f = " "; nro_f = "00000"; dias_f = "00"
    else:
        if tipo_liq not in ("M", "Q", "D", "H"):
            raise ValueError("Tipo de liquidación debe ser M, Q, D o H.")
        nro = int(nro_liq)
        tipo_f = tipo_liq
        nro_f  = _pad_left(str(nro), 5)
        dias_f = "30"
    rec = ("01" + cuit + ident_envio + periodo + tipo_f
           + nro_f + dias_f + _pad_left(str(cant_reg_04), 6))
    assert len(rec) == 35, f"Reg01 mide {len(rec)} ≠ 35"
    return rec


def make_registro_02(cuil, fecha_pago, forma_pago, legajo="", dependencia="",
                     cbu="", dias_liquidados="0", fecha_rubrica="") -> str:
    if not _is_digits(cuil, 11):
        raise ValueError(f"CUIL {cuil}: debe tener 11 dígitos.")
    if forma_pago not in ("1", "2", "3", "4"):
        raise ValueError("Forma de pago debe ser 1, 2, 3 o 4.")
    if forma_pago == "3" and len(cbu.strip()) != 22:
        raise ValueError(f"CBU debe tener 22 dígitos (CUIL {cuil}).")
    if not re.match(r"^\d{8}$", fecha_pago):
        raise ValueError(f"Fecha de pago inválida '{fecha_pago}' (yyyymmdd).")
    dias = max(0, min(999, int(dias_liquidados) if str(dias_liquidados).isdigit() else 0))
    cbu_f = _pad_left(cbu.strip(), 22) if forma_pago == "3" else _pad_right(cbu.strip(), 22)
    rub_f = fecha_rubrica.strip() if re.match(r"^\d{8}$", fecha_rubrica.strip()) else "        "
    rec = ("02" + cuil + _pad_right(legajo, 10) + _pad_right(dependencia, 50)
           + cbu_f + _pad_left(str(dias), 3) + fecha_pago + rub_f + forma_pago)
    assert len(rec) == 115, f"Reg02 mide {len(rec)} ≠ 115"
    return rec


def make_registro_03(cuil, cod_concepto, cantidad, unidad, importe, debcred,
                     periodo_ajuste="000000") -> str:
    if not _is_digits(cuil, 11):
        raise ValueError(f"CUIL {cuil}: debe tener 11 dígitos.")
    if debcred not in ("D", "C"):
        raise ValueError(f"D/C debe ser 'D' o 'C' (CUIL {cuil}).")
    unid_f = unidad if unidad in ("$", "%", "A", "Q", "M", "D", "H", " ") else " "
    per_aj = periodo_ajuste if re.match(r"^\d{6}$", str(periodo_ajuste)) else "000000"
    rec = ("03" + cuil + _pad_right(cod_concepto, 10) + _fmt_decimal(cantidad, 5)
           + unid_f + _fmt_decimal(importe, 15) + debcred + per_aj)
    assert len(rec) == 51, f"Reg03 mide {len(rec)} ≠ 51"
    return rec


def make_registro_04(d: dict) -> str:
    cuil = str(d["cuil"])
    if not _is_digits(cuil, 11):
        raise ValueError(f"CUIL {cuil}: debe tener 11 dígitos.")

    def g(k, default="0"):
        return str(d.get(k, default)).strip() or default

    def gcod(k, length, default="0"):
        val = g(k, default)
        if len(val) > length:
            raise ValueError(f"Campo '{k}': '{val}' excede {length} chars.")
        return _pad_left(val, length)

    def gi(k):
        return _fmt_decimal(g(k, "0"), 15)

    dias_t = g("dias_trabajados", "30")
    hs_t   = g("horas_trabajadas", "0")

    rec = (
        "04" + cuil
        + ("1" if g("conyuge") in ("1", "S") else "0")
        + _pad_left(g("cant_hijos", "0"), 2)
        + ("1" if g("cct") in ("1", "S") else "0")
        + ("1" if g("scvo") in ("1", "S") else "0")
        + ("1" if g("reduccion") in ("1", "S") else "0")
        + (g("tipo_empresa", "1") if g("tipo_empresa", "1") in ("0","1","2","4","5","7","8") else "1")
        + "0"
        + gcod("cod_situacion", 2, "01")
        + gcod("cod_condicion", 2, "01")
        + gcod("cod_actividad", 3, "001")
        + gcod("cod_modalidad", 3, "102")
        + gcod("cod_siniestrado", 2, "00")
        + gcod("cod_localidad", 2, "00")
        + _pad_left(g("sit_revista_1", "01"), 2)
        + _pad_left(g("dia_inicio_revista_1", "01"), 2)
        + _pad_left(g("sit_revista_2", "  "), 2, " ")
        + _pad_left(g("dia_inicio_revista_2", "  "), 2, " ")
        + _pad_left(g("sit_revista_3", "  "), 2, " ")
        + _pad_left(g("dia_inicio_revista_3", "  "), 2, " ")
        + _pad_left(dias_t, 2)
        + _pad_left(hs_t, 3)
        + _fmt_decimal(g("aporte_adicional_ss_pct", "0"), 5)
        + _fmt_decimal(g("contrib_tarea_diferencial_pct", "0"), 5)
        + _pad_left(g("cod_obra_social", "0"), 6)
        + _pad_left(g("cant_adherentes", "0"), 2)
        + gi("aporte_adicional_os")   + gi("contrib_adicional_os")
        + gi("base_dif_aporte_os_fsr") + gi("base_dif_contrib_os_fsr")
        + gi("base_dif_lrt")          + gi("rem_maternidad")
        + gi("rem_bruta")
        + gi("bi1")  + gi("bi2")  + gi("bi3")  + gi("bi4")  + gi("bi5")
        + gi("bi6")  + gi("bi7")  + gi("bi8")  + gi("bi9")
        + gi("base_dif_aporte_ss")    + gi("base_dif_contrib_ss")
        + gi("bi10") + gi("importe_detraer")
    )
    if len(rec) != 370:
        raise ValueError(f"Reg04 (CUIL {cuil}) mide {len(rec)} ≠ 370")
    return rec


def calcular_bases_imponibles(calculo: dict, tope: float | None) -> dict:
    sub_rem      = calculo.get("sub_rem", 0.0)
    asist_no_rem = calculo.get("asist_no_rem", 0.0)
    no_rem_base  = calculo.get("no_rem_total", 0.0) - asist_no_rem
    sub_nr       = calculo.get("sub_no_rem", 0.0)
    rem_bruta    = sub_rem + sub_nr
    bi1 = min(sub_rem, tope) if tope else sub_rem
    bi4 = min(sub_rem + asist_no_rem + no_rem_base, tope) if tope else (sub_rem + asist_no_rem + no_rem_base)
    bi8 = sub_rem + asist_no_rem + no_rem_base
    return {
        "rem_bruta": rem_bruta, "bi1": bi1, "bi2": sub_rem, "bi3": sub_rem,
        "bi4": bi4, "bi5": bi1, "bi6": 0.0, "bi7": 0.0, "bi8": bi8, "bi9": bi8,
        "bi10": 0.0, "base_dif_aporte_ss": 0.0, "base_dif_contrib_ss": 0.0,
        "importe_detraer": 0.0, "aporte_adicional_os": 0.0,
        "contrib_adicional_os": 0.0, "base_dif_aporte_os_fsr": 0.0,
        "base_dif_contrib_os_fsr": 0.0, "base_dif_lrt": 0.0, "rem_maternidad": 0.0,
    }


def build_txt(calculo, empleado_data, nomina, empleador, parametros,
              tope, periodo, nro_liq, fecha_pago, aguinaldo=False) -> list[str]:
    cuil       = str(empleado_data.get("cuil", "")).strip()
    dias_liq   = str(int(float(empleado_data.get("dias", 30))))
    forma_pago = nomina.get("forma_pago", "1")
    cbu        = nomina.get("cbu", "")

    reg01 = make_registro_01(
        cuit=empleador["cuit"], periodo=periodo,
        ident_envio=empleador.get("ident_envio", "SJ"),
        tipo_liq="M", nro_liq=nro_liq, cant_reg_04=1
    )
    reg02 = make_registro_02(
        cuil=cuil, fecha_pago=fecha_pago, forma_pago=forma_pago,
        legajo=nomina.get("legajo", ""), cbu=cbu,
        dias_liquidados=dias_liq if int(dias_liq) < 30 else "0",
    )

    mapa = {
        "basico_calc":  "BASICO",  "antiguedad_c": "ANTIG",
        "asist_rem":    "ASIST_R", "asist_no_rem": "ASIST_NR",
        "no_rem_base":  "NO_REM",  "hex50_c":      "HEX50",
        "hex100_c":     "HEX100",  "aguinaldo_c":  "SAC",
        "jub":          "JUB",     "ley19032":     "LEY19032",
        "ob_social":    "OSSOCIAL","sec_100":      "SEC100",
        "sec_101":      "SEC101",  "sindicato":    "SIND",
        "ceclac":       "CECLAC",
    }
    calculo_ext = dict(calculo)
    calculo_ext["no_rem_base"] = calculo.get("no_rem_total", 0.0) - calculo.get("asist_no_rem", 0.0)
    param_idx = {p["cod_empleador"]: p for p in parametros}

    regs03 = []
    for calc_key, cod_emp in mapa.items():
        valor = calculo_ext.get(calc_key, 0.0)
        if valor == 0.0:
            continue
        if calc_key == "aguinaldo_c" and not aguinaldo:
            continue
        param = param_idx.get(cod_emp)
        if not param:
            continue
        regs03.append(make_registro_03(
            cuil=cuil, cod_concepto=cod_emp, cantidad="1", unidad="$",
            importe=f"{abs(valor):.2f}", debcred=param["debcred"],
        ))

    bases = calcular_bases_imponibles(calculo, tope)
    dias_reg04 = dias_liq if int(dias_liq) < 30 else "30"
    reg04_data = {
        "cuil": cuil, "conyuge": "0", "cant_hijos": "0",
        "cct":       "1" if nomina.get("cct", 1) else "0",
        "scvo":      "1" if nomina.get("scvo", 1) else "0",
        "reduccion": "1" if nomina.get("reduccion", 0) else "0",
        "tipo_empresa":   empleador.get("tipo_empresa", "1"),
        "cod_situacion":  nomina.get("cod_situacion",  "01"),
        "cod_condicion":  nomina.get("cod_condicion",  "01"),
        "cod_actividad":  empleador.get("cod_actividad", "001"),
        "cod_modalidad":  empleador.get("cod_modalidad", "102"),
        "cod_siniestrado":nomina.get("cod_siniestrado","00"),
        "cod_localidad":  empleador.get("cod_localidad","00"),
        "sit_revista_1": "01", "dia_inicio_revista_1": "01",
        "sit_revista_2": "  ", "dia_inicio_revista_2": "  ",
        "sit_revista_3": "  ", "dia_inicio_revista_3": "  ",
        "dias_trabajados": dias_reg04, "horas_trabajadas": "0",
        "aporte_adicional_ss_pct": "0", "contrib_tarea_diferencial_pct": "0",
        "cod_obra_social": nomina.get("cod_obra_social", "000000"),
        "cant_adherentes": "0",
    }
    for k, v in bases.items():
        reg04_data[k] = f"{v:.2f}"
    reg04 = make_registro_04(reg04_data)

    return [reg01, reg02] + regs03 + [reg04]


def write_txt(path: str, lines: list[str]) -> None:
    with open(path, "wb") as f:
        f.write("\r\n".join(lines).encode("latin-1", errors="replace"))


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: EMPLEADO (alta / edición)
# ══════════════════════════════════════════════════════════════

class DialogEmpleado(QDialog):
    def __init__(self, parent=None, datos: dict | None = None):
        super().__init__(parent)
        self.setWindowTitle("Nuevo empleado" if not datos else "Editar empleado")
        self.setMinimumWidth(480)
        self.setStyleSheet(STYLE_BASE)
        self._datos = datos or {}
        self._build()
        if datos:
            self._cargar(datos)

    def _build(self):
        form = QFormLayout()
        self.inp_cuil    = QLineEdit(); self.inp_cuil.setPlaceholderText("11 dígitos, sin guiones")
        self.inp_nombre  = QLineEdit()
        self.inp_legajo  = QLineEdit()
        self.inp_ingreso = QLineEdit(); self.inp_ingreso.setPlaceholderText("dd/mm/aaaa")
        self.inp_cbu     = QLineEdit(); self.inp_cbu.setPlaceholderText("22 dígitos (si pago por acreditación)")
        self.cmb_fpago   = QComboBox()
        for val, lbl in FORMA_PAGO_OPTS:
            self.cmb_fpago.addItem(f"{val} – {lbl}", val)
        self.inp_cod_os  = QLineEdit(); self.inp_cod_os.setPlaceholderText("6 dígitos ARCA. Ej: 800803")
        self.inp_cod_sit = QLineEdit("01")
        self.inp_cod_cond= QLineEdit("01")
        self.inp_cod_sin = QLineEdit("00")
        self.chk_scvo    = QCheckBox("SCVO (Seguro Colectivo Vida Obligatorio)"); self.chk_scvo.setChecked(True)
        self.chk_cct     = QCheckBox("Trabajador en CCT"); self.chk_cct.setChecked(True)
        self.chk_red     = QCheckBox("Corresponde reducción")
        self.chk_activo  = QCheckBox("Activo en la nómina"); self.chk_activo.setChecked(True)

        form.addRow("CUIL *:", self.inp_cuil)
        form.addRow("Apellido y Nombre *:", self.inp_nombre)
        form.addRow("Legajo:", self.inp_legajo)
        form.addRow("Fecha de ingreso:", self.inp_ingreso)
        form.addRow(_sep_h(), QLabel())
        form.addRow("Forma de pago:", self.cmb_fpago)
        form.addRow("CBU:", self.inp_cbu)
        form.addRow(_sep_h(), QLabel())
        form.addRow("Cód. Obra Social:", self.inp_cod_os)
        form.addRow("Cód. Situación:", self.inp_cod_sit)
        form.addRow("Cód. Condición:", self.inp_cod_cond)
        form.addRow("Cód. Siniestrado:", self.inp_cod_sin)
        form.addRow(_sep_h(), QLabel())
        form.addRow("", self.chk_scvo)
        form.addRow("", self.chk_cct)
        form.addRow("", self.chk_red)
        form.addRow("", self.chk_activo)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._validar)
        btns.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)
        lay.setContentsMargins(20, 16, 20, 16)

    def _cargar(self, d):
        self.inp_cuil.setText(d.get("cuil", ""))
        self.inp_cuil.setReadOnly(True)
        self.inp_nombre.setText(d.get("apellido_nombre", ""))
        self.inp_legajo.setText(d.get("legajo", ""))
        self.inp_ingreso.setText(d.get("fecha_ingreso", ""))
        self.inp_cbu.setText(d.get("cbu", ""))
        self.inp_cod_os.setText(d.get("cod_obra_social", ""))
        self.inp_cod_sit.setText(d.get("cod_situacion", "01"))
        self.inp_cod_cond.setText(d.get("cod_condicion", "01"))
        self.inp_cod_sin.setText(d.get("cod_siniestrado", "00"))
        self.chk_scvo.setChecked(bool(d.get("scvo", 1)))
        self.chk_cct.setChecked(bool(d.get("cct", 1)))
        self.chk_red.setChecked(bool(d.get("reduccion", 0)))
        self.chk_activo.setChecked(bool(d.get("activo", 1)))
        fp = d.get("forma_pago", "1")
        for i in range(self.cmb_fpago.count()):
            if self.cmb_fpago.itemData(i) == fp:
                self.cmb_fpago.setCurrentIndex(i); break

    def _validar(self):
        cuil = self.inp_cuil.text().strip()
        if not cuil.isdigit() or len(cuil) != 11:
            QMessageBox.warning(self, "Error", "CUIL debe tener 11 dígitos numéricos."); return
        if not self.inp_nombre.text().strip():
            QMessageBox.warning(self, "Error", "Apellido y Nombre es obligatorio."); return
        fp = self.cmb_fpago.currentData()
        cbu = self.inp_cbu.text().strip()
        if fp == "3" and (len(cbu) != 22 or not cbu.isdigit()):
            QMessageBox.warning(self, "Error", "Con forma de pago Acreditación, el CBU debe tener 22 dígitos."); return
        self.accept()

    def get_datos(self) -> dict:
        return {
            "cuil":            self.inp_cuil.text().strip(),
            "apellido_nombre": self.inp_nombre.text().strip(),
            "legajo":          self.inp_legajo.text().strip(),
            "fecha_ingreso":   self.inp_ingreso.text().strip(),
            "cbu":             self.inp_cbu.text().strip(),
            "forma_pago":      self.cmb_fpago.currentData(),
            "cod_obra_social": self.inp_cod_os.text().strip() or "000000",
            "cod_situacion":   self.inp_cod_sit.text().strip() or "01",
            "cod_condicion":   self.inp_cod_cond.text().strip() or "01",
            "cod_siniestrado": self.inp_cod_sin.text().strip() or "00",
            "scvo":    1 if self.chk_scvo.isChecked() else 0,
            "cct":     1 if self.chk_cct.isChecked() else 0,
            "reduccion":1 if self.chk_red.isChecked() else 0,
            "activo":  1 if self.chk_activo.isChecked() else 0,
        }


# ══════════════════════════════════════════════════════════════
#  TAB: NÓMINA
# ══════════════════════════════════════════════════════════════

class TabNomina(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.setSpacing(8)

        top = QHBoxLayout()
        btn_nuevo  = _btn("＋ Nuevo empleado", _GREEN)
        btn_editar = QPushButton("✏️  Editar")
        btn_baja   = QPushButton("✕  Dar de baja")
        btn_baja.setStyleSheet(
            f"QPushButton {{ color: {_RED}; border: 1px solid {_RED}; border-radius: 5px; padding: 6px 14px; }}"
            f"QPushButton:hover {{ background: {_RED}; color: {_BG2}; }}"
        )
        self.chk_inactivos = QCheckBox("Mostrar inactivos")
        self.chk_inactivos.stateChanged.connect(lambda _: self._cargar())
        btn_nuevo.clicked.connect(self._nuevo)
        btn_editar.clicked.connect(self._editar)
        btn_baja.clicked.connect(self._dar_baja)
        top.addWidget(btn_nuevo)
        top.addWidget(btn_editar)
        top.addWidget(btn_baja)
        top.addStretch()
        top.addWidget(self.chk_inactivos)
        lay.addLayout(top)

        self.tabla = _tabla(["CUIL", "Apellido y Nombre", "Legajo", "Forma Pago",
                             "Cód. OS", "Situación", "SCVO", "Activo"])
        self.tabla.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tabla.doubleClicked.connect(self._editar)
        lay.addWidget(self.tabla)

        self._rows: list[dict] = []
        self._cargar()

    def _cargar(self):
        self.tabla.setRowCount(0)
        solo_activos = not self.chk_inactivos.isChecked()
        self._rows = _leer_nomina(solo_activos)
        fp_map = dict(FORMA_PAGO_OPTS)
        for r in self._rows:
            ri = self.tabla.rowCount()
            self.tabla.insertRow(ri)
            activo = bool(r.get("activo", 1))
            color = _TEXT if activo else _TEXT_FAINT
            vals = [
                r["cuil"], r["apellido_nombre"], r.get("legajo", ""),
                fp_map.get(r.get("forma_pago", "1"), "?"),
                r.get("cod_obra_social", ""), r.get("cod_situacion", ""),
                "✔" if r.get("scvo", 1) else "",
                "Activo" if activo else "Baja",
            ]
            for ci, v in enumerate(vals):
                it = _item(v, color)
                self.tabla.setItem(ri, ci, it)

    def _selected(self) -> dict | None:
        row = self.tabla.currentRow()
        if 0 <= row < len(self._rows):
            return self._rows[row]
        QMessageBox.information(self, "Sin selección", "Seleccioná un empleado.")
        return None

    def _nuevo(self):
        dlg = DialogEmpleado(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            d = dlg.get_datos()
            try:
                with conn_ctx() as conn:
                    conn.execute(
                        "INSERT INTO nomina_lsd (cuil,apellido_nombre,legajo,fecha_ingreso,cbu,"
                        "forma_pago,cod_obra_social,cod_situacion,cod_condicion,cod_siniestrado,"
                        "scvo,cct,reduccion,activo) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (d["cuil"], d["apellido_nombre"], d["legajo"], d["fecha_ingreso"],
                         d["cbu"], d["forma_pago"], d["cod_obra_social"], d["cod_situacion"],
                         d["cod_condicion"], d["cod_siniestrado"],
                         d["scvo"], d["cct"], d["reduccion"], d["activo"])
                    )
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(self, "Duplicado", f"Ya existe un empleado con CUIL {d['cuil']}."); return
                raise
            self._cargar()

    def _editar(self):
        d = self._selected()
        if not d:
            return
        dlg = DialogEmpleado(self, datos=d)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            nd = dlg.get_datos()
            with conn_ctx() as conn:
                conn.execute(
                    "UPDATE nomina_lsd SET apellido_nombre=?,legajo=?,fecha_ingreso=?,cbu=?,"
                    "forma_pago=?,cod_obra_social=?,cod_situacion=?,cod_condicion=?,"
                    "cod_siniestrado=?,scvo=?,cct=?,reduccion=?,activo=? WHERE cuil=?",
                    (nd["apellido_nombre"], nd["legajo"], nd["fecha_ingreso"], nd["cbu"],
                     nd["forma_pago"], nd["cod_obra_social"], nd["cod_situacion"],
                     nd["cod_condicion"], nd["cod_siniestrado"],
                     nd["scvo"], nd["cct"], nd["reduccion"], nd["activo"], nd["cuil"])
                )
            self._cargar()

    def _dar_baja(self):
        d = self._selected()
        if not d:
            return
        if QMessageBox.question(
            self, "Dar de baja",
            f"¿Marcar como inactivo a {d['apellido_nombre']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            with conn_ctx() as conn:
                conn.execute("UPDATE nomina_lsd SET activo=0 WHERE cuil=?", (d["cuil"],))
            self._cargar()


# ══════════════════════════════════════════════════════════════
#  DIÁLOGO: EXPORTAR TXT LSD
# ══════════════════════════════════════════════════════════════

class DialogExportLSD(QDialog):
    def __init__(self, calculo: dict, empleado_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar al Libro de Sueldos Digital (ARCA)")
        self.setMinimumSize(820, 680)
        self.setStyleSheet(STYLE_BASE)
        self._calculo      = calculo
        self._empleado_data = empleado_data
        self._empleador    = _leer_empleador()
        self._nomina       = _leer_nomina(solo_activos=True)
        self._parametros   = _leer_parametros()
        self._build()
        self._preselect_empleado()
        self._actualizar_preview()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner  = QWidget()
        main   = QVBoxLayout(inner)
        main.setContentsMargins(16, 16, 16, 16)
        main.setSpacing(10)

        # Advertencia si falta CUIT
        if not self._empleador.get("cuit"):
            warn = QLabel("⚠  El CUIT del empleador no está configurado en la pestaña Configuración LSD.")
            warn.setStyleSheet(f"background: {_YELLOW}33; color: {_YELLOW}; padding: 6px; border-radius: 4px;")
            warn.setWordWrap(True)
            main.addWidget(warn)

        # Selección empleado + período
        grp_sel = QGroupBox("Empleado y período")
        g = QGridLayout()

        g.addWidget(QLabel("Empleado *:"), 0, 0)
        self.cmb_empleado = QComboBox()
        cuil_m7 = str(self._empleado_data.get("cuil", "")).strip()
        for em in self._nomina:
            self.cmb_empleado.addItem(f"{em['apellido_nombre']}  ({em['cuil']})", em["cuil"])
        self.cmb_empleado.currentIndexChanged.connect(self._actualizar_preview)
        g.addWidget(self.cmb_empleado, 0, 1, 1, 3)

        g.addWidget(QLabel("Período (AAAAMM) *:"), 1, 0)
        self.inp_periodo = QLineEdit()
        mes_str  = self._empleado_data.get("mes_nombre", "")
        anio_str = self._empleado_data.get("anio", "")
        if mes_str and anio_str:
            self.inp_periodo.setText(f"{anio_str}{MESES_MM.get(mes_str, '')}")
        else:
            self.inp_periodo.setPlaceholderText("Ej: 202506")
        self.inp_periodo.textChanged.connect(self._actualizar_preview)
        g.addWidget(self.inp_periodo, 1, 1)

        g.addWidget(QLabel("Nro. liquidación *:"), 1, 2)
        self.inp_nro_liq = QLineEdit("1")
        g.addWidget(self.inp_nro_liq, 1, 3)

        g.addWidget(QLabel("Fecha de pago (yyyymmdd) *:"), 2, 0)
        self.inp_fecha_pago = QLineEdit(date.today().strftime("%Y%m%d"))
        g.addWidget(self.inp_fecha_pago, 2, 1)

        g.addWidget(QLabel("Tope ANSeS del período:"), 2, 2)
        self.lbl_tope = QLabel("— (sin configurar)")
        self.lbl_tope.setStyleSheet(f"color: {_RED}; font-style: italic;")
        g.addWidget(self.lbl_tope, 2, 3)

        grp_sel.setLayout(g)
        main.addWidget(grp_sel)

        # Preview conceptos
        grp_prev = QGroupBox("Preview — Conceptos incluidos en el TXT")
        lay_prev = QVBoxLayout()
        self.tbl_prev = _tabla(["Cód. Empleador", "Descripción", "Importe", "D/C", "Cód. ARCA"])
        self.tbl_prev.setMaximumHeight(260)
        self.lbl_totales = QLabel()
        self.lbl_totales.setStyleSheet(f"color: {_ACCENT}; font-weight: bold;")
        lay_prev.addWidget(self.tbl_prev)
        lay_prev.addWidget(self.lbl_totales)
        grp_prev.setLayout(lay_prev)
        main.addWidget(grp_prev)

        # Bases imponibles
        grp_bi = QGroupBox("Bases Imponibles calculadas automáticamente")
        g_bi   = QGridLayout()
        self.lbl_bi = {}
        bi_labels = [
            ("bi1", "BI 1 — Aportes previsionales"),
            ("bi2", "BI 2 — Contrib. prev. e INSSJyP"),
            ("bi3", "BI 3 — FNE, AAFF, RENATRE"),
            ("bi4", "BI 4 — Aportes OS y FSR"),
            ("bi5", "BI 5 — Aportes INSSJyP"),
            ("bi8", "BI 8 — Contrib. OS y FSR"),
            ("bi9", "BI 9 — LRT"),
            ("rem_bruta", "Remuneración Bruta"),
        ]
        for i, (k, lbl) in enumerate(bi_labels):
            row, col = divmod(i, 2)
            g_bi.addWidget(QLabel(f"{lbl}:"), row, col * 2)
            lbl_v = QLabel("—")
            lbl_v.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_v.setStyleSheet(f"color: {_ACCENT2}; font-weight: bold;")
            self.lbl_bi[k] = lbl_v
            g_bi.addWidget(lbl_v, row, col * 2 + 1)
        grp_bi.setLayout(g_bi)
        main.addWidget(grp_bi)

        # Botones
        main.addWidget(_sep_h())
        btn_row = QHBoxLayout()
        btn_gen = _btn("💾  Generar TXT y guardar", _ACCENT2)
        btn_gen.clicked.connect(self._generar)
        btn_cer = QPushButton("Cancelar")
        btn_cer.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(btn_cer)
        btn_row.addWidget(btn_gen)
        main.addLayout(btn_row)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _preselect_empleado(self):
        cuil = str(self._empleado_data.get("cuil", "")).strip()
        for i in range(self.cmb_empleado.count()):
            if self.cmb_empleado.itemData(i) == cuil:
                self.cmb_empleado.setCurrentIndex(i); return

    def _get_nomina_sel(self) -> dict | None:
        cuil = self.cmb_empleado.currentData()
        for em in self._nomina:
            if em["cuil"] == cuil:
                return em
        return None

    def _actualizar_preview(self):
        periodo = self.inp_periodo.text().strip()
        tope = None
        if len(periodo) == 6 and periodo.isdigit():
            tope = _leer_tope(periodo)
            if tope:
                self.lbl_tope.setText(f"${tope:,.2f}")
                self.lbl_tope.setStyleSheet(f"color: {_GREEN}; font-weight: bold;")
            else:
                self.lbl_tope.setText("Sin tope — se usa remuneración bruta")
                self.lbl_tope.setStyleSheet(f"color: {_YELLOW}; font-style: italic;")

        nomina = self._get_nomina_sel()
        if not nomina:
            return

        calculo = self._calculo
        aguinaldo = calculo.get("aguinaldo_c", 0.0) > 0
        calculo_ext = dict(calculo)
        calculo_ext["no_rem_base"] = calculo.get("no_rem_total", 0.0) - calculo.get("asist_no_rem", 0.0)

        mapa = {
            "basico_calc":  "BASICO",  "antiguedad_c": "ANTIG",
            "asist_rem":    "ASIST_R", "asist_no_rem": "ASIST_NR",
            "no_rem_base":  "NO_REM",  "hex50_c":      "HEX50",
            "hex100_c":     "HEX100",  "aguinaldo_c":  "SAC",
            "jub":          "JUB",     "ley19032":     "LEY19032",
            "ob_social":    "OSSOCIAL","sec_100":      "SEC100",
            "sec_101":      "SEC101",  "sindicato":    "SIND",
            "ceclac":       "CECLAC",
        }
        param_idx = {p["cod_empleador"]: p for p in self._parametros}
        filas = []
        total_hab = total_desc = 0.0
        for calc_key, cod_emp in mapa.items():
            valor = calculo_ext.get(calc_key, 0.0)
            if valor == 0.0:
                continue
            if calc_key == "aguinaldo_c" and not aguinaldo:
                continue
            param = param_idx.get(cod_emp)
            if not param:
                continue
            filas.append((cod_emp, param["descripcion"], valor, param["debcred"], param["cod_arca"]))
            if param["debcred"] == "C":
                total_hab += valor
            else:
                total_desc += valor

        self.tbl_prev.setRowCount(len(filas))
        for ri, (cod, desc, imp, dc, arca) in enumerate(filas):
            color_bg = _GREEN + "22" if dc == "C" else _RED + "22"
            for ci, v in enumerate([cod, desc, f"${imp:,.2f}", dc, arca]):
                it = _item(v)
                it.setBackground(QColor(color_bg))
                self.tbl_prev.setItem(ri, ci, it)

        self.lbl_totales.setText(
            f"Haberes: ${total_hab:,.2f}   |   "
            f"Descuentos: ${total_desc:,.2f}   |   "
            f"Neto estimado: ${(total_hab - total_desc):,.2f}"
        )

        bases = calcular_bases_imponibles(calculo, tope)
        for k, lbl_w in self.lbl_bi.items():
            v = bases.get(k, 0.0)
            lbl_w.setText(f"${v:,.2f}" if v else "—")

    def _generar(self):
        if not self._empleador.get("cuit"):
            QMessageBox.warning(self, "Sin configuración",
                "El CUIT del empleador no está configurado.\n"
                "Completalo en la pestaña Configuración LSD."); return
        nomina = self._get_nomina_sel()
        if not nomina:
            QMessageBox.warning(self, "Sin empleado", "No hay empleados en la nómina."); return
        periodo = self.inp_periodo.text().strip()
        if len(periodo) != 6 or not periodo.isdigit():
            QMessageBox.warning(self, "Período inválido", "Debe tener 6 dígitos (AAAAMM)."); return
        fecha_pago = self.inp_fecha_pago.text().strip()
        if not re.match(r"^\d{8}$", fecha_pago):
            QMessageBox.warning(self, "Fecha inválida", "Debe tener 8 dígitos (yyyymmdd)."); return
        try:
            nro_liq = int(self.inp_nro_liq.text().strip())
            if not (1 <= nro_liq <= 99999):
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Nro. inválido", "El número de liquidación debe ser 1-99999."); return

        tope      = _leer_tope(periodo)
        aguinaldo = self._calculo.get("aguinaldo_c", 0.0) > 0
        try:
            lines = build_txt(
                calculo       = self._calculo,
                empleado_data = {**self._empleado_data, "cuil": nomina["cuil"]},
                nomina        = nomina,
                empleador     = self._empleador,
                parametros    = self._parametros,
                tope          = tope,
                periodo       = periodo,
                nro_liq       = nro_liq,
                fecha_pago    = fecha_pago,
                aguinaldo     = aguinaldo,
            )
        except (ValueError, AssertionError) as e:
            QMessageBox.critical(self, "Error al construir TXT", str(e)); return

        default_name = f"LSD_{periodo}_SJ_{nro_liq:05d}_{nomina['cuil']}.txt"
        from config.settings import cargar as cfg_load
        cfg = cfg_load()
        default_dir = cfg.get("ruta_base", str(Path.home()))
        path, _ = QFileDialog.getSaveFileName(
            self, "Guardar TXT — Libro de Sueldos Digital",
            str(Path(default_dir) / default_name),
            "Archivo de texto (*.txt);;Todos los archivos (*.*)"
        )
        if not path:
            return
        try:
            write_txt(path, lines)
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e)); return

        _guardar_historial(nomina["cuil"], periodo, nro_liq, path,
                           datetime.now().strftime("%d/%m/%Y %H:%M"))
        cant_03 = sum(1 for l in lines if l.startswith("03"))
        QMessageBox.information(self, "TXT generado",
            f"✔  Archivo guardado:\n{path}\n\n"
            f"Registros: 01×1  02×1  03×{cant_03}  04×1  →  {len(lines)} líneas\n"
            f"Encoding: latin-1  ·  Fin de línea: CRLF")
        self.accept()


# ══════════════════════════════════════════════════════════════
#  TAB: CALCULADORA DE SUELDOS
# ══════════════════════════════════════════════════════════════

class TabCalculadora(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._ultimo_calculo: dict | None = None

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner  = QWidget()
        main   = QVBoxLayout(inner)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # ── Datos del empleador ──────────────────────────────
        grp_emp = QGroupBox("Empleador")
        g_emp   = QGridLayout()
        self.inp = {}
        g_emp.addWidget(QLabel("Razón Social / Nombre:"), 0, 0)
        self.inp["razon_social"] = QLineEdit()
        g_emp.addWidget(self.inp["razon_social"], 0, 1)
        g_emp.addWidget(QLabel("CUIT:"), 0, 2)
        self.inp["cuit_emp"] = QLineEdit()
        g_emp.addWidget(self.inp["cuit_emp"], 0, 3)
        g_emp.addWidget(QLabel("Domicilio:"), 1, 0)
        self.inp["domicilio"] = QLineEdit()
        g_emp.addWidget(self.inp["domicilio"], 1, 1, 1, 3)
        grp_emp.setLayout(g_emp)

        # ── Datos del empleado ────────────────────────────────
        grp_empl = QGroupBox("Empleado")
        g_empl   = QGridLayout()
        for (key, lbl, r, c) in [
            ("apellido_nombre", "Apellido y Nombre", 0, 0),
            ("cuil",            "CUIL",              0, 2),
            ("legajo",          "Nº Legajo",         1, 0),
            ("fecha_ingreso",   "Fecha Ingreso",     1, 2),
            ("puesto",          "Puesto",            2, 0),
        ]:
            g_empl.addWidget(QLabel(f"{lbl}:"), r, c)
            self.inp[key] = QLineEdit()
            g_empl.addWidget(self.inp[key], r, c + 1)
        g_empl.addWidget(QLabel("Categoría:"), 3, 0)
        self.cmb_cat = QComboBox()
        self.cmb_cat.addItems(CATEGORIAS_CCT)
        g_empl.addWidget(self.cmb_cat, 3, 1)
        g_empl.addWidget(QLabel("Obra Social:"), 3, 2)
        self.inp["obra_social"] = QLineEdit("O.S.E.C.A.C.")
        g_empl.addWidget(self.inp["obra_social"], 3, 3)
        grp_empl.setLayout(g_empl)

        # ── Período y valores ─────────────────────────────────
        grp_liq = QGroupBox("Período y valores de liquidación")
        g_liq   = QGridLayout()
        g_liq.addWidget(QLabel("Año:"), 0, 0)
        self.cmb_anio = QComboBox()
        self.cmb_anio.addItems([str(y) for y in range(2020, 2031)])
        self.cmb_anio.setCurrentText(str(date.today().year))
        g_liq.addWidget(self.cmb_anio, 0, 1)
        g_liq.addWidget(QLabel("Mes:"), 0, 2)
        self.cmb_mes = QComboBox()
        self.cmb_mes.addItems(MESES)
        self.cmb_mes.setCurrentIndex(date.today().month - 1)
        g_liq.addWidget(self.cmb_mes, 0, 3)
        g_liq.addWidget(QLabel("Antigüedad (años):"), 1, 0)
        self.inp["antiguedad"] = QLineEdit("0")
        g_liq.addWidget(self.inp["antiguedad"], 1, 1)
        g_liq.addWidget(QLabel("Jornada (hs/día):"), 1, 2)
        self.cmb_jornada = QComboBox()
        self.cmb_jornada.addItems(JORNADAS)
        self.cmb_jornada.setCurrentText("8")
        g_liq.addWidget(self.cmb_jornada, 1, 3)
        g_liq.addWidget(QLabel("Días trabajados:"), 2, 0)
        self.inp["dias"] = QLineEdit("30")
        g_liq.addWidget(self.inp["dias"], 2, 1)
        g_liq.addWidget(QLabel("Sueldo Básico ($):"), 2, 2)
        self.inp["basico"] = QLineEdit()
        self.inp["basico"].setPlaceholderText("Ej: 1450000")
        g_liq.addWidget(self.inp["basico"], 2, 3)
        g_liq.addWidget(QLabel("No Remunerativo ($):"), 3, 0)
        self.inp["no_rem"] = QLineEdit("0")
        g_liq.addWidget(self.inp["no_rem"], 3, 1)
        g_liq.addWidget(QLabel("% Sindicato:"), 3, 2)
        self.inp["pct_sind"] = QLineEdit("2.0")
        g_liq.addWidget(self.inp["pct_sind"], 3, 3)
        g_liq.addWidget(QLabel("Horas extra 50%:"), 4, 0)
        self.inp["hex50"] = QLineEdit("0")
        g_liq.addWidget(self.inp["hex50"], 4, 1)
        g_liq.addWidget(QLabel("Horas extra 100%:"), 4, 2)
        self.inp["hex100"] = QLineEdit("0")
        g_liq.addWidget(self.inp["hex100"], 4, 3)
        g_liq.addWidget(QLabel("Aguinaldo (SAC):"), 5, 0)
        self.cmb_agui = QComboBox()
        self.cmb_agui.addItems(["No", "Sí"])
        g_liq.addWidget(self.cmb_agui, 5, 1)
        grp_liq.setLayout(g_liq)

        # ── Resultado ─────────────────────────────────────────
        grp_res = QGroupBox("Resultado")
        g_res   = QGridLayout()
        self.lbl_res = {}
        conceptos = [
            ("basico_calc",  "Básico"),
            ("antiguedad_c", "Antigüedad"),
            ("asist_rem",    "Asistencia y Puntualidad (rem.)"),
            ("asist_no_rem", "Asistencia y Puntualidad (no rem.)"),
            ("no_rem_total", "No Remunerativo total"),
            ("hex50_c",      "Horas extra 50%"),
            ("hex100_c",     "Horas extra 100%"),
            ("aguinaldo_c",  "Aguinaldo"),
            ("sep1",         ""),
            ("sub_rem",      "Sub Total Remunerativo"),
            ("sub_no_rem",   "Sub Total No Remunerativo"),
            ("sep2",         ""),
            ("jub",          "↓ Jubilación 11%"),
            ("ley19032",     "↓ Ley 19.032  3%"),
            ("ob_social",    "↓ Obra Social  3%"),
            ("sec_100",      "↓ S.E.C. Art.100 CCT 130/75  2%"),
            ("sec_101",      "↓ S.E.C. Art.101 CCT 130/75  2%"),
            ("sindicato",    "↓ Cuota Sindical"),
            ("ceclac",       "↓ Aporte Caja CECLAC  $700"),
            ("sep3",         ""),
            ("sub_desc",     "Sub Total Descuentos"),
            ("sep4",         ""),
            ("neto",         "NETO A COBRAR"),
        ]
        for i, (key, lbl) in enumerate(conceptos):
            if key.startswith("sep"):
                sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
                g_res.addWidget(sep, i, 0, 1, 2)
                continue
            g_res.addWidget(QLabel(f"{lbl}:"), i, 0)
            val = QLabel("—")
            val.setAlignment(Qt.AlignmentFlag.AlignRight)
            if key == "neto":
                val.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {_GREEN};")
            elif key in ("sub_rem", "sub_no_rem", "sub_desc"):
                val.setStyleSheet(f"color: {_ACCENT}; font-weight: bold;")
            elif key.startswith("↓") or key in ("jub","ley19032","ob_social","sec_100","sec_101","sindicato","ceclac"):
                val.setStyleSheet(f"color: {_RED};")
            self.lbl_res[key] = val
            g_res.addWidget(val, i, 1)
        grp_res.setLayout(g_res)

        # ── Botones ───────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_calc   = _btn("⚡  Calcular", _ACCENT)
        btn_lsd    = _btn("📄  Exportar TXT LSD", _ACCENT2)
        btn_limpiar = QPushButton("🗑  Limpiar")
        btn_lsd.setEnabled(False)
        btn_calc.clicked.connect(self._calcular)
        btn_lsd.clicked.connect(self._exportar_lsd)
        btn_limpiar.clicked.connect(self._limpiar)
        self._btn_lsd = btn_lsd
        btn_row.addWidget(btn_calc)
        btn_row.addWidget(btn_lsd)
        btn_row.addStretch()
        btn_row.addWidget(btn_limpiar)

        main.addWidget(grp_emp)
        main.addWidget(grp_empl)
        main.addWidget(grp_liq)
        main.addWidget(grp_res)
        main.addLayout(btn_row)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _v(self, key) -> str:
        return self.inp[key].text().strip().replace(",", ".")

    def _calcular(self):
        basico = _f(self._v("basico"))
        if basico <= 0:
            QMessageBox.warning(self, "Error", "Ingresá el sueldo básico."); return

        dias      = _f(self._v("dias"), 30)
        antig_yr  = _f(self._v("antiguedad"), 0)
        no_rem    = _f(self._v("no_rem"), 0)
        pct_sind  = _f(self._v("pct_sind"), 2.0)
        hex50     = _f(self._v("hex50"), 0)
        hex100    = _f(self._v("hex100"), 0)
        jornada   = int(self.cmb_jornada.currentText())
        aguinaldo = self.cmb_agui.currentText() == "Sí"

        basico_prop  = basico * dias / 30
        antig_c      = basico_prop * antig_yr / 100
        asist_rem    = basico_prop * 0.0833
        asist_no_rem = no_rem * 0.0833 if no_rem > 0 else 0
        valor_hora   = basico / 30 / jornada
        hex50_c      = valor_hora * 1.50 * hex50
        hex100_c     = valor_hora * 2.00 * hex100
        agui_c       = (basico_prop + antig_c + asist_rem) / 2 if aguinaldo else 0

        sub_rem    = basico_prop + antig_c + asist_rem + hex50_c + hex100_c + agui_c
        sub_no_rem = no_rem + asist_no_rem

        jub_c    = sub_rem * 0.11
        ley19_c  = sub_rem * 0.03
        obs_c    = sub_rem * 0.03
        sec100_c = sub_rem * 0.02
        sec101_c = sub_rem * 0.02
        sind_c   = sub_rem * (pct_sind / 100)
        ceclac_c = 700.0
        sub_desc = jub_c + ley19_c + obs_c + sec100_c + sec101_c + sind_c + ceclac_c
        neto     = sub_rem + sub_no_rem - sub_desc

        self._ultimo_calculo = dict(
            basico_calc=basico_prop, antiguedad_c=antig_c,
            asist_rem=asist_rem, asist_no_rem=asist_no_rem,
            no_rem_total=sub_no_rem, hex50_c=hex50_c, hex100_c=hex100_c,
            aguinaldo_c=agui_c, sub_rem=sub_rem, sub_no_rem=sub_no_rem,
            jub=jub_c, ley19032=ley19_c, ob_social=obs_c,
            sec_100=sec100_c, sec_101=sec101_c, sindicato=sind_c,
            ceclac=ceclac_c, sub_desc=sub_desc, neto=neto
        )

        fmt = lambda v: f"${v:>14,.2f}" if v else "—"
        for key, val in self._ultimo_calculo.items():
            if key in self.lbl_res:
                self.lbl_res[key].setText(fmt(val))
        self.lbl_res["neto"].setText(f"$ {neto:,.2f}")
        self._btn_lsd.setEnabled(True)

    def _exportar_lsd(self):
        if not self._ultimo_calculo:
            return
        empleado_data = {
            "cuil":       self._v("cuil"),
            "dias":       self._v("dias"),
            "mes_nombre": self.cmb_mes.currentText(),
            "anio":       self.cmb_anio.currentText(),
        }
        dlg = DialogExportLSD(self._ultimo_calculo, empleado_data, self)
        dlg.exec()

    def _limpiar(self):
        for w in self.inp.values():
            w.clear()
        self.inp["dias"].setText("30")
        self.inp["antiguedad"].setText("0")
        self.inp["no_rem"].setText("0")
        self.inp["pct_sind"].setText("2.0")
        self.inp["hex50"].setText("0")
        self.inp["hex100"].setText("0")
        for lbl in self.lbl_res.values():
            lbl.setText("—")
        self._ultimo_calculo = None
        self._btn_lsd.setEnabled(False)


# ══════════════════════════════════════════════════════════════
#  TAB: CONFIGURACIÓN LSD
# ══════════════════════════════════════════════════════════════

class TabConfigLSD(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        tabs = QTabWidget()
        tabs.addTab(self._build_empleador(), "🏢  Empleador")
        tabs.addTab(self._build_parametros(), "🗂  Parámetros ARCA")
        tabs.addTab(self._build_tope(), "📊  Tope ANSeS")
        tabs.addTab(self._build_historial(), "🕑  Historial TXT")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(tabs)

    # ── Sub-tab: Empleador ────────────────────────────────────
    def _build_empleador(self) -> QWidget:
        w   = QWidget()
        grp = QGroupBox("Datos del empleador para el LSD")
        form = QFormLayout()
        self.emp_cuit    = QLineEdit(); self.emp_cuit.setPlaceholderText("11 dígitos sin guiones")
        self.emp_razon   = QLineEdit()
        self.emp_tipo    = QComboBox()
        for val, lbl in TIPO_EMP_OPTS:
            self.emp_tipo.addItem(f"{val} – {lbl}", val)
        self.emp_act     = QLineEdit(); self.emp_act.setPlaceholderText("3 dígitos. Ej: 001")
        self.emp_mod     = QLineEdit(); self.emp_mod.setPlaceholderText("3 dígitos. Ej: 102")
        self.emp_loc     = QLineEdit(); self.emp_loc.setPlaceholderText("2 dígitos. Ej: 00")
        self.emp_ident   = QComboBox()
        self.emp_ident.addItems(["SJ – Liquidación + DJ", "RE – Solo rectifica DJ"])
        form.addRow("CUIT empleador *:", self.emp_cuit)
        form.addRow("Razón social:", self.emp_razon)
        form.addRow("Tipo empresa *:", self.emp_tipo)
        form.addRow("Cód. Actividad *:", self.emp_act)
        form.addRow("Cód. Modalidad *:", self.emp_mod)
        form.addRow("Cód. Localidad:", self.emp_loc)
        form.addRow("Identificación envío:", self.emp_ident)
        grp.setLayout(form)
        btn = _btn("💾  Guardar", _GREEN)
        btn.clicked.connect(self._guardar_empleador)
        lay = QVBoxLayout(w)
        lay.addWidget(grp)
        lay.addWidget(btn)
        lay.addStretch()
        lay.setContentsMargins(12, 12, 12, 12)
        self._cargar_empleador()
        return w

    def _cargar_empleador(self):
        d = _leer_empleador()
        if not d:
            return
        self.emp_cuit.setText(d.get("cuit", ""))
        self.emp_razon.setText(d.get("razon_social", ""))
        self.emp_act.setText(d.get("cod_actividad", "001"))
        self.emp_mod.setText(d.get("cod_modalidad", "102"))
        self.emp_loc.setText(d.get("cod_localidad", "00"))
        te = d.get("tipo_empresa", "1")
        for i in range(self.emp_tipo.count()):
            if self.emp_tipo.itemData(i) == te:
                self.emp_tipo.setCurrentIndex(i); break
        self.emp_ident.setCurrentIndex(0 if d.get("ident_envio", "SJ") == "SJ" else 1)

    def _guardar_empleador(self):
        cuit = self.emp_cuit.text().strip()
        if not cuit.isdigit() or len(cuit) != 11:
            QMessageBox.warning(None, "Error", "CUIT debe tener 11 dígitos numéricos."); return
        ident = "SJ" if self.emp_ident.currentIndex() == 0 else "RE"
        with conn_ctx() as conn:
            conn.execute(
                "UPDATE empleador_lsd SET cuit=?,razon_social=?,tipo_empresa=?,"
                "cod_actividad=?,cod_modalidad=?,cod_localidad=?,ident_envio=? WHERE id=1",
                (cuit, self.emp_razon.text().strip(), self.emp_tipo.currentData(),
                 self.emp_act.text().strip() or "001", self.emp_mod.text().strip() or "102",
                 self.emp_loc.text().strip() or "00", ident)
            )
        QMessageBox.information(None, "Guardado", "Datos del empleador guardados.")

    # ── Sub-tab: Parámetros ARCA ──────────────────────────────
    def _build_parametros(self) -> QWidget:
        w = QWidget()
        info = QLabel(
            "Cada fila define cómo un concepto del liquidador se traduce a un código ARCA.\n"
            "Los parámetros por defecto corresponden al CCT 130/75 Empleados de Comercio."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        self.tbl_param = _tabla(["Cód. Empleador", "Descripción", "Cód. ARCA", "Tipo", "D/C"])
        self.tbl_param.doubleClicked.connect(self._editar_param)
        btn_reset = QPushButton("↺  Restablecer por defecto")
        btn_reset.setStyleSheet(f"color: {_RED};")
        btn_reset.clicked.connect(self._resetear_param)
        lay = QVBoxLayout(w)
        lay.addWidget(info)
        lay.addWidget(self.tbl_param)
        lay.addWidget(btn_reset)
        lay.setContentsMargins(8, 8, 8, 8)
        self._cargar_parametros()
        return w

    def _cargar_parametros(self):
        self.tbl_param.setRowCount(0)
        self._param_rows = _leer_parametros()
        colores = {"REM": _GREEN + "22", "NR": _YELLOW + "22", "DESC": _RED + "22"}
        for r in self._param_rows:
            ri = self.tbl_param.rowCount()
            self.tbl_param.insertRow(ri)
            color = colores.get(r["tipo"], "")
            for ci, v in enumerate([r["cod_empleador"], r["descripcion"],
                                     r["cod_arca"], r["tipo"], r["debcred"]]):
                it = _item(v)
                if color:
                    it.setBackground(QColor(color))
                self.tbl_param.setItem(ri, ci, it)

    def _editar_param(self):
        row = self.tbl_param.currentRow()
        if row < 0 or row >= len(self._param_rows):
            return
        d = self._param_rows[row]
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar: {d['cod_empleador']}")
        dlg.setStyleSheet(STYLE_BASE)
        form = QFormLayout()
        inp_desc = QLineEdit(d["descripcion"])
        inp_arca = QLineEdit(d["cod_arca"])
        cmb_tipo = QComboBox(); cmb_tipo.addItems(["REM", "NR", "DESC"])
        cmb_tipo.setCurrentText(d["tipo"])
        cmb_dc = QComboBox(); cmb_dc.addItems(["C", "D"])
        cmb_dc.setCurrentText(d["debcred"])
        form.addRow("Descripción:", inp_desc)
        form.addRow("Cód. ARCA:", inp_arca)
        form.addRow("Tipo:", cmb_tipo)
        form.addRow("Déb/Créd:", cmb_dc)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        lay2 = QVBoxLayout(dlg); lay2.addLayout(form); lay2.addWidget(btns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            with conn_ctx() as conn:
                conn.execute(
                    "UPDATE parametros_arca SET descripcion=?,cod_arca=?,tipo=?,debcred=? WHERE cod_empleador=?",
                    (inp_desc.text().strip(), inp_arca.text().strip(),
                     cmb_tipo.currentText(), cmb_dc.currentText(), d["cod_empleador"])
                )
            self._cargar_parametros()

    def _resetear_param(self):
        if QMessageBox.question(
            self, "Restablecer",
            "¿Restablecer todos los parámetros ARCA a los valores por defecto del CCT 130/75?\n"
            "Se perderán los cambios personalizados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            with conn_ctx() as conn:
                conn.execute("DELETE FROM parametros_arca")
                conn.executemany("INSERT INTO parametros_arca VALUES (?,?,?,?,?)", PARAMETROS_DEFAULT)
            self._cargar_parametros()

    # ── Sub-tab: Tope ANSeS ───────────────────────────────────
    def _build_tope(self) -> QWidget:
        w = QWidget()
        info = QLabel(
            "El tope ANSeS limita la Base Imponible 1 (aportes previsionales).\n"
            "Se actualiza con cada paritaria o resolución. Ingresalo mes a mes antes de generar los TXT.\n"
            "Si no hay tope configurado para un período, se usa la remuneración bruta sin límite."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        self.tbl_tope = _tabla(["Período (AAAAMM)", "Tope Base Imponible ($)"])
        self.tbl_tope.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        grp_nuevo = QGroupBox("Agregar / actualizar tope")
        g = QHBoxLayout()
        self.inp_periodo_tope = QLineEdit(); self.inp_periodo_tope.setPlaceholderText("AAAAMM  Ej: 202506")
        self.inp_tope_valor   = QLineEdit(); self.inp_tope_valor.setPlaceholderText("Ej: 2541000.99")
        btn_add = _btn("Guardar", _GREEN)
        btn_add.clicked.connect(self._guardar_tope)
        btn_del = QPushButton("🗑  Eliminar seleccionado")
        btn_del.setStyleSheet(f"color: {_RED};")
        btn_del.clicked.connect(self._eliminar_tope)
        g.addWidget(QLabel("Período:")); g.addWidget(self.inp_periodo_tope)
        g.addWidget(QLabel("Tope $:"));  g.addWidget(self.inp_tope_valor)
        g.addWidget(btn_add)
        grp_nuevo.setLayout(g)
        lay = QVBoxLayout(w)
        lay.addWidget(info)
        lay.addWidget(self.tbl_tope)
        lay.addWidget(grp_nuevo)
        lay.addWidget(btn_del)
        lay.setContentsMargins(8, 8, 8, 8)
        self._cargar_tope()
        return w

    def _cargar_tope(self):
        self.tbl_tope.setRowCount(0)
        with conn_ctx() as conn:
            rows = conn.execute("SELECT periodo, tope FROM tope_anses ORDER BY periodo DESC").fetchall()
        for per, tope in rows:
            ri = self.tbl_tope.rowCount()
            self.tbl_tope.insertRow(ri)
            self.tbl_tope.setItem(ri, 0, _item(per))
            self.tbl_tope.setItem(ri, 1, _item(f"${float(tope):,.2f}", _GREEN))

    def _guardar_tope(self):
        per  = self.inp_periodo_tope.text().strip()
        tope = self.inp_tope_valor.text().strip().replace(",", ".")
        if len(per) != 6 or not per.isdigit():
            QMessageBox.warning(self, "Error", "Período debe tener 6 dígitos (AAAAMM)."); return
        try:
            tope_f = float(tope)
        except ValueError:
            QMessageBox.warning(self, "Error", "El tope debe ser un número."); return
        with conn_ctx() as conn:
            conn.execute("INSERT OR REPLACE INTO tope_anses VALUES (?,?)", (per, tope_f))
        self.inp_periodo_tope.clear(); self.inp_tope_valor.clear()
        self._cargar_tope()

    def _eliminar_tope(self):
        row = self.tbl_tope.currentRow()
        if row < 0:
            return
        per = self.tbl_tope.item(row, 0).text()
        if QMessageBox.question(
            self, "Eliminar", f"¿Eliminar el tope del período {per}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            with conn_ctx() as conn:
                conn.execute("DELETE FROM tope_anses WHERE periodo=?", (per,))
            self._cargar_tope()

    # ── Sub-tab: Historial ────────────────────────────────────
    def _build_historial(self) -> QWidget:
        w = QWidget()
        self.tbl_hist = _tabla(["CUIL", "Período", "Nro. Liq.", "Archivo generado", "Fecha generación"])
        self.tbl_hist.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        btn_ref = QPushButton("🔄  Actualizar")
        btn_ref.clicked.connect(self._cargar_historial)
        lay = QVBoxLayout(w)
        lay.addWidget(self.tbl_hist)
        lay.addWidget(btn_ref)
        lay.setContentsMargins(8, 8, 8, 8)
        self._cargar_historial()
        return w

    def _cargar_historial(self):
        self.tbl_hist.setRowCount(0)
        with conn_ctx() as conn:
            rows = conn.execute(
                "SELECT cuil,periodo,nro_liquidacion,path_txt,fecha_generacion "
                "FROM historial_lsd ORDER BY id DESC LIMIT 200"
            ).fetchall()
        for r in rows:
            ri = self.tbl_hist.rowCount()
            self.tbl_hist.insertRow(ri)
            for ci, v in enumerate(r):
                self.tbl_hist.setItem(ri, ci, _item(str(v or "")))


# ══════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════════

class PanelLiquidador(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        _init_parametros()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        header.setStyleSheet(f"background: {_BG2}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 0, 16, 0)
        lbl = QLabel("📋  Liquidador de Sueldos")
        lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: bold;")
        sub = QLabel("CCT 130/75 Empleados de Comercio · Libro de Sueldos Digital")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        lay.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(TabCalculadora(), "⚡  Calculadora CCT 130/75")
        tabs.addTab(TabNomina(),      "👥  Nómina LSD")
        tabs.addTab(TabConfigLSD(),   "⚙️  Configuración LSD")
        lay.addWidget(tabs)
