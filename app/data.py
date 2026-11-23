
from datetime import datetime, timedelta, timezone
from uuid import uuid4


def utc_now():
    return datetime.now(timezone.utc)


def make_order(
    order_id: str,
    customer_name: str,
    email: str,
    items: list,
    status: str,
    days_ago: int,
    tracking_number: str,
    estimated_delivery_days: int = 0,
):
    reference_date = utc_now() - timedelta(days=days_ago)

    return {
        "order_id": order_id,
        "customer": {
            "name": customer_name,
            "email": email,
        },
        "items": items,
        "status": status,
        "ordered_at": (reference_date - timedelta(days=3)).isoformat(),
        "delivered_at": (
            reference_date.isoformat() if status == "delivered" else None
        ),
        "tracking_number": tracking_number,
        "estimated_delivery": (
            (utc_now() + timedelta(days=estimated_delivery_days)).date().isoformat()
            if status != "delivered"
            else None
        ),
    }


ORDERS = {
    "1042": make_order(
        order_id="1042",
        customer_name="Alex Morgan",
        email="alex@example.com",
        items=[
            {"name": "Wireless Headphones", "quantity": 1, "price": 89.99},
            {"name": "USB-C Cable", "quantity": 2, "price": 12.99},
        ],
        status="delivered",
        days_ago=7,
        tracking_number="SF1042001",
    ),
    "1043": make_order(
        order_id="1043",
        customer_name="Jamie Taylor",
        email="jamie@example.com",
        items=[
            {"name": "Mechanical Keyboard", "quantity": 1, "price": 129.99},
        ],
        status="delivered",
        days_ago=45,
        tracking_number="SF1043001",
    ),
    "1044": make_order(
        order_id="1044",
        customer_name="Sam Wilson",
        email="sam@example.com",
        items=[
            {"name": "Laptop Stand", "quantity": 1, "price": 49.99},
        ],
        status="in_transit",
        days_ago=2,
        tracking_number="SF1044001",
        estimated_delivery_days=2,
    ),
}

# Simulated delivery information
DELIVERIES = {
    "1042": {
        "status": "delivered",
        "location": "Front door",
        "carrier": "SwiftShip",
    },
    "1043": {
        "status": "delivered",
        "location": "Parcel locker",
        "carrier": "SwiftShip",
    },
    "1044": {
        "status": "in_transit",
        "location": "Regional distribution center",
        "carrier": "SwiftShip",
    },
}

# In-memory operation records
REFUND_REQUESTS = {}
SUPPORT_TICKETS = {}
