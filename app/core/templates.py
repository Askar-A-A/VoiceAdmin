
from fastapi import Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/templates")


def flash(request: Request, message: str, category: str = "success") -> None:
    """Stash a one-shot message in the session (shown on the next page)."""
    request.session.setdefault("_messages", []).append(
        {"message": message, "category": category}
    )


def get_flashed(request: Request) -> list[dict]:
    """Pop and return queued flash messages."""
    return request.session.pop("_messages", [])
