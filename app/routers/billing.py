"""Payment pages (logged-in customers) and the Stripe webhook (called by Stripe)."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_user
from app.core.templates import flash
from app.db.session import get_db
from app.models.user import User
from app.services import billing

router = APIRouter()          # needs login + CSRF
webhook_router = APIRouter()  # public: Stripe cannot log in, so it is authenticated by signature


def _base(request: Request) -> str:
    return str(request.base_url).rstrip("/")

 
@router.post("/billing/checkout/")
def checkout(request: Request, user: User = Depends(require_user)):
    """Upgrade button: send the customer to the Stripe payment page."""
    if not settings.billing_enabled:
        flash(request, "Online payment is not set up.", "danger")
        return RedirectResponse("/accounts/settings/", status_code=303)
    try:
        url = billing.create_checkout_url(
            user,
            success_url=_base(request) + "/billing/success/?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=_base(request) + "/billing/cancel/",
        )
    except Exception as e:
        print(f"Stripe checkout failed: {e}")
        flash(request, "Could not start the payment. Please try again.", "danger")
        return RedirectResponse("/accounts/settings/", status_code=303)
    return RedirectResponse(url, status_code=303)


@router.get("/billing/success/")
def success(request: Request, session_id: str = "", user: User = Depends(require_user), db: Session = Depends(get_db)):
    """Stripe sends the customer back here after paying. We confirm with Stripe first."""
    try:
        session = billing.paid_session_for(user, session_id) if session_id else None
    except Exception as e:
        print(f"Stripe session check failed: {e}")
        session = None
    if session is None:
        flash(request, "We could not confirm your payment yet. If you were charged, it will appear shortly.", "danger")
        return RedirectResponse("/accounts/settings/", status_code=303)
    billing.activate_private(db, user, session.customer, session.subscription)
    flash(request, "Payment received. You are now on the Private plan, so you can get your own number.")
    return RedirectResponse("/phone-menu/", status_code=303)


@router.get("/billing/cancel/")
def cancel(request: Request, user: User = Depends(require_user)):
    flash(request, "Payment cancelled. You were not charged.", "danger")
    return RedirectResponse("/accounts/settings/", status_code=303)


@router.post("/billing/portal/")
def portal(request: Request, user: User = Depends(require_user)):
    """Manage card / cancel on Stripe's own page."""
    if not (settings.billing_enabled and user.stripe_customer_id):
        return RedirectResponse("/accounts/settings/", status_code=303)
    try:
        url = billing.portal_url(user.stripe_customer_id, _base(request) + "/accounts/settings/")
    except Exception as e:
        print(f"Stripe portal failed: {e}")
        flash(request, "Could not open the billing page. Please try again.", "danger")
        return RedirectResponse("/accounts/settings/", status_code=303)
    return RedirectResponse(url, status_code=303)


@webhook_router.post("/billing/webhook/")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe tells us about payments and cancellations. Anything unsigned is rejected."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        return Response(status_code=400)
    payload = await request.body()
    try:
        billing._stripe().Webhook.construct_event(
            payload, request.headers.get("stripe-signature", ""), settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception:
        return Response(status_code=400)

    # The signature is verified, so the payload can be read as plain JSON.
    event = json.loads(payload)
    kind, obj = event.get("type"), event.get("data", {}).get("object", {})

    if kind == "checkout.session.completed":
        uid = obj.get("client_reference_id")
        user = db.get(User, int(uid)) if uid and uid.isdigit() else None
        if user and obj.get("payment_status") in ("paid", "no_payment_required"):
            billing.activate_private(db, user, obj.get("customer"), obj.get("subscription"))
    elif kind == "customer.subscription.deleted":
        customer = obj.get("customer")
        user = db.query(User).filter(User.stripe_customer_id == customer).first() if customer else None
        if user:
            billing.deactivate_to_free(db, user)
    return Response(status_code=200)
