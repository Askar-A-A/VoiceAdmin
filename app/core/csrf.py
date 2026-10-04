"""CSRF protection for the server-rendered forms.

Django gave this for free; on FastAPI we add it ourselves. A random token
lives in the session; every state-changing form must echo it back (hidden
field or X-CSRF-Token header), and this dependency checks it.

Attached to the form-serving routers in main.py. The public telephony
webhooks (voice/ and the calls webhook) are NOT protected this way — they
come from CarrierX/providers and authenticate differently.
"""
import hmac

from fastapi import Request, HTTPException

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


async def verify_csrf(request: Request) -> None:
    if request.method in SAFE_METHODS:
        return

    session_token = request.session.get("csrf_token")
    sent = request.headers.get("x-csrf-token")
    if not sent:
        form = await request.form()
        sent = form.get("csrf_token")

    if not session_token or not sent or not hmac.compare_digest(str(sent), str(session_token)):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid.")
