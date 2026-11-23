
import pytest

from app.tools import (
    get_order,
    track_delivery,
    check_refund_eligibility,
    process_refund,
    escalate_to_human,
)
from app.data import REFUND_REQUESTS, SUPPORT_TICKETS


@pytest.fixture(autouse=True)
def clean_test_data():
    REFUND_REQUESTS.clear()
    SUPPORT_TICKETS.clear()
    yield
    REFUND_REQUESTS.clear()
    SUPPORT_TICKETS.clear()


def test_get_existing_order():
    result = get_order("1042")

    assert result["success"] is True
    assert result["order"] is not None
    assert result["order"]["order_id"] == "1042"


def test_get_nonexistent_order():
    result = get_order("9999")

    assert result["success"] is False
    assert "not found" in result["error"]


def test_track_delivery():
    result = track_delivery("1044")

    assert result["success"] is True
    assert result["delivery_status"] == "in_transit"
    assert result["current_location"] == "Regional distribution center"


def test_refund_eligibility():
    result = check_refund_eligibility("1042")

    assert result["success"] is True
    assert result["eligible"] is True


def test_process_refund_and_prevent_duplicates():
    first = process_refund("1042", "Item arrived damaged")
    second = process_refund("1042", "Item arrived damaged")

    assert first["success"] is True
    assert first["created"] is True
    assert first["refund_request"]["payment_refunded"] is False

    assert second["success"] is True
    assert second["created"] is False
    assert second["refund_request"]["request_id"] == first["refund_request"]["request_id"]


def test_escalate_to_human():
    result = escalate_to_human(
        "Suspected fraudulent activity",
        "Customer requested human assistance.",
    )

    assert result["success"] is True
    assert result["escalated"] is True
    assert result["ticket"]["status"] == "open"
