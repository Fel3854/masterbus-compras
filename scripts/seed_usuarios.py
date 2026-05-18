"""
Script de carga inicial de datos.
Ejecutar UNA sola vez desde la carpeta webservice/:
  python scripts/seed_usuarios.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.auth.service import hash_password
from app.database import get_connection

PASSWORD_DEFAULT = "cambiar123"


BASES = ["ZTE", "SALTA", "JUJUY"]
SECTORES = ["CALIDAD", "RRHH", "MTO", "ABAST."]

USUARIOS = [
    {
        "username": "fulano",
        "nombre_display": "Fulano",
        "sector": "CALIDAD",
        "acceso_todas_bases": False,
        "bases": ["ZTE"],
        "roles": ["PEDIDOR"],
    },
    {
        "username": "mengano",
        "nombre_display": "Mengano",
        "sector": "RRHH",
        "acceso_todas_bases": False,
        "bases": ["ZTE"],
        "roles": ["PEDIDOR"],
    },
    {
        "username": "ariels",
        "nombre_display": "Ariel S.",
        "sector": "MTO",
        "acceso_todas_bases": True,
        "bases": [],
        "roles": ["PEDIDOR", "AUTORIZADOR"],
    },
    {
        "username": "julietac",
        "nombre_display": "Julieta C",
        "sector": "ABAST.",
        "acceso_todas_bases": True,
        "bases": [],
        "roles": ["PEDIDOR", "COMPRADOR"],
    },
    {
        "username": "cicrano",
        "nombre_display": "Cicrano",
        "sector": "MTO",
        "acceso_todas_bases": False,
        "bases": ["SALTA"],
        "roles": ["PEDIDOR"],
    },
    {
        "username": "juancito",
        "nombre_display": "Juancito",
        "sector": "MTO",
        "acceso_todas_bases": False,
        "bases": ["SALTA"],
        "roles": ["PEDIDOR"],
    },
]


def run():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Insertar bases
            print("Insertando bases...")
            for nombre in BASES:
                cur.execute(
                    "INSERT INTO bases (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
                    (nombre,),
                )

            # Insertar sectores
            print("Insertando sectores...")
            for nombre in SECTORES:
                cur.execute(
                    "INSERT INTO sectores (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING",
                    (nombre,),
                )

            # Cargar mapas de ids
            cur.execute("SELECT id, nombre FROM bases")
            base_map = {row["nombre"]: row["id"] for row in cur.fetchall()}
            cur.execute("SELECT id, nombre FROM sectores")
            sector_map = {row["nombre"]: row["id"] for row in cur.fetchall()}

            # Insertar usuarios
            print("Insertando usuarios...")
            pwd_hash = hash_password(PASSWORD_DEFAULT)
            for u in USUARIOS:
                sector_id = sector_map[u["sector"]]
                cur.execute(
                    """
                    INSERT INTO usuarios (username, nombre_display, password_hash, sector_id, acceso_todas_bases)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (username) DO UPDATE
                      SET nombre_display = EXCLUDED.nombre_display,
                          sector_id = EXCLUDED.sector_id,
                          acceso_todas_bases = EXCLUDED.acceso_todas_bases
                    RETURNING id
                    """,
                    (u["username"], u["nombre_display"], pwd_hash, sector_id, u["acceso_todas_bases"]),
                )
                user_id = cur.fetchone()["id"]

                # Roles
                cur.execute("DELETE FROM usuario_roles WHERE usuario_id = %s", (user_id,))
                for rol in u["roles"]:
                    cur.execute(
                        "INSERT INTO usuario_roles (usuario_id, rol) VALUES (%s, %s::rol_tipo)",
                        (user_id, rol),
                    )

                # Bases específicas
                cur.execute("DELETE FROM usuario_bases WHERE usuario_id = %s", (user_id,))
                for base_nombre in u["bases"]:
                    cur.execute(
                        "INSERT INTO usuario_bases (usuario_id, base_id) VALUES (%s, %s)",
                        (user_id, base_map[base_nombre]),
                    )

                roles_str = ", ".join(u["roles"])
                bases_str = ", ".join(u["bases"]) if u["bases"] else "TODAS"
                print(f"  ✓ {u['username']} ({u['sector']}/{bases_str}) [{roles_str}]")

        conn.commit()
        print(f"\nSeed completado. Contraseña por defecto: '{PASSWORD_DEFAULT}'")
        print("⚠  Recordá cambiar las contraseñas antes de usar en producción.")
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    run()
