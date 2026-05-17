"""
ui/panels/panel_asistente.py — Asistente IA con acceso a la base de datos
Chat en lenguaje natural · Ollama local · Gemini Flash · Groq
[Fase 4]
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTextBrowser,
    QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    QComboBox, QFrame, QSizePolicy, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

from db.connection import conn_ctx
from config import settings

# ── Paleta Catppuccin Mocha ──────────────────────────────────
_BG       = "#24273a"
_BG2      = "#1e1e2e"
_BG3      = "#313244"
_ACCENT   = "#cba6f7"
_ACCENT2  = "#89b4fa"
_GREEN    = "#a6e3a1"
_RED      = "#f38ba8"
_YELLOW   = "#f9e2af"
_TEXT     = "#cdd6f4"
_TEXT_DIM = "#a6adc8"
_BORDER   = "#45475a"

STYLE_BASE = f"""
    QWidget {{ background: {_BG}; color: {_TEXT}; font-size: 13px; }}
    QLineEdit, QComboBox {{
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
    QTabWidget::pane {{ border: 1px solid {_BORDER}; border-radius: 6px; }}
    QTabBar::tab {{
        background: {_BG2}; color: {_TEXT_DIM}; padding: 8px 20px;
        border: 1px solid {_BORDER}; border-bottom: none;
        border-top-left-radius: 5px; border-top-right-radius: 5px;
    }}
    QTabBar::tab:selected {{ background: {_BG3}; color: {_ACCENT}; font-weight: bold; }}
    QRadioButton {{ color: {_TEXT}; spacing: 6px; }}
    QLabel {{ color: {_TEXT}; }}
    QTextBrowser {{
        background: {_BG2}; border: 1px solid {_BORDER};
        border-radius: 6px; color: {_TEXT};
    }}
"""

# ── Proveedores cloud ────────────────────────────────────────
PROVEEDORES = {
    "Gemini Flash": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "modelo":   "gemini-2.0-flash",
    },
    "Groq": {
        "base_url": "https://api.groq.com/openai/v1/",
        "modelo":   "llama-3.3-70b-versatile",
    },
}

# ── Catálogo de modelos locales ──────────────────────────────
CATALOGO_MODELOS = [
    # (nombre,            tamaño,    descripcion)
    ("mistral:7b",       "4.1 GB",  "Recomendado · texto, SQL, conversación"),
    ("llama3.2:3b",      "2.0 GB",  "Liviano · bueno con 8 GB RAM"),
    ("llama3.1:8b",      "4.7 GB",  "Más razonamiento que mistral"),
    ("qwen2.5:7b",       "4.4 GB",  "Excelente para código y SQL"),
    ("gemma2:2b",        "1.6 GB",  "Ultra liviano · para PCs con poca RAM"),
    ("phi4:14b",         "8.9 GB",  "Muy potente · requiere 16+ GB RAM"),
    ("deepseek-r1:7b",   "4.7 GB",  "Razonamiento paso a paso"),
    ("codellama:7b",     "3.8 GB",  "Especializado en código / SQL"),
]

# ── System prompt ────────────────────────────────────────────
_SYSTEM_TPL = """Sos un asistente contable argentino para el estudio "{estudio}".
Tenés acceso a la base de datos SQLite del software. Cuando necesités consultar datos, \
incluí la query SQL así:

```sql
SELECT ...
```

El sistema la ejecuta automáticamente y te manda los resultados para que los uses en tu respuesta.

ESQUEMA DE LA BASE DE DATOS:
{schema}

REGLAS:
- Solo podés usar SELECT. Nada de INSERT, UPDATE, DELETE, DROP, PRAGMA ni similares.
- Si la pregunta requiere datos, siempre consultá la base antes de responder.
- Respondé en español rioplatense, de forma concisa y profesional.
- Si no sabés algo o el dato no está en la base, decilo claramente."""


def _schema_resumido() -> str:
    path = Path(__file__).parent.parent.parent / "db" / "schema.sql"
    if not path.exists():
        return "(schema no disponible)"
    lineas = []
    for l in path.read_text(encoding="utf-8").splitlines():
        stripped = l.strip()
        if stripped.startswith("--") or not stripped:
            continue
        lineas.append(l)
    return "\n".join(lineas)


def _fmt_error(e: Exception) -> str:
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 404:
            return (
                "Modelo no encontrado en Ollama (404).\n"
                "El modelo no está instalado. Abriendo pestaña 🗂 Modelos para instalarlo..."
            )
        if e.code == 429:
            return (
                "Límite de requests alcanzado (429 Too Many Requests).\n"
                "Esperá unos minutos antes de volver a intentar.\n"
                "Si usás el free tier de Gemini, el límite es 15 requests/minuto."
            )
        if e.code == 401:
            return (
                "API key inválida o sin autorización (401).\n"
                "Revisá la key en la pestaña Configuración IA."
            )
        if e.code == 403:
            return "Acceso denegado (403). Verificá que la API key tenga los permisos necesarios."
        return f"Error del servidor de IA ({e.code}): {e.reason}"

    if isinstance(e, urllib.error.URLError):
        reason = e.reason
        errno_ = getattr(reason, "errno", None)
        if errno_ in (10061, 111):
            return (
                "Ollama no está corriendo (conexión rechazada).\n"
                "Iniciá Ollama antes de usar el chat: ejecutá 'ollama serve' en una terminal,\n"
                "o abrí la aplicación Ollama desde el menú de inicio."
            )
        if errno_ in (11001, -2, -3):
            return "No se pudo resolver la URL del servidor. Revisá la dirección en Configuración IA."
        return f"Error de conexión: {reason}"

    return str(e)


def _btn(text: str, color: str = _ACCENT) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {color}; color: {_BG2}; border-radius: 5px; "
        f"padding: 6px 16px; font-weight: bold; font-size: 12px; border: none; }}"
        f"QPushButton:hover {{ background: {color}cc; }}"
    )
    return b


def _tabla_style() -> str:
    return (
        f"QTableWidget {{ background: {_BG2}; border: 1px solid {_BORDER}; "
        f"gridline-color: {_BORDER}; color: {_TEXT}; }}"
        f"QTableWidget::item {{ padding: 4px 8px; }}"
        f"QTableWidget::item:alternate {{ background: {_BG3}; }}"
        f"QHeaderView::section {{ background: {_BG3}; color: {_ACCENT}; "
        f"padding: 4px 8px; border: none; font-weight: bold; }}"
    )


# ══════════════════════════════════════════════════════════════
#  WORKER: LLAMADA AL LLM
# ══════════════════════════════════════════════════════════════

class WorkerChat(QThread):
    respuesta = pyqtSignal(str)
    sql_usado = pyqtSignal(str, str)
    error     = pyqtSignal(str)
    estado    = pyqtSignal(str)

    def __init__(self, mensajes: list[dict], cfg: dict):
        super().__init__()
        self._mensajes = mensajes
        self._cfg      = cfg

    def run(self):
        try:
            resp = self._llamar_con_retry(self._mensajes)
            sql  = self._extraer_sql(resp)
            if sql:
                resultado = self._ejecutar_sql(sql)
                self.sql_usado.emit(sql, resultado)
                msgs2 = self._mensajes + [
                    {"role": "assistant", "content": resp},
                    {"role": "user",      "content": f"[RESULTADO DE LA CONSULTA]\n{resultado}"},
                ]
                resp = self._llamar_con_retry(msgs2)
            self.respuesta.emit(resp)
        except Exception as e:
            self.error.emit(_fmt_error(e))

    def _llamar_con_retry(self, mensajes: list[dict]) -> str:
        for intento in range(3):
            try:
                return self._llamar(mensajes)
            except urllib.error.HTTPError as e:
                if e.code == 429 and intento < 2:
                    espera = int(e.headers.get("Retry-After", 0) or 0) or 60
                    for s in range(espera, 0, -5):
                        self.estado.emit(f"⏳  Rate limit — reintentando en {s}s...")
                        time.sleep(min(5, s))
                    continue
                raise

    def _llamar(self, mensajes: list[dict]) -> str:
        cfg  = self._cfg
        modo = cfg.get("ai_modo", "local")
        if modo == "local":
            url     = cfg.get("ai_ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
            modelo  = cfg.get("ai_modelo_local", "mistral:7b")
            payload = {"model": modelo, "messages": mensajes, "stream": False}
            data    = self._post(url, payload)
            return data["message"]["content"]
        else:
            base    = cfg.get("ai_cloud_base_url", "").rstrip("/")
            url     = f"{base}/chat/completions"
            api_key = cfg.get("ai_api_key", "")
            modelo  = cfg.get("ai_modelo_cloud", "gemini-2.0-flash")
            payload = {"model": modelo, "messages": mensajes, "max_tokens": 2048}
            data    = self._post(url, payload, {"Authorization": f"Bearer {api_key}"})
            return data["choices"][0]["message"]["content"]

    def _post(self, url: str, payload: dict, extra: dict | None = None) -> dict:
        body    = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if extra:
            headers.update(extra)
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())

    def _extraer_sql(self, texto: str) -> str | None:
        m = re.search(r"```(?:sql|SQL)\s*\n(.*?)\n```", texto, re.DOTALL)
        if not m:
            return None
        sql      = m.group(1).strip()
        primera  = sql.lstrip().split()[0].upper() if sql.split() else ""
        return sql if primera == "SELECT" else None

    def _ejecutar_sql(self, sql: str) -> str:
        try:
            with conn_ctx() as conn:
                rows = conn.execute(sql).fetchmany(50)
            if not rows:
                return "La consulta no devolvió resultados."
            return json.dumps([dict(r) for r in rows], ensure_ascii=False, default=str)
        except Exception as e:
            return f"Error al ejecutar SQL: {e}"


# ══════════════════════════════════════════════════════════════
#  ARRANQUE AUTOMÁTICO DE OLLAMA
# ══════════════════════════════════════════════════════════════

_OLLAMA_PATHS = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
    Path("C:/Program Files/Ollama/ollama.exe"),
    Path("C:/Program Files (x86)/Ollama/ollama.exe"),
]


def _encontrar_ollama() -> str | None:
    en_path = shutil.which("ollama")
    if en_path:
        return en_path
    for p in _OLLAMA_PATHS:
        if p.exists():
            return str(p)
    return None


class WorkerArranqueOllama(QThread):
    listo  = pyqtSignal()
    fallo  = pyqtSignal(str)
    estado = pyqtSignal(str)

    def __init__(self, ollama_url: str):
        super().__init__()
        self._ping_url = ollama_url.rstrip("/") + "/api/tags"

    def run(self):
        if self._ping():
            self.listo.emit()
            return
        exe = _encontrar_ollama()
        if not exe:
            self.fallo.emit(
                "Ollama no está instalado.\n"
                "Descargalo desde ollama.com e instalalo, luego reiniciá el software."
            )
            return
        self.estado.emit("Iniciando Ollama...")
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                [exe, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except Exception as e:
            self.fallo.emit(f"No se pudo iniciar Ollama: {e}")
            return
        for i in range(30):
            time.sleep(1)
            self.estado.emit(f"Esperando Ollama... {i + 1}s")
            if self._ping():
                self.listo.emit()
                return
        self.fallo.emit(
            "Ollama tardó demasiado en iniciar (>30s).\n"
            "Intentá iniciarlo manualmente con 'ollama serve'."
        )

    def _ping(self) -> bool:
        try:
            with urllib.request.urlopen(
                urllib.request.Request(self._ping_url), timeout=2
            ):
                return True
        except Exception:
            return False


# ══════════════════════════════════════════════════════════════
#  WORKER: LISTAR MODELOS INSTALADOS
# ══════════════════════════════════════════════════════════════

class WorkerListarModelos(QThread):
    resultado = pyqtSignal(list)
    error     = pyqtSignal(str)

    def __init__(self, ollama_url: str):
        super().__init__()
        self._url = ollama_url.rstrip("/") + "/api/tags"

    def run(self):
        try:
            with urllib.request.urlopen(
                urllib.request.Request(self._url), timeout=5
            ) as r:
                data = json.loads(r.read())
            self.resultado.emit(data.get("models", []))
        except Exception as e:
            self.error.emit(_fmt_error(e))


# ══════════════════════════════════════════════════════════════
#  WORKER: DESCARGAR MODELO (ollama pull)
# ══════════════════════════════════════════════════════════════

class WorkerPull(QThread):
    progreso  = pyqtSignal(str, int)  # mensaje, porcentaje (-1 = indeterminado)
    terminado = pyqtSignal()
    error     = pyqtSignal(str)

    def __init__(self, modelo: str, ollama_url: str):
        super().__init__()
        self._modelo    = modelo
        self._url       = ollama_url.rstrip("/") + "/api/pull"
        self._cancelado = False

    def cancelar(self):
        self._cancelado = True

    def run(self):
        try:
            payload = json.dumps({"name": self._modelo, "stream": True}).encode()
            req = urllib.request.Request(
                self._url, data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                for linea in resp:
                    if self._cancelado:
                        return
                    if not linea.strip():
                        continue
                    try:
                        obj = json.loads(linea)
                    except json.JSONDecodeError:
                        continue
                    status    = obj.get("status", "")
                    total     = obj.get("total", 0)
                    completed = obj.get("completed", 0)
                    if total:
                        self.progreso.emit(status, int(completed * 100 / total))
                    else:
                        self.progreso.emit(status, -1)
                    if status == "success":
                        self.terminado.emit()
                        return
            self.terminado.emit()
        except Exception as e:
            if not self._cancelado:
                self.error.emit(_fmt_error(e))


# ══════════════════════════════════════════════════════════════
#  TAB: CONFIGURACIÓN IA
# ══════════════════════════════════════════════════════════════

class TabConfigIA(QWidget):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._cfg = settings.cargar()

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(14)

        # ── Modo ──────────────────────────────────────────────
        grp_modo = QGroupBox("Modo")
        gm = QHBoxLayout()
        self.rb_local = QRadioButton("🖥️  Local (Ollama)")
        self.rb_cloud = QRadioButton("☁️  Nube (API cloud)")
        grp_rb = QButtonGroup(self)
        grp_rb.addButton(self.rb_local)
        grp_rb.addButton(self.rb_cloud)
        gm.addWidget(self.rb_local)
        gm.addWidget(self.rb_cloud)
        gm.addStretch()
        grp_modo.setLayout(gm)
        lay.addWidget(grp_modo)

        # ── Sección Local ─────────────────────────────────────
        self.grp_local = QGroupBox("Configuración Ollama")
        gl = QVBoxLayout()

        row_url = QHBoxLayout()
        row_url.addWidget(QLabel("URL de Ollama:"))
        self.inp_ollama_url = QLineEdit()
        self.inp_ollama_url.setPlaceholderText("http://localhost:11434")
        row_url.addWidget(self.inp_ollama_url)
        gl.addLayout(row_url)

        row_mod = QHBoxLayout()
        row_mod.addWidget(QLabel("Modelo activo:"))
        self.cmb_modelo_local = QComboBox()
        self.cmb_modelo_local.setEditable(True)
        self.cmb_modelo_local.setPlaceholderText("Seleccioná o escribí el modelo")
        row_mod.addWidget(self.cmb_modelo_local)
        gl.addLayout(row_mod)

        info_local = QLabel(
            "Instalá y cambiá modelos desde la pestaña 🗂 Modelos.\n"
            "Ollama debe estar corriendo. Instalación: https://ollama.com"
        )
        info_local.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        info_local.setWordWrap(True)
        gl.addWidget(info_local)
        self.grp_local.setLayout(gl)
        lay.addWidget(self.grp_local)

        # ── Sección Cloud ─────────────────────────────────────
        self.grp_cloud = QGroupBox("Configuración API Cloud")
        gc = QVBoxLayout()

        row_prov = QHBoxLayout()
        row_prov.addWidget(QLabel("Proveedor:"))
        self.cmb_proveedor = QComboBox()
        for p in PROVEEDORES:
            self.cmb_proveedor.addItem(p)
        self.cmb_proveedor.currentTextChanged.connect(self._on_proveedor_cambio)
        row_prov.addWidget(self.cmb_proveedor)
        row_prov.addStretch()
        gc.addLayout(row_prov)

        row_key = QHBoxLayout()
        row_key.addWidget(QLabel("API Key:"))
        self.inp_api_key = QLineEdit()
        self.inp_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.inp_api_key.setPlaceholderText("Pegá tu API key acá")
        btn_toggle = QPushButton("👁")
        btn_toggle.setFixedWidth(36)
        btn_toggle.setCheckable(True)
        btn_toggle.toggled.connect(
            lambda v: self.inp_api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if v else QLineEdit.EchoMode.Password
            )
        )
        row_key.addWidget(self.inp_api_key)
        row_key.addWidget(btn_toggle)
        gc.addLayout(row_key)

        row_mod_c = QHBoxLayout()
        row_mod_c.addWidget(QLabel("Modelo:"))
        self.inp_modelo_cloud = QLineEdit()
        row_mod_c.addWidget(self.inp_modelo_cloud)
        gc.addLayout(row_mod_c)

        info_cloud = QLabel(
            "La API key se guarda localmente en data/config.json (nunca se sube al repositorio)."
        )
        info_cloud.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        info_cloud.setWordWrap(True)
        gc.addWidget(info_cloud)
        self.grp_cloud.setLayout(gc)
        lay.addWidget(self.grp_cloud)

        # ── Botones ───────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {_BORDER};")
        lay.addWidget(sep)

        row_btns = QHBoxLayout()
        self._btn_test = _btn("🔌  Probar conexión", _ACCENT2)
        self._btn_test.clicked.connect(self._probar)
        btn_guardar = _btn("💾  Guardar", _GREEN)
        btn_guardar.clicked.connect(self._guardar)
        self.lbl_test = QLabel("")
        self.lbl_test.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        row_btns.addWidget(self._btn_test)
        row_btns.addWidget(btn_guardar)
        row_btns.addSpacing(12)
        row_btns.addWidget(self.lbl_test)
        row_btns.addStretch()
        lay.addLayout(row_btns)
        lay.addStretch()

        self._cargar_valores()
        self.rb_local.toggled.connect(self._toggle_seccion)
        self._toggle_seccion(self.rb_local.isChecked())

    # ── Helpers ───────────────────────────────────────────────

    def _cargar_valores(self):
        cfg = self._cfg
        if cfg.get("ai_modo", "local") == "cloud":
            self.rb_cloud.setChecked(True)
        else:
            self.rb_local.setChecked(True)
        self.inp_ollama_url.setText(cfg.get("ai_ollama_url", "http://localhost:11434"))
        self.cmb_modelo_local.setCurrentText(cfg.get("ai_modelo_local", "mistral:7b"))
        prov = cfg.get("ai_proveedor", "Gemini Flash")
        idx  = self.cmb_proveedor.findText(prov)
        if idx >= 0:
            self.cmb_proveedor.setCurrentIndex(idx)
        self.inp_api_key.setText(cfg.get("ai_api_key", ""))
        self.inp_modelo_cloud.setText(cfg.get("ai_modelo_cloud", "gemini-2.0-flash"))

    def _toggle_seccion(self, local: bool):
        self.grp_local.setVisible(local)
        self.grp_cloud.setVisible(not local)

    def _on_proveedor_cambio(self, nombre: str):
        p = PROVEEDORES.get(nombre, {})
        self.inp_modelo_cloud.setText(p.get("modelo", ""))

    def _guardar(self):
        cfg = settings.cargar()
        cfg["ai_modo"]         = "local" if self.rb_local.isChecked() else "cloud"
        cfg["ai_ollama_url"]   = self.inp_ollama_url.text().strip() or "http://localhost:11434"
        cfg["ai_modelo_local"] = self.cmb_modelo_local.currentText().strip() or "mistral:7b"
        prov = self.cmb_proveedor.currentText()
        cfg["ai_proveedor"]      = prov
        cfg["ai_cloud_base_url"] = PROVEEDORES.get(prov, {}).get("base_url", "")
        cfg["ai_api_key"]        = self.inp_api_key.text().strip()
        cfg["ai_modelo_cloud"]   = self.inp_modelo_cloud.text().strip()
        settings.guardar(cfg)
        self._cfg = cfg
        self.lbl_test.setText("✅  Guardado.")

    def _probar(self):
        cfg  = self._get_config_actual()
        modo = cfg.get("ai_modo", "local")
        if modo == "local":
            self.lbl_test.setText("Iniciando Ollama...")
            self._btn_test.setEnabled(False)
            url    = cfg.get("ai_ollama_url", "http://localhost:11434")
            worker = WorkerArranqueOllama(url)
            worker.estado.connect(self.lbl_test.setText)
            worker.listo.connect(self._on_ollama_listo)
            worker.fallo.connect(self._on_ollama_fallo)
            worker.start()
            self._arranque_worker = worker
        else:
            self.lbl_test.setText("Probando conexión cloud...")
            worker = _WorkerTest(cfg)
            worker.resultado.connect(lambda ok, msg: self.lbl_test.setText(
                f"✅  {msg}" if ok else f"❌  {msg}"
            ))
            worker.start()
            self._test_worker = worker

    def _on_ollama_listo(self):
        cfg = self._get_config_actual()
        url = cfg.get("ai_ollama_url", "http://localhost:11434")
        self.lbl_test.setText("Ollama activo — cargando modelos...")
        worker = WorkerListarModelos(url)
        worker.resultado.connect(self._on_modelos_listados)
        worker.error.connect(lambda e: (
            self.lbl_test.setText(f"❌  {e}"),
            self._btn_test.setEnabled(True),
        ))
        worker.start()
        self._listar_worker = worker

    def _on_ollama_fallo(self, msg: str):
        self.lbl_test.setText(f"❌  {msg}")
        self._btn_test.setEnabled(True)

    def _on_modelos_listados(self, modelos: list):
        nombres = [m["name"] if isinstance(m, dict) else m for m in modelos]
        self.actualizar_modelos(nombres)
        n = len(nombres)
        self.lbl_test.setText(f"✅  Ollama OK — {n} modelo(s) disponible(s)")
        self._btn_test.setEnabled(True)

    def _get_config_actual(self) -> dict:
        cfg = settings.cargar()
        cfg["ai_modo"]         = "local" if self.rb_local.isChecked() else "cloud"
        cfg["ai_ollama_url"]   = self.inp_ollama_url.text().strip() or "http://localhost:11434"
        cfg["ai_modelo_local"] = self.cmb_modelo_local.currentText().strip() or "mistral:7b"
        prov = self.cmb_proveedor.currentText()
        cfg["ai_proveedor"]      = prov
        cfg["ai_cloud_base_url"] = PROVEEDORES.get(prov, {}).get("base_url", "")
        cfg["ai_api_key"]        = self.inp_api_key.text().strip()
        cfg["ai_modelo_cloud"]   = self.inp_modelo_cloud.text().strip()
        return cfg

    def get_config(self) -> dict:
        return self._get_config_actual()

    def actualizar_modelos(self, modelos: list[str]):
        """Llamado por TabModelos cuando refresca la lista de instalados."""
        actual = self.cmb_modelo_local.currentText()
        self.cmb_modelo_local.clear()
        for m in modelos:
            self.cmb_modelo_local.addItem(m)
        if actual:
            idx = self.cmb_modelo_local.findText(actual)
            if idx >= 0:
                self.cmb_modelo_local.setCurrentIndex(idx)
            else:
                self.cmb_modelo_local.setCurrentText(actual)

    def set_modelo_local(self, modelo: str):
        """Llamado por TabModelos cuando el usuario elige 'Usar'."""
        idx = self.cmb_modelo_local.findText(modelo)
        if idx >= 0:
            self.cmb_modelo_local.setCurrentIndex(idx)
        else:
            self.cmb_modelo_local.setCurrentText(modelo)
        cfg = settings.cargar()
        cfg["ai_modelo_local"] = modelo
        settings.guardar(cfg)
        self._cfg = cfg


class _WorkerTest(QThread):
    resultado = pyqtSignal(bool, str)

    def __init__(self, cfg: dict):
        super().__init__()
        self._cfg = cfg

    def run(self):
        cfg  = self._cfg
        modo = cfg.get("ai_modo", "local")
        try:
            if modo == "local":
                url = cfg.get("ai_ollama_url", "http://localhost:11434").rstrip("/") + "/api/tags"
                with urllib.request.urlopen(
                    urllib.request.Request(url), timeout=5
                ) as r:
                    data   = json.loads(r.read())
                    models = [m["name"] for m in data.get("models", [])]
                    txt    = f"Ollama OK — {len(models)} modelo(s): {', '.join(models[:3])}"
                    self.resultado.emit(True, txt)
            else:
                base = cfg.get("ai_cloud_base_url", "").rstrip("/")
                key  = cfg.get("ai_api_key", "")
                if not key:
                    self.resultado.emit(False, "API Key vacía.")
                    return
                url = f"{base}/models"
                req = urllib.request.Request(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    data = json.loads(r.read())
                n = len(data.get("data", []))
                prov = cfg.get("ai_proveedor", "")
                self.resultado.emit(True, f"Conexión OK con {prov} — {n} modelos disponibles")
        except Exception as e:
            self.resultado.emit(False, _fmt_error(e))


# ══════════════════════════════════════════════════════════════
#  TAB: GESTIÓN DE MODELOS
# ══════════════════════════════════════════════════════════════

class TabModelos(QWidget):
    modelo_activo_cambiado = pyqtSignal(str)

    def __init__(self, config_tab: TabConfigIA):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._config_tab     = config_tab
        self._worker_listar: WorkerListarModelos | None = None
        self._worker_pull:   WorkerPull | None          = None
        self._instalados:    list[str]                  = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        # ── Barra superior ─────────────────────────────────────
        row_top = QHBoxLayout()
        self.lbl_url = QLabel("")
        self.lbl_url.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        btn_ref = _btn("🔄  Actualizar", _ACCENT2)
        btn_ref.clicked.connect(self._refrescar)
        row_top.addWidget(self.lbl_url)
        row_top.addStretch()
        row_top.addWidget(btn_ref)
        lay.addLayout(row_top)

        # ── Paneles lado a lado ─────────────────────────────────
        row_paneles = QHBoxLayout()
        row_paneles.setSpacing(12)

        # Instalados
        grp_inst = QGroupBox("Modelos instalados")
        gl = QVBoxLayout()
        self.tbl_inst = QTableWidget(0, 3)
        self.tbl_inst.setHorizontalHeaderLabels(["Modelo", "Tamaño", ""])
        self.tbl_inst.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbl_inst.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_inst.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_inst.verticalHeader().setVisible(False)
        self.tbl_inst.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_inst.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_inst.setAlternatingRowColors(True)
        self.tbl_inst.setStyleSheet(_tabla_style())
        gl.addWidget(self.tbl_inst)
        grp_inst.setLayout(gl)
        row_paneles.addWidget(grp_inst, 1)

        # Catálogo
        grp_cat = QGroupBox("Disponibles para instalar")
        gc = QVBoxLayout()
        self.tbl_cat = QTableWidget(len(CATALOGO_MODELOS), 4)
        self.tbl_cat.setHorizontalHeaderLabels(["Modelo", "Tamaño", "Descripción", ""])
        self.tbl_cat.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cat.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cat.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tbl_cat.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_cat.verticalHeader().setVisible(False)
        self.tbl_cat.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_cat.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_cat.setAlternatingRowColors(True)
        self.tbl_cat.setStyleSheet(_tabla_style())
        for i, (nombre, tamano, desc) in enumerate(CATALOGO_MODELOS):
            self.tbl_cat.setItem(i, 0, QTableWidgetItem(nombre))
            self.tbl_cat.setItem(i, 1, QTableWidgetItem(tamano))
            self.tbl_cat.setItem(i, 2, QTableWidgetItem(desc))
            btn_i = _btn("⬇ Instalar", _ACCENT2)
            btn_i.clicked.connect(lambda _, n=nombre: self._instalar(n))
            self.tbl_cat.setCellWidget(i, 3, btn_i)
        self.tbl_cat.resizeRowsToContents()
        gc.addWidget(self.tbl_cat)
        grp_cat.setLayout(gc)
        row_paneles.addWidget(grp_cat, 1)

        lay.addLayout(row_paneles, 1)

        # ── Barra de progreso de descarga ───────────────────────
        self.frm_prog = QFrame()
        self.frm_prog.setStyleSheet(
            f"background: {_BG2}; border: 1px solid {_BORDER}; border-radius: 6px;"
        )
        fp = QHBoxLayout(self.frm_prog)
        fp.setContentsMargins(12, 6, 12, 6)
        self.lbl_prog_nombre = QLabel("")
        self.lbl_prog_nombre.setStyleSheet(f"color: {_ACCENT}; font-weight: bold;")
        self.lbl_prog_status = QLabel("")
        self.lbl_prog_status.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 100)
        self.pbar.setFixedWidth(220)
        self.pbar.setStyleSheet(
            f"QProgressBar {{ background: {_BG3}; border: 1px solid {_BORDER}; "
            f"border-radius: 4px; height: 14px; text-align: center; }}"
            f"QProgressBar::chunk {{ background: {_ACCENT}; border-radius: 4px; }}"
        )
        btn_cancel = _btn("✖ Cancelar", _RED)
        btn_cancel.clicked.connect(self._cancelar)
        fp.addWidget(self.lbl_prog_nombre)
        fp.addSpacing(8)
        fp.addWidget(self.lbl_prog_status)
        fp.addStretch()
        fp.addWidget(self.pbar)
        fp.addSpacing(8)
        fp.addWidget(btn_cancel)
        self.frm_prog.setVisible(False)
        lay.addWidget(self.frm_prog)

        self._refrescar()

    # ── Refrescar lista ────────────────────────────────────────

    def _refrescar(self):
        cfg = self._config_tab.get_config()
        url = cfg.get("ai_ollama_url", "http://localhost:11434")
        self.lbl_url.setText(f"Ollama: {url}")
        self._worker_listar = WorkerListarModelos(url)
        self._worker_listar.resultado.connect(self._on_modelos)
        self._worker_listar.error.connect(self._on_error_listar)
        self._worker_listar.start()

    def _on_modelos(self, modelos: list):
        self._instalados   = [m["name"] for m in modelos]
        cfg_modelo         = self._config_tab.get_config().get("ai_modelo_local", "")

        self.tbl_inst.setRowCount(0)
        for m in modelos:
            nombre = m["name"]
            size_b = m.get("size", 0)
            size_s = f"{size_b / 1e9:.1f} GB" if size_b else "—"
            ri     = self.tbl_inst.rowCount()
            self.tbl_inst.insertRow(ri)

            item_n = QTableWidgetItem(nombre)
            if nombre == cfg_modelo:
                item_n.setForeground(QColor(_GREEN))
            self.tbl_inst.setItem(ri, 0, item_n)
            self.tbl_inst.setItem(ri, 1, QTableWidgetItem(size_s))

            es_activo = nombre == cfg_modelo
            btn_usar  = _btn("✔ Activo" if es_activo else "Usar",
                             _GREEN if es_activo else _ACCENT)
            btn_usar.clicked.connect(lambda _, n=nombre: self._usar(n))
            self.tbl_inst.setCellWidget(ri, 2, btn_usar)

        self._actualizar_catalogo()
        self._config_tab.actualizar_modelos(self._instalados)

    def _on_error_listar(self, msg: str):
        self.tbl_inst.setRowCount(1)
        item = QTableWidgetItem(f"⚠ {msg}")
        item.setForeground(QColor(_RED))
        self.tbl_inst.setItem(0, 0, item)

    def _actualizar_catalogo(self):
        for i in range(self.tbl_cat.rowCount()):
            nombre = self.tbl_cat.item(i, 0).text()
            btn    = self.tbl_cat.cellWidget(i, 3)
            if nombre in self._instalados:
                btn.setText("✔ Instalado")
                btn.setEnabled(False)
            else:
                btn.setText("⬇ Instalar")
                btn.setEnabled(True)

    # ── Instalar ───────────────────────────────────────────────

    def iniciar_instalacion(self, modelo: str):
        """Llamable desde TabChat para auto-instalar en caso de 404."""
        self._instalar(modelo)

    def _instalar(self, modelo: str):
        if self._worker_pull and self._worker_pull.isRunning():
            QMessageBox.warning(self, "Descarga en curso",
                                "Ya hay un modelo descargándose. Esperá a que termine.")
            return
        cfg = self._config_tab.get_config()
        url = cfg.get("ai_ollama_url", "http://localhost:11434")
        self.lbl_prog_nombre.setText(f"Descargando: {modelo}")
        self.lbl_prog_status.setText("Iniciando...")
        self.pbar.setRange(0, 100)
        self.pbar.setValue(0)
        self.frm_prog.setVisible(True)
        self._worker_pull = WorkerPull(modelo, url)
        self._worker_pull.progreso.connect(self._on_progreso)
        self._worker_pull.terminado.connect(lambda: self._on_terminado(modelo))
        self._worker_pull.error.connect(self._on_error_pull)
        self._worker_pull.start()

    def _on_progreso(self, msg: str, pct: int):
        self.lbl_prog_status.setText(msg)
        if pct >= 0:
            self.pbar.setRange(0, 100)
            self.pbar.setValue(pct)
        else:
            self.pbar.setRange(0, 0)   # animación indeterminada

    def _on_terminado(self, modelo: str):
        self.frm_prog.setVisible(False)
        self._refrescar()
        QMessageBox.information(
            self, "Instalación completa",
            f"'{modelo}' instalado correctamente.\n"
            "Usá el botón 'Usar' para activarlo."
        )

    def _on_error_pull(self, msg: str):
        self.frm_prog.setVisible(False)
        QMessageBox.critical(self, "Error de descarga", msg)

    def _cancelar(self):
        if self._worker_pull:
            self._worker_pull.cancelar()
        self.frm_prog.setVisible(False)

    # ── Activar modelo ─────────────────────────────────────────

    def _usar(self, modelo: str):
        self._config_tab.set_modelo_local(modelo)
        self.modelo_activo_cambiado.emit(modelo)
        self._refrescar()


# ══════════════════════════════════════════════════════════════
#  TAB: CHAT
# ══════════════════════════════════════════════════════════════

_HTML_USER = (
    '<div style="margin:6px 0; text-align:right;">'
    '<span style="background:#45475a; color:#cdd6f4; border-radius:10px; '
    'padding:6px 12px; display:inline-block; max-width:75%;">'
    '{texto}</span></div>'
)
_HTML_ASIST = (
    '<div style="margin:6px 0;">'
    '<span style="background:#313244; color:#cdd6f4; border-radius:10px; '
    'padding:6px 12px; display:inline-block; max-width:85%; white-space:pre-wrap;">'
    '<b style="color:#cba6f7;">IA</b><br>{texto}</span></div>'
)
_HTML_SQL = (
    '<div style="margin:4px 0 4px 8px;">'
    '<span style="background:#1e1e2e; color:#a6e3a1; border-radius:6px; '
    'padding:4px 10px; font-family:monospace; font-size:11px; display:inline-block;">'
    '🗄 SQL: {sql}</span></div>'
)
_HTML_ERROR = (
    '<div style="margin:6px 0;">'
    '<span style="background:#45475a; color:#f38ba8; border-radius:10px; '
    'padding:6px 12px; display:inline-block;">'
    '⚠ {texto}</span></div>'
)


def _escapar(texto: str) -> str:
    return (texto
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>"))


class TabChat(QWidget):
    instalar_modelo = pyqtSignal(str)   # emitido en 404 para auto-instalar

    def __init__(self, tab_config: TabConfigIA):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._tab_config       = tab_config
        self._historial:       list[dict] = []
        self._worker:          WorkerChat | None = None
        self._arranque_worker: WorkerArranqueOllama | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        # Estado
        row_top = QHBoxLayout()
        self.lbl_estado = QLabel("⚪  Sin configurar")
        self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        btn_limpiar = QPushButton("🗑  Limpiar chat")
        btn_limpiar.clicked.connect(self._limpiar)
        row_top.addWidget(self.lbl_estado)
        row_top.addStretch()
        row_top.addWidget(btn_limpiar)
        lay.addLayout(row_top)

        # Área de chat
        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(False)
        self.chat.setReadOnly(True)
        self.chat.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.chat.setMinimumHeight(80)
        lay.addWidget(self.chat, 1)

        # Input
        row_inp = QHBoxLayout()
        self.inp = QLineEdit()
        self.inp.setPlaceholderText("Preguntá algo sobre tus clientes, honorarios, liquidaciones...")
        self.inp.returnPressed.connect(self._enviar)
        self.btn_enviar = _btn("Enviar ↵", _ACCENT)
        self.btn_enviar.clicked.connect(self._enviar)
        row_inp.addWidget(self.inp)
        row_inp.addWidget(self.btn_enviar)
        lay.addLayout(row_inp)

        nota = QLabel(
            "El asistente puede consultar directamente tu base de datos. "
            "Las consultas son de solo lectura (SELECT)."
        )
        nota.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 11px;")
        lay.addWidget(nota)

        self._auto_arrancar_ollama()

    def _auto_arrancar_ollama(self):
        cfg = self._tab_config.get_config()
        if cfg.get("ai_modo", "local") != "local":
            self._actualizar_estado()
            return
        self._set_input(False)
        self.lbl_estado.setText("🟡  Verificando Ollama...")
        self.lbl_estado.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
        url = cfg.get("ai_ollama_url", "http://localhost:11434")
        self._arranque_worker = WorkerArranqueOllama(url)
        self._arranque_worker.estado.connect(
            lambda msg: self.lbl_estado.setText(f"🟡  {msg}")
        )
        self._arranque_worker.listo.connect(self._on_ollama_listo)
        self._arranque_worker.fallo.connect(self._on_ollama_fallo)
        self._arranque_worker.start()

    def _on_ollama_listo(self):
        self._set_input(True)
        cfg    = self._tab_config.get_config()
        modelo = cfg.get("ai_modelo_local", "—")
        self.lbl_estado.setText(f"🟢  Ollama listo — {modelo}")
        self.lbl_estado.setStyleSheet(f"color: {_GREEN}; font-size: 12px;")

    def _on_ollama_fallo(self, msg: str):
        self._set_input(True)
        self._agregar_html(_HTML_ERROR.format(texto=_escapar(msg)))
        self.lbl_estado.setText("🔴  Ollama no disponible")
        self.lbl_estado.setStyleSheet(f"color: {_RED}; font-size: 12px;")

    def _set_input(self, habilitado: bool):
        self.inp.setEnabled(habilitado)
        self.btn_enviar.setEnabled(habilitado)

    def _actualizar_estado(self):
        cfg  = self._tab_config.get_config()
        modo = cfg.get("ai_modo", "local")
        if modo == "local":
            modelo = cfg.get("ai_modelo_local", "—")
            self.lbl_estado.setText(f"🖥️  Ollama — {modelo}")
            self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        else:
            prov  = cfg.get("ai_proveedor", "—")
            key   = cfg.get("ai_api_key", "")
            if not key:
                self.lbl_estado.setText(f"☁️  {prov} — ⚠ sin API key")
                self.lbl_estado.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
            else:
                modelo = cfg.get("ai_modelo_cloud", "—")
                self.lbl_estado.setText(f"☁️  {prov} — {modelo}")
                self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")

    def _enviar(self):
        texto = self.inp.text().strip()
        if not texto or (self._worker and self._worker.isRunning()):
            return
        self.inp.clear()
        self._agregar_html(_HTML_USER.format(texto=_escapar(texto)))
        self._historial.append({"role": "user", "content": texto})

        cfg      = self._tab_config.get_config()
        sistema  = _SYSTEM_TPL.format(
            estudio=cfg.get("nombre_estudio", "el estudio"),
            schema=_schema_resumido(),
        )
        mensajes = [{"role": "system", "content": sistema}] + self._historial

        self._worker = WorkerChat(mensajes, cfg)
        self._worker.respuesta.connect(self._on_respuesta)
        self._worker.sql_usado.connect(self._on_sql)
        self._worker.error.connect(self._on_error)
        self._worker.estado.connect(self.lbl_estado.setText)
        self._worker.start()

        self._set_input(False)
        self.lbl_estado.setText("🟡  Pensando...")
        self.lbl_estado.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")

    def _on_respuesta(self, texto: str):
        self._agregar_html(_HTML_ASIST.format(texto=_escapar(texto)))
        self._historial.append({"role": "assistant", "content": texto})
        self._set_input(True)
        self._actualizar_estado()

    def _on_sql(self, sql: str, _resultado: str):
        self._agregar_html(_HTML_SQL.format(sql=_escapar(sql.replace("\n", " "))))

    def _on_error(self, msg: str):
        self._agregar_html(_HTML_ERROR.format(texto=_escapar(msg)))
        self._set_input(True)
        self.lbl_estado.setText("🔴  Error")
        self.lbl_estado.setStyleSheet(f"color: {_RED}; font-size: 12px;")
        # Modelo no instalado → disparar auto-instalación
        if "Modelo no encontrado" in msg:
            cfg    = self._tab_config.get_config()
            modelo = cfg.get("ai_modelo_local", "")
            if modelo:
                self.instalar_modelo.emit(modelo)

    def _agregar_html(self, html: str):
        cursor = self.chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.chat.setTextCursor(cursor)
        self.chat.insertHtml(html)
        self.chat.insertHtml("<br>")
        self.chat.ensureCursorVisible()

    def _limpiar(self):
        self._historial.clear()
        self.chat.clear()


# ══════════════════════════════════════════════════════════════
#  PANEL PRINCIPAL
# ══════════════════════════════════════════════════════════════

class PanelAsistente(QWidget):
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
        lbl = QLabel("🤖  Asistente IA")
        lbl.setStyleSheet(f"color: {_ACCENT}; font-size: 18px; font-weight: bold;")
        sub = QLabel("Chat con tu base de datos · Ollama local · Gemini Flash · Groq")
        sub.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        hl.addWidget(lbl)
        hl.addSpacing(16)
        hl.addWidget(sub)
        hl.addStretch()
        lay.addWidget(header)

        config_tab  = TabConfigIA()
        chat_tab    = TabChat(config_tab)
        tab_modelos = TabModelos(config_tab)

        tabs = QTabWidget()
        tabs.addTab(chat_tab,    "💬  Chat")
        tabs.addTab(tab_modelos, "🗂  Modelos")
        tabs.addTab(config_tab,  "⚙️  Configuración IA")

        # Re-verificar Ollama al volver al chat
        tabs.currentChanged.connect(
            lambda i: chat_tab._auto_arrancar_ollama() if i == 0 else None
        )

        # Modelo 404 → ir a tab Modelos y arrancar descarga
        def _on_instalar(modelo: str):
            tabs.setCurrentWidget(tab_modelos)
            tab_modelos.iniciar_instalacion(modelo)

        chat_tab.instalar_modelo.connect(_on_instalar)

        # Cambio de modelo activo → actualizar estado del chat
        tab_modelos.modelo_activo_cambiado.connect(
            lambda _: chat_tab._actualizar_estado()
        )

        lay.addWidget(tabs)
