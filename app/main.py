from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.security import NotAuthenticated
from app.routers import accounts, dashboard, audio, ivr, voice, calls, voicemail

app = FastAPI(title="VoicePortal")

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.exception_handler(NotAuthenticated)
async def _redirect_to_login(request: Request, exc: NotAuthenticated):
    return RedirectResponse("/accounts/login/", status_code=303)


for module in (accounts, dashboard, audio, ivr, voice, calls, voicemail):
    app.include_router(module.router)


@app.get("/health")
def health():
    return {"status": "ok"}
