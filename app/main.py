from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.security import NotAuthenticated
from app.core.csrf import verify_csrf
from app.routers import accounts, dashboard, audio, ivr, voice, calls, voicemail

app = FastAPI(title="VoicePortal")

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated):
    return RedirectResponse("/accounts/login/", status_code=303)


# Routers with user-facing forms get CSRF protection.
csrf = [Depends(verify_csrf)]
app.include_router(accounts.router, dependencies=csrf)
app.include_router(audio.router, dependencies=csrf)
app.include_router(ivr.router, dependencies=csrf)
app.include_router(voicemail.router, dependencies=csrf)

# No CSRF: dashboard is read-only; voice/calls are public provider webhooks.
app.include_router(dashboard.router)
app.include_router(voice.router)
app.include_router(calls.router)


@app.get("/health")
def health():
    return {"status": "ok"}
