from __future__ import annotations

import bcrypt
from app.database import get_connection


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def load_user_by_username(username: str) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.nombre_display,
                    u.password_hash,
                    u.sector_id,
                    u.acceso_todas_bases,
                    s.nombre AS sector_nombre,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT ur.rol::text), NULL) AS roles,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT ub.base_id), NULL)   AS bases
                FROM usuarios u
                JOIN sectores s ON s.id = u.sector_id
                LEFT JOIN usuario_roles ur ON ur.usuario_id = u.id
                LEFT JOIN usuario_bases ub ON ub.usuario_id = u.id
                WHERE u.username = %s AND u.activo = TRUE
                GROUP BY u.id, s.nombre
                """,
                (username,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


def load_user_by_id(user_id: int) -> dict | None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    u.id,
                    u.username,
                    u.nombre_display,
                    u.sector_id,
                    u.acceso_todas_bases,
                    s.nombre AS sector_nombre,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT ur.rol::text), NULL) AS roles,
                    ARRAY_REMOVE(ARRAY_AGG(DISTINCT ub.base_id), NULL)   AS bases
                FROM usuarios u
                JOIN sectores s ON s.id = u.sector_id
                LEFT JOIN usuario_roles ur ON ur.usuario_id = u.id
                LEFT JOIN usuario_bases ub ON ub.usuario_id = u.id
                WHERE u.id = %s AND u.activo = TRUE
                GROUP BY u.id, s.nombre
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    finally:
        conn.close()


# Orden de prioridad para redirect post-login
_ROLE_HOME = {
    "COMPRADOR":   "/compras/dashboard",
    "AUTORIZADOR": "/autorizaciones/pendientes",
    "PEDIDOR":     "/pedidos/mis-pedidos",
}


def get_home_for_user(roles: list[str]) -> str:
    for role in ("COMPRADOR", "AUTORIZADOR", "PEDIDOR"):
        if role in roles:
            return _ROLE_HOME[role]
    return "/login"
