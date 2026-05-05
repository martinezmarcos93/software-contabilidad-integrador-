# Software de Contabilidad Integrador

Aplicación de escritorio para estudios contables argentinos. Unifica y supera a [set_contable](https://github.com/martinezmarcos93/03-set_contable) y [herramientas_de_gestion](https://github.com/martinezmarcos93/herramientas_de_gestion), incorporando un asistente de IA local o cloud como capa transversal.

---

## Características

| Módulo | Descripción |
|--------|-------------|
| **Clientes** | Monotributistas y Responsables Inscriptos con detalle, cuenta corriente y claves AFIP/ARCA |
| **Honorarios** | Registro de cobros con actualización automática por índice INDEC |
| **Liquidador** | Sueldos CCT 130/75 (Empleados de Comercio) + exportación Libro de Sueldos Digital |
| **Archivos** | Renombrado en lote, detección de duplicados y archivos huérfanos |
| **Calculadoras** | IVA (neto ↔ total, monto de IVA), percepciones, porcentajes |
| **Asistente IA** | Chat en lenguaje natural con la base de datos — Ollama local o APIs cloud gratuitas |

---

## Stack técnico

- **UI**: PyQt6
- **Base de datos**: SQLite (archivo local en `data/contabilidad.db`)
- **IA local**: [Ollama](https://ollama.com) — modelos recomendados: `mistral:7b`, `llama3.2:3b`
- **IA cloud**: API compatible OpenAI — Gemini Flash (Google AI Studio, gratuito), Groq

---

## Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/martinezmarcos93/software-contabilidad-integrador.git
cd software-contabilidad-integrador

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar
python main.py
```

> La carpeta `data/` se crea automáticamente en el primer uso y está excluida del repositorio.  
> En la primera ejecución se configura el nombre del estudio, usuario y contraseña.

---

## Modelos Ollama recomendados

Para una PC con i5 / 16 GB RAM:

```bash
ollama pull mistral:7b       # Chat con DB, resúmenes — ~5 GB RAM
ollama pull llama3.2:3b      # Clasificación de archivos — ~3 GB RAM
```

Para el modo cloud, configurar la variable de entorno:

```
SOFTWARE_CONTABLE_API_KEY=tu_api_key_aqui
```

---

## Estructura del proyecto

```
├── main.py                  # Punto de entrada
├── db/
│   ├── connection.py        # Conexión SQLite unificada
│   └── schema.sql           # Esquema completo de tablas
├── config/
│   └── settings.py          # Configuración central (JSON en data/)
├── ui/
│   ├── login.py             # Login + configuración inicial
│   ├── main_window.py       # Ventana principal con sidebar
│   └── panels/              # Un archivo por sección
│       ├── panel_clientes.py
│       ├── panel_honorarios.py
│       ├── panel_liquidador.py
│       ├── panel_archivos.py
│       ├── panel_calculadoras.py
│       └── panel_asistente.py
└── data/                    # Generado localmente, no versionado
    ├── contabilidad.db
    ├── credenciales.json
    └── config.json
```

---

## Roadmap

- [x] **Fase 1** — Esqueleto: login, ventana principal con sidebar, DB unificada
- [x] **Fase 2** — Módulos de gestión: clientes, honorarios, liquidador, calculadoras
- [x] **Fase 3** — Gestión de archivos y carpetas de clientes
- [ ] **Fase 4** — Panel de Asistente IA (Ollama local + cloud)

---

## Proyectos de origen

Este software unifica y supera a:
- [`03-set_contable`](https://github.com/martinezmarcos93/03-set_contable) — Software contable PyQt6
- [`herramientas_de_gestion`](https://github.com/martinezmarcos93/herramientas_de_gestion) — Herramientas de oficina
