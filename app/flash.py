from fastapi import Request


def flash(request: Request, message: str, category: str = "info") -> None:
    flashes = request.session.setdefault("_flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["_flashes"] = flashes


def get_flashes(request: Request) -> list:
    flashes = request.session.get("_flashes", [])
    request.session["_flashes"] = []
    return flashes
