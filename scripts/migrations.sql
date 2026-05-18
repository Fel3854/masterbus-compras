-- ============================================================
-- SISTEMA DE GESTIÓN DE COMPRAS — Migraciones completas
-- Pegar todo en el SQL Editor de Supabase y ejecutar.
-- ============================================================

-- Migration 01: bases y sectores
CREATE TABLE IF NOT EXISTS bases (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS sectores (
    id     SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    activa BOOLEAN NOT NULL DEFAULT TRUE
);

-- Migration 02: usuarios y roles
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rol_tipo') THEN
        CREATE TYPE rol_tipo AS ENUM ('PEDIDOR', 'AUTORIZADOR', 'COMPRADOR');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS usuarios (
    id                  SERIAL PRIMARY KEY,
    username            VARCHAR(50) NOT NULL UNIQUE,
    nombre_display      VARCHAR(100) NOT NULL,
    password_hash       VARCHAR(255) NOT NULL,
    sector_id           INTEGER NOT NULL REFERENCES sectores(id),
    acceso_todas_bases  BOOLEAN NOT NULL DEFAULT FALSE,
    activo              BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usuario_roles (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    rol        rol_tipo NOT NULL,
    PRIMARY KEY (usuario_id, rol)
);

CREATE TABLE IF NOT EXISTS usuario_bases (
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    base_id    INTEGER NOT NULL REFERENCES bases(id) ON DELETE CASCADE,
    PRIMARY KEY (usuario_id, base_id)
);

-- Migration 03: catálogo de artículos
CREATE TABLE IF NOT EXISTS catalogo (
    id             SERIAL PRIMARY KEY,
    codigo         VARCHAR(50) UNIQUE,
    descripcion    VARCHAR(255) NOT NULL,
    unidad_defecto VARCHAR(30),
    ultimo_precio  NUMERIC(12, 2),
    ultima_compra  DATE,
    activo         BOOLEAN NOT NULL DEFAULT TRUE
);

-- Migration 04: pedidos y autorizaciones
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pedido_estado') THEN
        CREATE TYPE pedido_estado AS ENUM ('PENDIENTE', 'AUTORIZADO', 'RECHAZADO', 'RECIBIDO');
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS pedidos (
    id             SERIAL PRIMARY KEY,
    pedidor_id     INTEGER NOT NULL REFERENCES usuarios(id),
    sector_id      INTEGER NOT NULL REFERENCES sectores(id),
    base_id        INTEGER NOT NULL REFERENCES bases(id),
    catalogo_id    INTEGER REFERENCES catalogo(id),
    descripcion    VARCHAR(255) NOT NULL,
    numero_parte   VARCHAR(100),
    cantidad       NUMERIC(10, 2) NOT NULL,
    unidad         VARCHAR(30) NOT NULL,
    notas          TEXT,
    estado         pedido_estado NOT NULL DEFAULT 'PENDIENTE',
    creado_en      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS autorizaciones (
    id             SERIAL PRIMARY KEY,
    pedido_id      INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    autorizador_id INTEGER NOT NULL REFERENCES usuarios(id),
    decision       pedido_estado NOT NULL,
    comentario     TEXT,
    precio_ref     NUMERIC(12, 2),
    resuelto_en    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Migration 05: índices para queries de visibilidad
CREATE INDEX IF NOT EXISTS idx_pedidos_pedidor       ON pedidos(pedidor_id);
CREATE INDEX IF NOT EXISTS idx_pedidos_sector_estado ON pedidos(sector_id, estado);
CREATE INDEX IF NOT EXISTS idx_pedidos_base_estado   ON pedidos(base_id, estado);
CREATE INDEX IF NOT EXISTS idx_pedidos_estado        ON pedidos(estado);
