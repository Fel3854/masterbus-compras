from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from app.auth.service import load_user_by_id


async def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    user = load_user_by_id(user_id)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=307, headers={"Location": "/login"})
    return user


def require_role(*roles: str):
    """Dependency factory: el usuario debe tener al menos uno de los roles dados."""
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        user_roles = set(user["roles"] or [])
        if not user_roles.intersection(roles):
            raise HTTPException(status_code=403, detail="Acceso denegado")
        return user
    return checker
