from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional

from app.auth.dependencies import require_role
from app.database import get_connection
from app.flash import flash
from app.masterbus import sync_catalogo
from app.templates_env import templates

router = APIRouter()

_require_comprador = require_role("COMPRADOR")


def _list_catalogo(busqueda: Optional[str] = None, solo_activos: bool = False) -> list:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            filtros = []
            params: list = []
            if busqueda:
                filtros.append("(LOWER(descripcion) LIKE %s OR LOWER(codigo) LIKE %s)")
                like = f"%{busqueda.lower()}%"
                params += [like, like]
            if solo_activos:
                filtros.append("activo = TRUE")
            where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
            cur.execute(
                f"SELECT * FROM catalogo {where} ORDER BY descripcion",
                params,
            )
            return cur.fetchall()
    finally:
        conn.close()


def _get_item(item_id: int) -> dict:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM catalogo WHERE id = %s", (item_id,))
            item = cur.fetchone()
            if not item:
                raise HTTPException(status_code=404, detail="Artículo no encontrado")
            return item
    finally:
        conn.close()


@router.get("/", response_class=HTMLResponse)
async def lista_catalogo(
    request: Request,
    busqueda: Optional[str] = None,
    mostrar_inactivos: Optional[str] = None,
    user: dict = Depends(_require_comprador),
):
    solo_activos = mostrar_inactivos != "1"
    items = _list_catalogo(busqueda, solo_activos)
    return templates.TemplateResponse(
        "modulo_c/catalogo.html",
        {
            "request": request,
            "user": user,
            "items": items,
            "busqueda": busqueda or "",
            "mostrar_inactivos": not solo_activos,
        },
    )


@router.get("/nuevo", response_class=HTMLResponse)
async def nuevo_item_form(request: Request, user: dict = Depends(_require_comprador)):
    return templates.TemplateResponse(
        "modulo_c/catalogo_form.html",
        {"request": request, "user": user, "item": None, "modo": "nuevo"},
    )


@router.post("/nuevo")
async def nuevo_item_submit(
    request: Request,
    codigo: Optional[str] = Form(None),
    descripcion: str = Form(...),
    unidad_defecto: Optional[str] = Form(None),
    ultimo_precio: Optional[float] = Form(None),
    user: dict = Depends(_require_comprador),
):
    codigo_limpio = codigo.strip().upper() if codigo and codigo.strip() else None
    redirect_url = "/catalogo/"
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if codigo_limpio:
                cur.execute("SELECT id FROM catalogo WHERE codigo = %s", (codigo_limpio,))
                if cur.fetchone():
                    flash(request, f"Ya existe un artículo con código '{codigo_limpio}'", "error")
                    redirect_url = "/catalogo/nuevo"
                    return RedirectResponse(url=redirect_url, status_code=302)
            cur.execute(
                """
                INSERT INTO catalogo (codigo, descripcion, unidad_defecto, ultimo_precio)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    codigo_limpio,
                    descripcion.strip(),
                    unidad_defecto.strip() if unidad_defecto and unidad_defecto.strip() else None,
                    ultimo_precio,
                ),
            )
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/{item_id}/editar", response_class=HTMLResponse)
async def editar_item_form(
    item_id: int, request: Request, user: dict = Depends(_require_comprador)
):
    item = _get_item(item_id)
    return templates.TemplateResponse(
        "modulo_c/catalogo_form.html",
        {"request": request, "user": user, "item": item, "modo": "editar"},
    )


@router.post("/{item_id}/editar")
async def editar_item_submit(
    item_id: int,
    request: Request,
    codigo: Optional[str] = Form(None),
    descripcion: str = Form(...),
    unidad_defecto: Optional[str] = Form(None),
    ultimo_precio: Optional[float] = Form(None),
    user: dict = Depends(_require_comprador),
):
    codigo_limpio = codigo.strip().upper() if codigo and codigo.strip() else None
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            if codigo_limpio:
                cur.execute(
                    "SELECT id FROM catalogo WHERE codigo = %s AND id != %s",
                    (codigo_limpio, item_id),
                )
                if cur.fetchone():
                    flash(request, f"Ya existe otro artículo con código '{codigo_limpio}'", "error")
                    return RedirectResponse(url=f"/catalogo/{item_id}/editar", status_code=302)
            cur.execute(
                """
                UPDATE catalogo
                SET codigo = %s, descripcion = %s, unidad_defecto = %s, ultimo_precio = %s
                WHERE id = %s
                """,
                (
                    codigo_limpio,
                    descripcion.strip(),
                    unidad_defecto.strip() if unidad_defecto and unidad_defecto.strip() else None,
                    ultimo_precio,
                    item_id,
                ),
            )
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/catalogo/", status_code=302)


@router.post("/{item_id}/desactivar")
async def desactivar_item(item_id: int, user: dict = Depends(_require_comprador)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE catalogo SET activo = FALSE WHERE id = %s", (item_id,))
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/catalogo/", status_code=302)


@router.post("/{item_id}/activar")
async def activar_item(item_id: int, user: dict = Depends(_require_comprador)):
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE catalogo SET activo = TRUE WHERE id = %s", (item_id,))
            conn.commit()
    finally:
        conn.close()
    return RedirectResponse(url="/catalogo/?mostrar_inactivos=1", status_code=302)


@router.post("/sync")
async def sync_desde_masterbus(_: dict = Depends(_require_comprador)):
    resultado = sync_catalogo()
    return RedirectResponse(
        url=f"/catalogo/?sync_ok={resultado['total']}",
        status_code=302,
    )
