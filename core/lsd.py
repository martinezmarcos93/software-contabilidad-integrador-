"""
core/lsd.py — Funciones de base de datos para el Libro de Sueldos Digital
          Constantes y helpers de lectura/escritura, sin lógica de UI.
"""
from db.connection import get_conn

TIPO_EMP_OPTS = [
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


def init_lsd_db() -> None:
    """Inserta fila empleador vacía y parámetros por defecto si no existen."""
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO empleador_lsd (id) VALUES (1)")
        if conn.execute("SELECT COUNT(*) FROM parametros_arca").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO parametros_arca VALUES (?,?,?,?,?)",
                PARAMETROS_DEFAULT
            )
        conn.commit()


def leer_empleador() -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM empleador_lsd WHERE id=1").fetchone()
    if not row:
        return {}
    keys = ["id", "cuit", "razon_social", "tipo_empresa", "cod_actividad",
            "cod_modalidad", "cod_localidad", "ident_envio"]
    return dict(zip(keys, tuple(row)))


def leer_nomina(solo_activos: bool = True) -> list[dict]:
    q = "SELECT * FROM nomina_lsd"
    if solo_activos:
        q += " WHERE activo=1"
    q += " ORDER BY apellido_nombre"
    keys = ["id", "cuil", "apellido_nombre", "legajo", "fecha_ingreso",
            "cbu", "forma_pago", "cod_obra_social", "cod_situacion",
            "cod_condicion", "cod_siniestrado", "scvo", "cct",
            "reduccion", "activo"]
    with get_conn() as conn:
        rows = conn.execute(q).fetchall()
    return [dict(zip(keys, tuple(r))) for r in rows]


def leer_empleado_por_cuil(cuil: str) -> dict | None:
    keys = ["id", "cuil", "apellido_nombre", "legajo", "fecha_ingreso",
            "cbu", "forma_pago", "cod_obra_social", "cod_situacion",
            "cod_condicion", "cod_siniestrado", "scvo", "cct",
            "reduccion", "activo"]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM nomina_lsd WHERE cuil=?", (cuil,)
        ).fetchone()
    return dict(zip(keys, tuple(row))) if row else None


def leer_parametros() -> list[dict]:
    keys = ["cod_empleador", "descripcion", "cod_arca", "tipo", "debcred"]
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM parametros_arca ORDER BY tipo, cod_empleador"
        ).fetchall()
    return [dict(zip(keys, tuple(r))) for r in rows]


def leer_tope(periodo: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT tope FROM tope_anses WHERE periodo=?", (periodo,)
        ).fetchone()
    return float(row[0]) if row else None


def guardar_historial(cuil: str, periodo: str, nro_liq: int,
                      path_txt: str, fecha: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO historial_lsd "
            "(cuil, periodo, nro_liquidacion, path_txt, fecha_generacion) "
            "VALUES (?,?,?,?,?)",
            (cuil, periodo, nro_liq, path_txt, fecha)
        )
        conn.commit()
