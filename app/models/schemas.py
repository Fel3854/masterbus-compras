from pydantic import BaseModel
from typing import Optional


class NuevoPedidoForm(BaseModel):
    tipo: str  # 'CATALOGADO' o 'LIBRE'
    catalogo_id: Optional[int] = None
    descripcion: Optional[str] = None
    numero_parte: Optional[str] = None
    cantidad: float
    unidad: str
    notas: Optional[str] = None


class AutorizarForm(BaseModel):
    comentario: Optional[str] = None
    precio_ref: Optional[float] = None
