from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Optional

from app.auth.dependencies import require_role
from app.database import get_connection
from app.flash import flash
from app.templates_env import templates

router = APIRouter()

_require_comprador = require_role("COMPRADOR")

PAGE_SIZE = 50


def _get_pedidos_compras(
    estados: Optional[List[str]] = None,
    sector_id: Optional[int] = None,
    base_id: Optional[int] = None,
    page: int = 1,
) -> tuple:
    if estados is None:
        estados = ["AUTORIZADO", "RECIBIDO"]
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            filters = ["p.estado = ANY(%s)"]
            params: list = [estados]
            if sector_id:
                filters.append("p.sector_id = %s")
                params.append(sector_id)
            if base_id:
                filters.append("p.base_id = %s")
                params.append(base_id)

            where = " AND ".join(filters)

            cur.execute(
                f"SELECT COUNT(*) AS total FROM pedidos p WHERE {where}",
                params,
            )
            total = cur.fetchone()["total"]

            offset = (page - 1) * PAGE_SIZE
            cur.execute(
                f"""
                SELECT p.*,
                       ped.nombre_display AS pedidor_nombre,
                       s.nombre AS sector_nombre,
                       b.nombre AS base_nombre,
                       a.precio_ref,
                       a.comentario AS comentario_autorizacion,
                       aut.nombre_display AS autorizador_nombre,
                       a.resuelto_en AS fecha_autorizacion
                FROM pedidos p
                JOIN usuarios ped ON ped.id = p.pedidor_id
                JOIN sectores s ON s.id = p.sector_id
                JOIN bases b ON b.id = p.base_id
                LEFT JOIN autorizaciones a ON a.pedido_id = p.id
                LEFT JOIN usuarios aut ON aut.id = a.autorizador_id
                WHERE {where}
                ORDER BY a.resuelto_en DESC NULLS LAST
                LIMIT %s OFFSET %s
                """,
                params + [PAGE_SIZE, offset],
            )
            pedidos = cur.fetchall()
            return pedidos, total
    finally:
        conn.close()


def _get_filtros() -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM sectores WHERE activa = TRUE ORDER BY nombre")
            sectores = cur.fetchall()
            cur.execute("SELECT id, nombre FROM bases WHERE activa = TRUE ORDER BY nombre")
            bases = cur.fetchall()
            return {"sectores": sectores, "bases": bases}
    finally:
        conn.close()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    sector_id: Optional[int] = Query(None),
    base_id: Optional[int] = Query(None),
    estado: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    user: dict = Depends(_require_comprador),
):
    estados = [estado] if estado in ("AUTORIZADO", "RECIBIDO") else None
    pedidos, total = _get_pedidos_compras(estados, sector_id, base_id, page)
    filtros = _get_filtros()
    pages = max(1, -(-total // PAGE_SIZE))  # ceil division
    return templates.TemplateResponse(
        "modulo_c/dashboard.html",
        {
            "request": request,
            "user": user,
            "pedidos": pedidos,
            "filtros": filtros,
            "filtro_sector": sector_id,
            "filtro_base": base_id,
            "filtro_estado": estado or "",
            "page": page,
            "pages": pages,
            "total": total,
        },
    )


@router.post("/{pedido_id}/recibir")
async def marcar_recibido(
    pedido_id: int,
    request: Request,
    user: dict = Depends(_require_comprador),
):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, estado FROM pedidos WHERE id = %s", (pedido_id,))
            pedido = cur.fetchone()
            if not pedido or pedido["estado"] != "AUTORIZADO":
                flash(request, "Solo se pueden recibir pedidos con estado AUTORIZADO", "error")
                return RedirectResponse(url="/compras/dashboard", status_code=302)
            cur.execute(
                "UPDATE pedidos SET estado = 'RECIBIDO', actualizado_en = NOW() WHERE id = %s",
                (pedido_id,),
            )
            conn.commit()
    finally:
        conn.close()
    flash(request, f"Pedido #{pedido_id} marcado como recibido", "success")
    return RedirectResponse(url="/compras/dashboard", status_code=302)
