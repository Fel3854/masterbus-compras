from __future__ import annotations

import pymysql
import pymysql.cursors
from app.config import settings


def get_masterbus_connection():
    return pymysql.connect(
        host=settings.masterbus_host,
        port=settings.masterbus_port,
        user=settings.masterbus_user,
        password=settings.masterbus_pass,
        database=settings.masterbus_db,
        connect_timeout=15,
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


def sync_catalogo() -> dict:
    """
    Sincroniza piezas de MasterBus hacia catalogo en Supabase.
    Upsert por masterbus_id. El precio local seteado por autorizaciones
    no se pisa si MasterBus no tiene historial de compra para esa pieza.
    """
    mb_conn = get_masterbus_connection()
    try:
        with mb_conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    p.id          AS masterbus_id,
                    p.nro_pieza   AS codigo,
                    p.descripcion,
                    um.nombre     AS unidad_defecto,
                    IF(p.habilitada = 1 AND p.deleted_at IS NULL, 1, 0) AS activo,
                    lp.costo      AS ultimo_precio,
                    lp.fecha      AS ultima_compra
                FROM piezas p
                JOIN unidades_medidas um ON um.id = p.unidad_medida_id
                LEFT JOIN (
                    SELECT
                        ocd.piezas_id,
                        ocd.costo,
                        DATE(oc.created_at) AS fecha,
                        ROW_NUMBER() OVER (
                            PARTITION BY ocd.piezas_id
                            ORDER BY oc.created_at DESC
                        ) AS rn
                    FROM orden_compra_detalle ocd
                    JOIN orden_compra oc ON oc.id = ocd.orden_compra_id
                    WHERE ocd.deleted_at IS NULL AND ocd.costo > 0
                ) lp ON lp.piezas_id = p.id AND lp.rn = 1
                WHERE p.deleted_at IS NULL
                ORDER BY p.id
                """
            )
            piezas = cur.fetchall()
    finally:
        mb_conn.close()

    if not piezas:
        return {"total": 0}

    import psycopg2
    import psycopg2.extras
    from app.config import settings as s

    rows = [
        (
            p["masterbus_id"],
            p["codigo"],
            p["descripcion"],
            p["unidad_defecto"],
            bool(p["activo"]),
            float(p["ultimo_precio"]) if p["ultimo_precio"] else None,
            p["ultima_compra"],
        )
        for p in piezas
    ]

    pg_conn = psycopg2.connect(s.database_url)
    try:
        with pg_conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO catalogo
                    (masterbus_id, codigo, descripcion, unidad_defecto, activo,
                     ultimo_precio, ultima_compra)
                VALUES %s
                ON CONFLICT (masterbus_id) DO UPDATE SET
                    codigo         = EXCLUDED.codigo,
                    descripcion    = EXCLUDED.descripcion,
                    unidad_defecto = EXCLUDED.unidad_defecto,
                    activo         = EXCLUDED.activo,
                    ultimo_precio  = COALESCE(EXCLUDED.ultimo_precio, catalogo.ultimo_precio),
                    ultima_compra  = COALESCE(EXCLUDED.ultima_compra, catalogo.ultima_compra)
                """,
                rows,
                page_size=500,
            )
        pg_conn.commit()
    finally:
        pg_conn.close()

    return {"total": len(piezas)}
