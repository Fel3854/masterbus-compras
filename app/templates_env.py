from fastapi.templating import Jinja2Templates
from app.flash import get_flashes

templates = Jinja2Templates(directory="app/templates")
templates.env.globals["get_flashes"] = get_flashes
