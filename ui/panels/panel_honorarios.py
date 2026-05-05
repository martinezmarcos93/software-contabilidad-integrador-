"""
panel_honorarios.py — Honorarios con actualización por índice INDEC
                      [Fase 2]
"""
from ui.panels._base import PanelBase


class PanelHonorarios(PanelBase):
    titulo    = "Honorarios"
    subtitulo = "Registro de cobros · Actualización por inflación INDEC"
    fase      = 2
