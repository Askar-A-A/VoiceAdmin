import csv
import hmac
import io
from datetime import date

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user
from app.core.templates import templates
from app.db.session import get_db
from app.models.user import User
from app.models.ivr import IVRConfig
from app.models.calls import (
    Call, CallLog, normalize_phone_number, COMPLETED, MISSED, BUSY, CALL_STATUSES,
)
from app.schemas.calls import CallLogOut, CallStats, CallLogsPage, WebhookResult

router = APIRouter()

LOGS_PAGE_SIZE = 25
LOGS_ORDERING = {
    "created_at", "-created_at", "duration_seconds", "-duration_seconds", "status", "-status",
}


# --- recording calls --------------------------------------------------------

def log_call(db: Session, owner_id: int, to_number: str = "", from_number: str = "") -> None:
    """Called from the IVR webhook when a call is answered."""
    to_n = normalize_phone_number(to_number)
    from_n = normalize_phone_number(from_number)
    db.add(CallLog(target_phone_number=to_n, caller_phone_number=from_n))
    db.add(Call(owner_id=owner_id, to_number=to_n, from_number=from_n))
    db.commit()


_STATUS_ALIASES = {
    "completed": COMPLETED, "answered": COMPLETED, "in-progress": COMPLETED, "success": COMPLETED,
    "busy": BUSY,
    "no-answer": MISSED, "noanswer": MISSED, "not_answered": MISSED, "missed": MISSED,
    "failed": MISSED, "canceled": MISSED, "cancelled": MISSED,
}


# --- filtering / stats ------------------------------------------------------

def _parse_date(value: str | None):
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError:
        return None


def _conditions(params, restrict_to_number: str) -> list:
    conds = [CallLog.target_phone_number == restrict_to_number]
    df = _parse_date(params.get("date_from"))
    if df:
        conds.append(func.date(CallLog.created_at) >= df)
    dt = _parse_date(params.get("date_to"))
    if dt:
        conds.append(func.date(CallLog.created_at) <= dt)
    return conds


def build_stats(db: Session, params, restrict_to_number: str) -> dict:
    conds = _conditions(params, restrict_to_number)
    total = db.query(func.count(CallLog.id)).filter(*conds).scalar() or 0
    unique = db.query(func.count(func.distinct(CallLog.caller_phone_number))).filter(*conds).scalar() or 0
    missed = db.query(func.count(CallLog.id)).filter(*conds, CallLog.status == MISSED).scalar() or 0
    missed_pct = (missed / total * 100) if total else 0

    day = func.date(CallLog.created_at)
    daily_rows = (
        db.query(day.label("day"), func.count(CallLog.id))
        .filter(*conds).group_by(day).order_by(day).all()
    )
    daily = [
        {"date": row[0].isoformat() if hasattr(row[0], "isoformat") else str(row[0]), "count": row[1]}
        for row in daily_rows
    ]
    return {
        "total_calls": total,
        "unique_callers": unique,
        "missed_percentage": round(missed_pct, 1),
        "daily": daily,
    }


def _own_target_number(db: Session, user: User) -> str:
    config = db.query(IVRConfig).filter(IVRConfig.owner_id == user.id).first()
    if not config or not config.phone_number:
        return ""
    return normalize_phone_number(config.phone_number)


def _filtered_logs(db: Session, params, restrict_to_number: str):
    conds = _conditions(params, restrict_to_number)
    status = (params.get("status") or "").strip()
    if status in CALL_STATUSES:
        conds.append(CallLog.status == status)
    q = (params.get("q") or "").strip()
    if q:
        digits = normalize_phone_number(q)
        conds.append(or_(
            CallLog.target_phone_number.ilike(f"%{digits}%"),
            CallLog.caller_phone_number.ilike(f"%{digits}%"),
        ))
    ordering = params.get("ordering", "-created_at")
    if ordering not in LOGS_ORDERING:
        ordering = "-created_at"
    column = getattr(CallLog, ordering.lstrip("-"))
    query = db.query(CallLog).filter(*conds)
    return query.order_by(column.desc() if ordering.startswith("-") else column.asc())


def _format_duration(total_seconds: int) -> str:
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes}m {seconds}s" if minutes else f"{seconds}s"


# --- pages / API ------------------------------------------------------------

@router.get("/call-analytics/")
def call_analytics_dashboard(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return templates.TemplateResponse("calls/analytics.html", {
        "request": request, "user": user, "own_number": _own_target_number(db, user),
    })


@router.get("/api/calls/stats/", response_model=CallStats)
def api_calls_stats(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    return build_stats(db, request.query_params, _own_target_number(db, user))


@router.get("/api/calls/logs/", response_model=CallLogsPage)
def api_calls_logs(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    params = request.query_params
    query = _filtered_logs(db, params, _own_target_number(db, user))

    try:
        page_size = min(int(params.get("page_size", LOGS_PAGE_SIZE)), 100)
    except ValueError:
        page_size = LOGS_PAGE_SIZE
    page_size = max(page_size, 1)
    try:
        page = max(int(params.get("page", 1)), 1)
    except ValueError:
        page = 1

    count = query.count()
    num_pages = max((count + page_size - 1) // page_size, 1)
    page = min(page, num_pages)
    rows = query.offset((page - 1) * page_size).limit(page_size).all()

    return CallLogsPage(
        results=[CallLogOut.model_validate(log) for log in rows],
        count=count, page=page, num_pages=num_pages,
    )


@router.get("/api/calls/logs/export/")
def api_calls_logs_export(request: Request, user: User = Depends(require_user), db: Session = Depends(get_db)):
    query = _filtered_logs(db, request.query_params, _own_target_number(db, user))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "ID", "Target number", "Caller number", "Country", "City",
        "IP address", "Duration (s)", "Duration (min)", "Status", "Created at",
    ])
    for log in query.all():
        writer.writerow([
            log.id, log.target_phone_number, log.caller_phone_number,
            log.location_country, log.location_city, log.ip_address or "",
            log.duration_seconds, _format_duration(log.duration_seconds),
            log.status, log.created_at.isoformat(),
        ])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="call_logs.csv"'},
    )


@router.post("/api/webhooks/calls/", response_model=WebhookResult, status_code=201)
async def webhook_calls(request: Request, db: Session = Depends(get_db)):
    expected = settings.CALL_WEBHOOK_API_KEY
    provided = request.headers.get("X-Webhook-Key", "")
    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing webhook key.")

    form = {}
    try:
        form = dict(await request.form())
    except Exception:
        pass
    body_json = {}
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            body_json = await request.json()
        except Exception:
            body_json = {}

    def param(*names):
        for n in names:
            if n in form and str(form[n]).strip():
                return str(form[n]).strip()
            if n in request.query_params and request.query_params[n].strip():
                return request.query_params[n].strip()
            if isinstance(body_json, dict) and body_json.get(n) is not None:
                return str(body_json[n]).strip()
        return ""

    target = param("target_phone_number", "To", "to", "Called", "DNIS")
    caller = param("caller_phone_number", "From", "from", "Caller", "CallerID")
    if not target or not caller:
        raise HTTPException(status_code=400, detail="target and caller phone numbers are required.")

    raw_status = param("status", "CallStatus", "DialCallStatus").lower()
    status = _STATUS_ALIASES.get(raw_status, COMPLETED)
    try:
        duration = max(0, int(param("duration_seconds", "CallDuration", "DialCallDuration", "Duration")))
    except ValueError:
        duration = 0

    call_log = CallLog(
        target_phone_number=normalize_phone_number(target),
        caller_phone_number=normalize_phone_number(caller),
        location_country=param("location_country", "Country", "FromCountry"),
        location_city=param("location_city", "City", "FromCity"),
        ip_address=param("ip_address") or None,
        duration_seconds=duration,
        status=status,
    )
    db.add(call_log)
    db.commit()
    db.refresh(call_log)
    return WebhookResult(success=True, id=call_log.id)
