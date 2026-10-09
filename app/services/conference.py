"""CarrierX Conference v2 API.

Note: Conference v2 uses endpoint-specific HTTP Basic auth (login/password),
NOT the Bearer token the rest of CarrierX uses. CarrierX does NOT generate the
access codes — we create them and tell it which code maps to which role.
"""
import random

import requests
from requests.auth import HTTPBasicAuth

from app.core.config import settings

MEETING_ROOMS = "https://api.carrierx.com/conference/v2/meeting_rooms"


def _auth() -> HTTPBasicAuth:
    return HTTPBasicAuth(settings.CARRIERX_CONF_LOGIN, settings.CARRIERX_CONF_PASSWORD)


def _code() -> str:
    return f"{random.randint(0, 999999):06d}"


def create_meeting_room(name: str) -> dict | None:
    """Create a room with host/participant/listener codes.

    Returns {meeting_room_sid, host, participant, listener} or None on failure.
    """
    codes = {"host": _code(), "participant": _code(), "listener": _code()}
    payload = {
        "name": name,
        "access_codes": [{"role": role, "access_code": code} for role, code in codes.items()],
    }
    try:
        resp = requests.post(MEETING_ROOMS, json=payload, auth=_auth(), timeout=30)
    except requests.RequestException:
        return None
    if resp.status_code not in (200, 201):
        return None
    sid = resp.json().get("meeting_room_sid")
    if not sid:
        return None
    return {"meeting_room_sid": sid, **codes}


def delete_meeting_room(sid: str) -> bool:
    try:
        resp = requests.delete(f"{MEETING_ROOMS}/{sid}", auth=_auth(), timeout=30)
    except requests.RequestException:
        return False
    return resp.status_code in (200, 204)
