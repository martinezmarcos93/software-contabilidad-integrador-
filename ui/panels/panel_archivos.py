"""
panel_archivos.py — Gestión de archivos: renombrado, duplicados, huérfanos
                    [Fase 3]
"""
from ui.panels._base import PanelBase


class PanelArchivos(PanelBase):
    titulo    = "Gestión de Archivos"
    subtitulo = "Renombrado en lote · Detección de duplicados · Archivos huérfanos"
    fase      = 3
