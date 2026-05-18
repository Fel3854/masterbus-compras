from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from typing import Optional

from app.auth.dependencies import require_role
from app.database import get_connection
from app.flash import flash
from app.templates_env import templates

router = APIRouter()

_require_pedidor = require_role("PEDIDOR")


def _get_mis_pedidos(user: dict) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if user["acceso_todas_bases"]:
                cur.execute(
                    """
                    SELECT p.*, s.nombre AS sector_nombre, b.nombre AS base_nombre,
                           a.comentario AS comentario_autorizacion
                    FROM pedidos p
                    JOIN sectores s ON s.id = p.sector_id
                    JOIN bases b ON b.id = p.base_id
                    LEFT JOIN autorizaciones a ON a.pedido_id = p.id
                    WHERE p.pedidor_id = %s
                    ORDER BY p.creado_en DESC
                    """,
                    (user["id"],),
                )
            else:
                cur.execute(
                    """
                    SELECT p.*, s.nombre AS sector_nombre, b.nombre AS base_nombre,
                           a.comentario AS comentario_autorizacion
                    FROM pedidos p
                    JOIN sectores s ON s.id = p.sector_id
                    JOIN bases b ON b.id = p.base_id
                    LEFT JOIN autorizaciones a ON a.pedido_id = p.id
                    WHERE p.pedidor_id = %s
                      AND p.base_id = ANY(%s)
                    ORDER BY p.creado_en DESC
                    """,
                    (user["id"], user["bases"] or []),
                )
            return cur.fetchall()
    finally:
        conn.close()


def _buscar_catalogo(q: str) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            like = f"%{q.upper()}%"
            cur.execute(
                """
                SELECT id, codigo, descripcion, unidad_defecto, ultimo_precio
                FROM catalogo
                WHERE activo = TRUE
                  AND (UPPER(descripcion) LIKE %s OR UPPER(codigo) LIKE %s)
                ORDER BY descripcion
                LIMIT 30
                """,
                (like, like),
            )
            return cur.fetchall()
    finally:
        conn.close()


def _get_bases_for_user(user: dict) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if user["acceso_todas_bases"]:
                cur.execute("SELECT id, nombre FROM bases WHERE activa = TRUE ORDER BY nombre")
            else:
                cur.execute(
                    "SELECT id, nombre FROM bases WHERE id = ANY(%s) AND activa = TRUE ORDER BY nombre",
                    (user["bases"] or [],),
                )
            return cur.fetchall()
    finally:
        conn.close()


@router.get("/mis-pedidos", response_class=HTMLResponse)
async def mis_pedidos(request: Request, user: dict = Depends(_require_pedidor)):
    pedidos = _get_mis_pedidos(user)
    return templates.TemplateResponse(
        "modulo_a/mis_pedidos.html",
        {"request": request, "user": user, "pedidos": pedidos},
    )


@router.get("/nuevo", response_class=HTMLResponse)
async def nuevo_pedido_form(request: Request, user: dict = Depends(_require_pedidor)):
    bases = _get_bases_for_user(user)
    return templates.TemplateResponse(
        "modulo_a/nuevo_pedido.html",
        {"request": request, "user": user, "bases": bases},
    )


@router.get("/catalogo-buscar")
async def catalogo_buscar(
    q: str = Query("", min_length=0),
    _: dict = Depends(_require_pedidor),
):
    if len(q.strip()) < 3:
        return JSONResponse([])
    items = _buscar_catalogo(q.strip())
    return JSONResponse([
        {
            "id": r["id"],
            "codigo": r["codigo"] or "",
            "descripcion": r["descripcion"],
            "unidad": r["unidad_defecto"] or "",
        }
        for r in items
    ])


@router.post("/nuevo")
async def nuevo_pedido_submit(
    request: Request,
    tipo: str = Form(...),
    base_id: int = Form(...),
    catalogo_id: Optional[int] = Form(None),
    descripcion: Optional[str] = Form(None),
    numero_parte: Optional[str] = Form(None),
    cantidad: float = Form(...),
    unidad: str = Form(...),
    notas: Optional[str] = Form(None),
    user: dict = Depends(_require_pedidor),
):
    bases_validas = _get_bases_for_user(user)
    ids_validos = {b["id"] for b in bases_validas}
    if base_id not in ids_validos:
        flash(request, "Base no permitida para este usuario", "error")
        return RedirectResponse(url="/pedidos/nuevo", status_code=302)

    if tipo == "CATALOGADO":
        if not catalogo_id:
            flash(request, "Seleccione un ítem del catálogo", "error")
            return RedirectResponse(url="/pedidos/nuevo", status_code=302)
        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT descripcion FROM catalogo WHERE id = %s AND activo = TRUE",
                    (catalogo_id,),
                )
                item = cur.fetchone()
                if not item:
                    flash(request, "Ítem de catálogo no válido", "error")
                    return RedirectResponse(url="/pedidos/nuevo", status_code=302)
                descripcion_final = item["descripcion"]
        finally:
            conn.close()
    else:
        if not descripcion or not descripcion.strip():
            flash(request, "Ingrese una descripción para el ítem libre", "error")
            return RedirectResponse(url="/pedidos/nuevo", status_code=302)
        catalogo_id = None
        descripcion_final = descripcion.strip()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pedidos
                    (pedidor_id, sector_id, base_id, catalogo_id, descripcion,
                     numero_parte, cantidad, unidad, notas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user["id"],
                    user["sector_id"],  # siempre del usuario autenticado
                    base_id,
                    catalogo_id,
                    descripcion_final,
                    numero_parte.strip() if numero_parte else None,
                    cantidad,
                    unidad.strip(),
                    notas.strip() if notas else None,
                ),
            )
            conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url="/pedidos/mis-pedidos", status_code=302)
