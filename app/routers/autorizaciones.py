from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

from app.auth.dependencies import require_role
from app.database import get_connection
from app.flash import flash
from app.templates_env import templates

router = APIRouter()

_require_autorizador = require_role("AUTORIZADOR")


def _get_pendientes(user: dict) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if user["acceso_todas_bases"]:
                cur.execute(
                    """
                    SELECT p.*,
                           u.nombre_display AS pedidor_nombre,
                           s.nombre AS sector_nombre,
                           b.nombre AS base_nombre,
                           c.ultimo_precio AS precio_referencia,
                           c.descripcion AS descripcion_catalogo
                    FROM pedidos p
                    JOIN usuarios u ON u.id = p.pedidor_id
                    JOIN sectores s ON s.id = p.sector_id
                    JOIN bases b ON b.id = p.base_id
                    LEFT JOIN catalogo c ON c.id = p.catalogo_id
                    WHERE p.sector_id = %s
                      AND p.estado = 'PENDIENTE'
                      AND p.pedidor_id != %s
                    ORDER BY p.creado_en ASC
                    """,
                    (user["sector_id"], user["id"]),
                )
            else:
                cur.execute(
                    """
                    SELECT p.*,
                           u.nombre_display AS pedidor_nombre,
                           s.nombre AS sector_nombre,
                           b.nombre AS base_nombre,
                           c.ultimo_precio AS precio_referencia,
                           c.descripcion AS descripcion_catalogo
                    FROM pedidos p
                    JOIN usuarios u ON u.id = p.pedidor_id
                    JOIN sectores s ON s.id = p.sector_id
                    JOIN bases b ON b.id = p.base_id
                    LEFT JOIN catalogo c ON c.id = p.catalogo_id
                    WHERE p.sector_id = %s
                      AND p.base_id = ANY(%s)
                      AND p.estado = 'PENDIENTE'
                      AND p.pedidor_id != %s
                    ORDER BY p.creado_en ASC
                    """,
                    (user["sector_id"], user["bases"] or [], user["id"]),
                )
            return cur.fetchall()
    finally:
        conn.close()


def _resolver_pedido(pedido_id: int, autorizador: dict, decision: str, comentario: Optional[str], precio_ref: Optional[float]) -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sector_id, estado, pedidor_id, catalogo_id FROM pedidos WHERE id = %s",
                (pedido_id,),
            )
            pedido = cur.fetchone()
            if not pedido:
                raise HTTPException(status_code=404, detail="Pedido no encontrado")
            if pedido["sector_id"] != autorizador["sector_id"]:
                raise HTTPException(status_code=403, detail="No podés autorizar pedidos de otro sector")
            if pedido["pedidor_id"] == autorizador["id"]:
                raise HTTPException(status_code=403, detail="No podés autorizar tu propio pedido")
            if pedido["estado"] != "PENDIENTE":
                raise HTTPException(status_code=409, detail="El pedido ya fue procesado")

            cur.execute(
                """
                INSERT INTO autorizaciones (pedido_id, autorizador_id, decision, comentario, precio_ref)
                VALUES (%s, %s, %s::pedido_estado, %s, %s)
                """,
                (pedido_id, autorizador["id"], decision, comentario, precio_ref),
            )
            cur.execute(
                "UPDATE pedidos SET estado = %s::pedido_estado, actualizado_en = NOW() WHERE id = %s",
                (decision, pedido_id),
            )
            # Si se autorizó con precio y el pedido viene del catálogo, actualizar precio de referencia
            if decision == "AUTORIZADO" and precio_ref and pedido["catalogo_id"]:
                cur.execute(
                    "UPDATE catalogo SET ultimo_precio = %s, ultima_compra = CURRENT_DATE WHERE id = %s",
                    (precio_ref, pedido["catalogo_id"]),
                )
            conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.get("/pendientes", response_class=HTMLResponse)
async def pendientes(request: Request, user: dict = Depends(_require_autorizador)):
    pedidos = _get_pendientes(user)
    return templates.TemplateResponse(
        "modulo_b/pendientes.html",
        {"request": request, "user": user, "pedidos": pedidos},
    )


@router.post("/{pedido_id}/autorizar")
async def autorizar(
    pedido_id: int,
    request: Request,
    comentario: Optional[str] = Form(None),
    precio_ref: Optional[float] = Form(None),
    user: dict = Depends(_require_autorizador),
):
    try:
        _resolver_pedido(pedido_id, user, "AUTORIZADO", comentario, precio_ref)
    except HTTPException as e:
        flash(request, e.detail, "error")
    return RedirectResponse(url="/autorizaciones/pendientes", status_code=302)


@router.post("/{pedido_id}/rechazar")
async def rechazar(
    pedido_id: int,
    request: Request,
    comentario: Optional[str] = Form(None),
    precio_ref: Optional[float] = Form(None),
    user: dict = Depends(_require_autorizador),
):
    try:
        _resolver_pedido(pedido_id, user, "RECHAZADO", comentario, precio_ref)
    except HTTPException as e:
        flash(request, e.detail, "error")
    return RedirectResponse(url="/autorizaciones/pendientes", status_code=302)
