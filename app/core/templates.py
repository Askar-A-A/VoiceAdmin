import secrets

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.core.format import filesizeformat, fmt_dt
from app.models.ivr import MENU_TYPE_LABELS


def _inject_messages(request: Request) -> dict:
    """Make one-shot flash messages available to every rendered page."""
    try:
        messages = request.session.pop("_messages", [])
    except (AssertionError, AttributeError, KeyError):
        messages = []
    return {"messages": messages}


def _inject_csrf(request: Request) -> dict:
    """Ensure a CSRF token exists in the session and expose it to templates."""
    try:
        token = request.session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            request.session["csrf_token"] = token
    except (AssertionError, AttributeError):
        token = ""
    return {"csrf_token": token}


class _Templates(Jinja2Templates):
    """Accepts the legacy TemplateResponse(name, context) call style.

    Newer Starlette wants (request, name, context); the app is written the
    old way, so translate it here in one place.
    """

    def TemplateResponse(self, *args, **kwargs):
        if args and isinstance(args[0], str):
            name = args[0]
            context = args[1] if len(args) > 1 else kwargs.pop("context", {})
            request = context.get("request")
            return super().TemplateResponse(request, name, context, *args[2:], **kwargs)
        return super().TemplateResponse(*args, **kwargs)


templates = _Templates(
    directory="app/templates",
    context_processors=[_inject_messages, _inject_csrf],
)
templates.env.filters["filesizeformat"] = filesizeformat
templates.env.filters["fmt_dt"] = fmt_dt
templates.env.globals["menu_type_label"] = lambda t: MENU_TYPE_LABELS.get(t, t)


def flash(request: Request, message: str, category: str = "success") -> None:
    """Stash a one-shot message in the session (shown on the next page)."""
    request.session.setdefault("_messages", []).append(
        {"message": message, "category": category}
    )
