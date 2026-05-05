"""
ui/panels/panel_asistente.py — Asistente IA con acceso a la base de datos
Chat en lenguaje natural · Ollama local · Gemini Flash · Groq
[Fase 4]
"""
from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QLineEdit, QLabel, QTextBrowser,
    QMessageBox, QGroupBox, QRadioButton, QButtonGroup,
    QComboBox, QFrame, QSizePolicy,
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


def _btn(text: str, color: str = _ACCENT) -> QPushButton:
    b = QPushButton(text)
    b.setStyleSheet(
        f"QPushButton {{ background: {color}; color: {_BG2}; border-radius: 5px; "
        f"padding: 6px 16px; font-weight: bold; font-size: 12px; border: none; }}"
        f"QPushButton:hover {{ background: {color}cc; }}"
    )
    return b


# ══════════════════════════════════════════════════════════════
#  WORKER: LLAMADA AL LLM
# ══════════════════════════════════════════════════════════════

class WorkerChat(QThread):
    respuesta  = pyqtSignal(str)
    sql_usado  = pyqtSignal(str, str)   # sql, resultado_json
    error      = pyqtSignal(str)

    def __init__(self, mensajes: list[dict], cfg: dict):
        super().__init__()
        self._mensajes = mensajes
        self._cfg      = cfg

    def run(self):
        try:
            resp = self._llamar(self._mensajes)

            sql = self._extraer_sql(resp)
            if sql:
                resultado = self._ejecutar_sql(sql)
                self.sql_usado.emit(sql, resultado)
                # Segunda vuelta: LLM recibe los datos y formula la respuesta
                msgs2 = self._mensajes + [
                    {"role": "assistant", "content": resp},
                    {"role": "user",      "content": f"[RESULTADO DE LA CONSULTA]\n{resultado}"},
                ]
                resp = self._llamar(msgs2)

            self.respuesta.emit(resp)
        except urllib.error.URLError as e:
            self.error.emit(f"No se pudo conectar al servidor de IA.\n{e.reason}")
        except Exception as e:
            self.error.emit(str(e))

    # ── HTTP ─────────────────────────────────────────────────

    def _llamar(self, mensajes: list[dict]) -> str:
        cfg  = self._cfg
        modo = cfg.get("ai_modo", "local")

        if modo == "local":
            url    = cfg.get("ai_ollama_url", "http://localhost:11434").rstrip("/") + "/api/chat"
            modelo = cfg.get("ai_modelo_local", "mistral:7b")
            payload = {"model": modelo, "messages": mensajes, "stream": False}
            data    = self._post(url, payload)
            return data["message"]["content"]
        else:
            base   = cfg.get("ai_cloud_base_url", "").rstrip("/")
            url    = f"{base}/chat/completions"
            api_key = cfg.get("ai_api_key", "")
            modelo  = cfg.get("ai_modelo_cloud", "gemini-2.0-flash")
            payload = {"model": modelo, "messages": mensajes, "max_tokens": 2048}
            headers = {"Authorization": f"Bearer {api_key}"}
            data    = self._post(url, payload, headers)
            return data["choices"][0]["message"]["content"]

    def _post(self, url: str, payload: dict, extra: dict | None = None) -> dict:
        body    = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if extra:
            headers.update(extra)
        req = urllib.request.Request(url, data=body, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read())

    # ── SQL ──────────────────────────────────────────────────

    def _extraer_sql(self, texto: str) -> str | None:
        m = re.search(r"```(?:sql|SQL)\s*\n(.*?)\n```", texto, re.DOTALL)
        if not m:
            return None
        sql = m.group(1).strip()
        # Solo SELECT permitido
        primera = sql.lstrip().split()[0].upper() if sql.split() else ""
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

        # ── Modo ─────────────────────────────────────────────
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
        row_mod.addWidget(QLabel("Modelo:"))
        self.inp_modelo_local = QLineEdit()
        self.inp_modelo_local.setPlaceholderText("mistral:7b  ·  llama3.2:3b")
        row_mod.addWidget(self.inp_modelo_local)
        gl.addLayout(row_mod)

        info_local = QLabel(
            "Ollama debe estar corriendo antes de usar el chat.\n"
            "Instalación: https://ollama.com  —  Modelos recomendados: mistral:7b, llama3.2:3b"
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
        btn_test  = _btn("🔌  Probar conexión", _ACCENT2)
        btn_test.clicked.connect(self._probar)
        btn_guardar = _btn("💾  Guardar", _GREEN)
        btn_guardar.clicked.connect(self._guardar)
        self.lbl_test = QLabel("")
        self.lbl_test.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")
        row_btns.addWidget(btn_test)
        row_btns.addWidget(btn_guardar)
        row_btns.addSpacing(12)
        row_btns.addWidget(self.lbl_test)
        row_btns.addStretch()
        lay.addLayout(row_btns)
        lay.addStretch()

        # ── Poblar valores ───────────────────────────────────
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
        self.inp_modelo_local.setText(cfg.get("ai_modelo_local", "mistral:7b"))

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
        cfg["ai_modelo_local"] = self.inp_modelo_local.text().strip() or "mistral:7b"
        prov = self.cmb_proveedor.currentText()
        cfg["ai_proveedor"]       = prov
        cfg["ai_cloud_base_url"]  = PROVEEDORES.get(prov, {}).get("base_url", "")
        cfg["ai_api_key"]         = self.inp_api_key.text().strip()
        cfg["ai_modelo_cloud"]    = self.inp_modelo_cloud.text().strip()
        settings.guardar(cfg)
        self._cfg = cfg
        self.lbl_test.setText("✅  Guardado.")

    def _probar(self):
        self.lbl_test.setText("Probando...")
        cfg = self._get_config_actual()
        worker = _WorkerTest(cfg)
        worker.resultado.connect(lambda ok, msg: self.lbl_test.setText(
            f"✅  {msg}" if ok else f"❌  {msg}"
        ))
        worker.start()
        self._test_worker = worker

    def _get_config_actual(self) -> dict:
        cfg = settings.cargar()
        cfg["ai_modo"]         = "local" if self.rb_local.isChecked() else "cloud"
        cfg["ai_ollama_url"]   = self.inp_ollama_url.text().strip() or "http://localhost:11434"
        cfg["ai_modelo_local"] = self.inp_modelo_local.text().strip() or "mistral:7b"
        prov = self.cmb_proveedor.currentText()
        cfg["ai_proveedor"]      = prov
        cfg["ai_cloud_base_url"] = PROVEEDORES.get(prov, {}).get("base_url", "")
        cfg["ai_api_key"]        = self.inp_api_key.text().strip()
        cfg["ai_modelo_cloud"]   = self.inp_modelo_cloud.text().strip()
        return cfg

    def get_config(self) -> dict:
        return self._get_config_actual()


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
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as r:
                    data   = json.loads(r.read())
                    models = [m["name"] for m in data.get("models", [])]
                    txt    = f"Ollama OK — {len(models)} modelo(s): {', '.join(models[:3])}"
                    self.resultado.emit(True, txt)
            else:
                base  = cfg.get("ai_cloud_base_url", "").rstrip("/")
                key   = cfg.get("ai_api_key", "")
                model = cfg.get("ai_modelo_cloud", "")
                if not key:
                    self.resultado.emit(False, "API Key vacía.")
                    return
                url     = f"{base}/chat/completions"
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": "Hola"}],
                    "max_tokens": 5,
                }
                body = json.dumps(payload).encode()
                req  = urllib.request.Request(
                    url, data=body,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {key}"},
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    json.loads(r.read())
                self.resultado.emit(True, f"Conexión OK con {cfg.get('ai_proveedor','')}")
        except urllib.error.HTTPError as e:
            self.resultado.emit(False, f"HTTP {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            self.resultado.emit(False, f"Sin conexión: {e.reason}")
        except Exception as e:
            self.resultado.emit(False, str(e))


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
    def __init__(self, tab_config: TabConfigIA):
        super().__init__()
        self.setStyleSheet(STYLE_BASE)
        self._tab_config  = tab_config
        self._historial:  list[dict] = []
        self._worker:     WorkerChat | None = None

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
        lay.addWidget(self.chat)

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

        self._actualizar_estado()

    def _actualizar_estado(self):
        cfg  = self._tab_config.get_config()
        modo = cfg.get("ai_modo", "local")
        if modo == "local":
            modelo = cfg.get("ai_modelo_local", "—")
            self.lbl_estado.setText(f"🖥️  Ollama — {modelo}")
        else:
            prov   = cfg.get("ai_proveedor", "—")
            modelo = cfg.get("ai_modelo_cloud", "—")
            key    = cfg.get("ai_api_key", "")
            if not key:
                self.lbl_estado.setText(f"☁️  {prov} — ⚠ sin API key")
                self.lbl_estado.setStyleSheet(f"color: {_YELLOW}; font-size: 12px;")
            else:
                self.lbl_estado.setText(f"☁️  {prov} — {modelo}")
                self.lbl_estado.setStyleSheet(f"color: {_TEXT_DIM}; font-size: 12px;")

    def _enviar(self):
        texto = self.inp.text().strip()
        if not texto or self._worker and self._worker.isRunning():
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
        self._worker.start()

        self.inp.setEnabled(False)
        self.btn_enviar.setEnabled(False)
        self.lbl_estado.setText("🟡  Pensando...")

    def _on_respuesta(self, texto: str):
        self._agregar_html(_HTML_ASIST.format(texto=_escapar(texto)))
        self._historial.append({"role": "assistant", "content": texto})
        self.inp.setEnabled(True)
        self.btn_enviar.setEnabled(True)
        self._actualizar_estado()

    def _on_sql(self, sql: str, resultado: str):
        self._agregar_html(_HTML_SQL.format(sql=_escapar(sql.replace("\n", " "))))

    def _on_error(self, msg: str):
        self._agregar_html(_HTML_ERROR.format(texto=_escapar(msg)))
        self.inp.setEnabled(True)
        self.btn_enviar.setEnabled(True)
        self.lbl_estado.setText(f"🔴  Error de conexión")
        self.lbl_estado.setStyleSheet(f"color: {_RED}; font-size: 12px;")

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

        tabs = QTabWidget()
        config_tab = TabConfigIA()
        chat_tab   = TabChat(config_tab)

        tabs.addTab(chat_tab,   "💬  Chat")
        tabs.addTab(config_tab, "⚙️  Configuración IA")

        # Cuando el usuario cambia a la tab de chat, actualiza el estado
        tabs.currentChanged.connect(
            lambda i: chat_tab._actualizar_estado() if i == 0 else None
        )
        lay.addWidget(tabs)
