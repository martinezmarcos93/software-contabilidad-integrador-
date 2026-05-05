-- ============================================================
-- Schema unificado — Software de Contabilidad Integrador
-- ============================================================

-- Clientes monotributistas
CREATE TABLE IF NOT EXISTS monotributistas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    revision        INTEGER DEFAULT 0,
    nombre          TEXT,
    categoria       TEXT,
    actividad       TEXT,
    cuit            TEXT,
    clave_afip      TEXT,
    clave_agip_arba TEXT,
    iibb            TEXT,
    observaciones   TEXT,
    condicion       TEXT DEFAULT 'Activo'
);

-- Clientes responsables inscriptos
CREATE TABLE IF NOT EXISTS responsables_inscriptos (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    revision       INTEGER DEFAULT 0,
    razon_social   TEXT,
    cuit           TEXT,
    clave_arca     TEXT,
    clave_arba     TEXT,
    clave_agip     TEXT,
    condicion_iibb TEXT,
    observaciones  TEXT,
    condicion      TEXT DEFAULT 'Activo'
);

-- Detalle de contacto y configuración por cliente
CREATE TABLE IF NOT EXISTS clientes_detalle (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,       -- 'mono' | 'resp'
    cliente_id  INTEGER NOT NULL,
    cel         TEXT DEFAULT '',
    mail        TEXT DEFAULT '',
    banco       TEXT DEFAULT '',
    cbu         TEXT DEFAULT '',
    honorarios  REAL DEFAULT 0,
    notas       TEXT DEFAULT '',
    UNIQUE(tipo, cliente_id)
);

-- Cuenta corriente por cliente
CREATE TABLE IF NOT EXISTS cuenta_corriente (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,       -- 'mono' | 'resp'
    cliente_id  INTEGER NOT NULL,
    fecha       TEXT NOT NULL,       -- ISO: YYYY-MM-DD
    descripcion TEXT NOT NULL,
    debe        REAL DEFAULT 0,
    haber       REAL DEFAULT 0
);

-- Registro de honorarios cobrados
CREATE TABLE IF NOT EXISTS honorarios_cobrados (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo        TEXT NOT NULL,
    cliente_id  INTEGER NOT NULL,
    fecha       TEXT NOT NULL,
    descripcion TEXT DEFAULT '',
    debe        REAL DEFAULT 0,
    haber       REAL DEFAULT 0
);

-- LSD: datos del empleador (fila única)
CREATE TABLE IF NOT EXISTS empleador_lsd (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    cuit           TEXT NOT NULL DEFAULT '',
    razon_social   TEXT DEFAULT '',
    tipo_empresa   TEXT DEFAULT '1',
    cod_actividad  TEXT DEFAULT '001',
    cod_modalidad  TEXT DEFAULT '102',
    cod_localidad  TEXT DEFAULT '00',
    ident_envio    TEXT DEFAULT 'SJ'
);

-- LSD: nómina de empleados
CREATE TABLE IF NOT EXISTS nomina_lsd (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cuil             TEXT NOT NULL UNIQUE,
    apellido_nombre  TEXT DEFAULT '',
    legajo           TEXT DEFAULT '',
    fecha_ingreso    TEXT DEFAULT '',
    cbu              TEXT DEFAULT '',
    forma_pago       TEXT DEFAULT '1',
    cod_obra_social  TEXT DEFAULT '000000',
    cod_situacion    TEXT DEFAULT '01',
    cod_condicion    TEXT DEFAULT '01',
    cod_siniestrado  TEXT DEFAULT '00',
    scvo             INTEGER DEFAULT 1,
    cct              INTEGER DEFAULT 1,
    reduccion        INTEGER DEFAULT 0,
    activo           INTEGER DEFAULT 1
);

-- LSD: parámetros ARCA por concepto
CREATE TABLE IF NOT EXISTS parametros_arca (
    cod_empleador  TEXT PRIMARY KEY,
    descripcion    TEXT DEFAULT '',
    cod_arca       TEXT DEFAULT '',
    tipo           TEXT DEFAULT 'REM',
    debcred        TEXT DEFAULT 'C'
);

-- LSD: tope ANSES por período
CREATE TABLE IF NOT EXISTS tope_anses (
    periodo  TEXT PRIMARY KEY,
    tope     REAL NOT NULL
);

-- LSD: historial de liquidaciones generadas
CREATE TABLE IF NOT EXISTS historial_lsd (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cuil             TEXT,
    periodo          TEXT,
    nro_liquidacion  INTEGER,
    path_txt         TEXT,
    fecha_generacion TEXT
);
