"""
config/settings.py — Configuración central de la aplicación
"""
import json
from pathlib import Path

DATA_DIR    = Path(__file__).parent.parent / "data"
CONFIG_FILE = DATA_DIR / "config.json"

DEFAULTS = {
    "nombre_estudio":             "",
    "ruta_base":                  "",
    "honorario_base":             25475.00,
    "honorario_base_mes":         "2025-07",
    "meses_inactividad":          12,
    "carpetas_cliente_default":   ["Documentos", "Constancias y credenciales", "Facturacion"],
    "ai_modo":                    "local",           # "local" | "cloud"
    "ai_modelo_local":            "",                # vacío = autodetectar primer modelo disponible
    "ai_modelo_cloud":            "gemini-2.0-flash",
    "ai_cloud_base_url":          "https://generativelanguage.googleapis.com/v1beta/openai/",
}


def cargar() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in DEFAULTS.items():
            if k not in data:
                data[k] = v
        return data
    return DEFAULTS.copy()


def guardar(config: dict):
    DATA_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
