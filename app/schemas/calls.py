"""Pydantic schemas for the Call Analytics JSON API.

These give FastAPI typed, validated responses (and auto-generated /docs),
instead of returning bare dicts.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CallLogOut(BaseModel):
    # from_attributes lets us build this straight from a SQLAlchemy CallLog row.
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_phone_number: str
    caller_phone_number: str
    location_country: str
    location_city: str
    ip_address: str | None
    duration_seconds: int
    status: str
    created_at: datetime


class DailyPoint(BaseModel):
    date: str
    count: int


class CallStats(BaseModel):
    total_calls: int
    unique_callers: int
    missed_percentage: float
    daily: list[DailyPoint]


class CallLogsPage(BaseModel):
    results: list[CallLogOut]
    count: int
    page: int
    num_pages: int


class WebhookResult(BaseModel):
    success: bool
    id: int
