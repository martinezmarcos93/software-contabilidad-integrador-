"""
panel_asistente.py — Asistente IA: chat en lenguaje natural con la base de datos
                     Soporta Ollama (local) y APIs cloud compatibles OpenAI
                     [Fase 4]
"""
from ui.panels._base import PanelBase


class PanelAsistente(PanelBase):
    titulo    = "Asistente IA"
    subtitulo = "Chat con la base de datos en lenguaje natural\nOllama local · Gemini Flash · Groq"
    fase      = 4
