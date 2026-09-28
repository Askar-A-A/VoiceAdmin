"""CarrierX storage + phone-number (DID) API helpers.

Ported verbatim from the Django project — these are plain `requests` calls,
so nothing framework-specific changes.
"""
import json

import requests

from app.core.config import settings

STORAGE_FILES = "https://api.carrierx.com/core/v2/storage/files"
DIDS = "https://api.carrierx.com/core/v2/phonenumber/dids"


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {settings.CARRIERX_ACCESS_TOKEN}"}


def upload_to_carrierx(file_obj, filename: str) -> str | None:
    file_object_meta = {
        "container_sid": settings.CARRIERX_CONTAINER_SID,
        "name": filename,
        "type": "audio",
    }
    files = {
        "file_object": (None, json.dumps(file_object_meta), "application/json"),
        "data": (filename, file_obj, "audio/mpeg"),
    }
    response = requests.post(STORAGE_FILES, headers=_auth_headers(), files=files, timeout=300)
    if response.status_code in (200, 201):
        return response.json().get("file_sid")
    return None


def stream_from_carrierx(file_sid: str) -> requests.Response:
    return requests.get(
        f"{STORAGE_FILES}/{file_sid}/data",
        headers=_auth_headers(),
        stream=True,
        timeout=30,
    )


def delete_from_carrierx(file_sid: str) -> bool:
    response = requests.delete(f"{STORAGE_FILES}/{file_sid}", headers=_auth_headers(), timeout=30)
    return response.status_code in (200, 204)


def list_phone_numbers() -> list[str]:
    """Phone numbers (DIDs) rented on the account; empty list on any failure."""
    try:
        response = requests.get(DIDS, headers=_auth_headers(), timeout=10)
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []

    data = response.json()
    items = data.get("items", []) if isinstance(data, dict) else data
    numbers = []
    for item in items:
        number = item.get("phonenumber") or item.get("did") or item.get("number")
        if number:
            numbers.append(number)
    return numbers
