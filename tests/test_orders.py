from order_status_bot.models import Order
from order_status_bot.orders import ORDERS, cancel_order, get_order


def test_orders_loaded():
    # Ensure that orders are loaded from CSV
    assert ORDERS, "ORDERS dict should not be empty after load"
    # Check that known order exists
    assert "12345" in ORDERS
    order = get_order("12345")
    assert isinstance(order, Order)
    assert order.status == "shipped"


def test_cancel_processing_order():
    # Use a processing order
    order_id = "23456"
    order_before = get_order(order_id)
    assert order_before is not None
    assert order_before.status == "processing"
    # Cancel the order
    result = cancel_order(order_id)
    assert result.ok is True
    assert result.reason is None
    assert result.order is not None
    assert result.order.status == "canceled"
    # get_order should now reflect override
    order_after = get_order(order_id)
    assert order_after is not None
    assert order_after.status == "canceled"


def test_cancel_already_shipped_or_canceled():
    # Shipped order
    shipped = cancel_order("12345")
    assert shipped.ok is False
    assert shipped.reason == "immutable_status"
    # Cancel same order again
    cancel_order("23456")  # first cancel sets override
    again = cancel_order("23456")
    assert again.ok is False
    assert again.reason == "immutable_status"


def test_cancel_nonexistent_order():
    res = cancel_order("99999")
    assert res.ok is False
    assert res.reason == "not_found"
