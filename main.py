import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.auth.router import router as auth_router
from app.routers.pedidos import router as pedidos_router
from app.routers.autorizaciones import router as autorizaciones_router
from app.routers.compras import router as compras_router
from app.routers.catalogo import router as catalogo_router

app = FastAPI(title="Sistema de Pedidos de Compra")

app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth_router)
app.include_router(pedidos_router, prefix="/pedidos")
app.include_router(autorizaciones_router, prefix="/autorizaciones")
app.include_router(compras_router, prefix="/compras")
app.include_router(catalogo_router, prefix="/catalogo")


@app.get("/")
async def root():
    return RedirectResponse(url="/login", status_code=302)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
