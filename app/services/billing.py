"""Stripe billing for the Private plan.

Flow: customer clicks Upgrade -> we create a Checkout Session -> Stripe hosts the
payment page -> on return we ask Stripe whether it was really paid (never trust
the redirect alone) -> plan becomes Private. A webhook handles what happens later
(cancelled subscription).

`stripe` is imported lazily, so the app still starts if the package or the keys
are missing (demo mode).
"""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ivr import IVRConfig
from app.models.user import User, PLAN_FREE, PLAN_PRIVATE
from app.services.numbers import release_number


def _stripe():
    import stripe

    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_url(user: User, success_url: str, cancel_url: str) -> str:
    """Stripe-hosted payment page for the Private plan (a subscription)."""
    stripe = _stripe()
    params = dict(
        mode="subscription",
        line_items=[{"price": settings.STRIPE_PRICE_ID, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(user.id),  # how we find the user again afterwards
    )
    if user.stripe_customer_id:
        params["customer"] = user.stripe_customer_id
    else:
        params["customer_email"] = user.email
    return stripe.checkout.Session.create(**params).url


def paid_session_for(user: User, session_id: str):
    """The checkout session if Stripe says it is paid and belongs to this user, else None."""
    session = _stripe().checkout.Session.retrieve(session_id)
    if session.client_reference_id != str(user.id):
        return None
    if session.status != "complete" or session.payment_status not in ("paid", "no_payment_required"):
        return None
    return session


def portal_url(customer_id: str, return_url: str) -> str:
    """Stripe page where the customer updates the card or cancels."""
    return _stripe().billing_portal.Session.create(customer=customer_id, return_url=return_url).url


def cancel_subscription(subscription_id: str) -> None:
    _stripe().Subscription.cancel(subscription_id)


def activate_private(db: Session, user: User, customer_id: str | None, subscription_id: str | None) -> None:
    """Idempotent: safe if both the success page and the webhook report the same payment."""
    user.plan = PLAN_PRIVATE
    if customer_id:
        user.stripe_customer_id = customer_id
    if subscription_id:
        user.stripe_subscription_id = subscription_id
    db.commit()


def deactivate_to_free(db: Session, user: User) -> None:
    """Back to Free: the private number returns to the pool."""
    config = db.query(IVRConfig).filter(IVRConfig.owner_id == user.id).first()
    if config:
        release_number(db, config)
    user.plan = PLAN_FREE
    user.stripe_subscription_id = None
    db.commit()
