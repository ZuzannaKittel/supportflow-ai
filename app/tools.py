
from datetime import datetime, timezone
from uuid import uuid4

from app.data import (
    ORDERS,
    DELIVERIES,
    REFUND_REQUESTS,
    SUPPORT_TICKETS,
)


REFUND_WINDOW_DAYS = 30


def _get_order_or_error(order_id: str):
    order = ORDERS.get(order_id)

    if order is None:
        return None, {
            "success": False,
            "error": f"Order {order_id} was not found.",
        }

    return order, None


def get_order(order_id: str) -> dict:
    """Retrieve order information."""

    order, error = _get_order_or_error(order_id)

    if error:
        return error

    return {
        "success": True,
        "order": order,
    }


def track_delivery(order_id: str) -> dict:
    """Retrieve simulated delivery information."""

    order, error = _get_order_or_error(order_id)

    if error:
        return error

    delivery = DELIVERIES.get(order_id)

    if delivery is None:
        return {
            "success": False,
            "error": "Delivery information is unavailable.",
        }

    return {
        "success": True,
        "order_id": order_id,
        "tracking_number": order["tracking_number"],
        "delivery_status": delivery["status"],
        "current_location": delivery["location"],
        "carrier": delivery["carrier"],
        "estimated_delivery": order["estimated_delivery"],
    }


def check_refund_eligibility(order_id: str) -> dict:
    """Check whether an order qualifies for a refund request."""

    order, error = _get_order_or_error(order_id)

    if error:
        return error

    if order_id in REFUND_REQUESTS:
        return {
            "success": True,
            "eligible": False,
            "reason": "A refund request already exists for this order.",
            "existing_request": REFUND_REQUESTS[order_id],
        }

    if order["status"] != "delivered":
        return {
            "success": True,
            "eligible": False,
            "reason": "Only delivered orders qualify for refund requests.",
        }

    delivered_at = datetime.fromisoformat(order["delivered_at"])
    if delivered_at.tzinfo is None:
        delivered_at = delivered_at.replace(tzinfo=timezone.utc)

    age_days = (
        datetime.now(timezone.utc) - delivered_at
    ).total_seconds() / 86400

    if age_days > REFUND_WINDOW_DAYS:
        return {
            "success": True,
            "eligible": False,
            "reason": (
                f"The refund window of {REFUND_WINDOW_DAYS} days has expired."
            ),
            "days_since_delivery": round(age_days, 1),
        }

    return {
        "success": True,
        "eligible": True,
        "reason": "Order qualifies for a refund request.",
        "days_since_delivery": round(age_days, 1),
        "refund_window_days": REFUND_WINDOW_DAYS,
    }


def process_refund(order_id: str, reason: str) -> dict:
    """
    Create a simulated refund request.

    This does NOT initiate a real payment refund.
    Eligibility is independently checked inside this function.
    """

    if not reason or not reason.strip():
        return {
            "success": False,
            "error": "A refund reason is required.",
        }

    # Idempotency: repeated requests return the original record.
    if order_id in REFUND_REQUESTS:
        return {
            "success": True,
            "created": False,
            "message": "An existing refund request was returned.",
            "refund_request": REFUND_REQUESTS[order_id],
        }

    # Enforce eligibility even if the agent skips the eligibility tool.
    eligibility = check_refund_eligibility(order_id)

    if not eligibility.get("success") or not eligibility.get("eligible"):
        return {
            "success": False,
            "error": "Refund request rejected.",
            "eligibility": eligibility,
        }

    refund_request = {
        "request_id": f"REF-{uuid4().hex[:8].upper()}",
        "order_id": order_id,
        "reason": reason.strip(),
        "status": "submitted",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "payment_refunded": False,
    }

    REFUND_REQUESTS[order_id] = refund_request

    return {
        "success": True,
        "created": True,
        "message": "Simulated refund request successfully created.",
        "refund_request": refund_request,
    }


def escalate_to_human(
    reason: str,
    conversation_summary: str,
) -> dict:
    """Create a simulated human-support ticket."""

    if not reason or not reason.strip():
        return {
            "success": False,
            "error": "An escalation reason is required.",
        }

    if not conversation_summary or not conversation_summary.strip():
        return {
            "success": False,
            "error": "A conversation summary is required.",
        }

    ticket = {
        "ticket_id": f"TKT-{uuid4().hex[:8].upper()}",
        "reason": reason.strip(),
        "conversation_summary": conversation_summary.strip(),
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    SUPPORT_TICKETS[ticket["ticket_id"]] = ticket

    return {
        "success": True,
        "escalated": True,
        "ticket": ticket,
    }
