"""
Order loading and business logic for the order status chatbot.

This module reads a CSV file on import to create a base in-memory representation
of orders. It exposes functions to retrieve orders (with any in-memory
overrides) and to cancel orders according to simple business rules.

The business rules are:
  - Only orders with status 'processing' can be cancelled.
  - Orders that are 'shipped' or already 'canceled' are not eligibile to cancel.

All IDs are treated as strings to preserve formatting and to avoid type
ambiguity. Cancellations are stored in the OVERRIDES dictionary for the
duration of the server process; no file writes occur.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Optional

from .models import Order, CancelOrderResult

# In-memory stores for orders and overrides
ORDERS: Dict[str, Order] = {}
OVERRIDES: Dict[str, str] = {}

# CSV file path relative to this module
CSV_PATH = Path(__file__).with_name("orders.csv")


def _load_orders() -> None:
    """Read the CSV and populate the ORDERS dictionary."""
    ORDERS.clear()
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Order CSV not found at {CSV_PATH}")
    with CSV_PATH.open(newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            order_id = row.get("order_id")
            status = row.get("status")
            item = row.get("item")
            if not order_id or not status or not item:
                continue
            oid = str(order_id)
            order = Order(order_id=oid, status=status, item=item)
            if oid not in ORDERS:
                ORDERS[oid] = order


def get_order(order_id: str) -> Optional[Order]:
    """Retrieve an order by ID, applying any in-memory status overrides."""
    oid = str(order_id)
    order = ORDERS.get(oid)
    if order is None:
        return None
    override = OVERRIDES.get(oid)
    if override is not None:
        return Order(order_id=oid, status=override, item=order.item)
    return order


def cancel_order(order_id: str) -> CancelOrderResult:
    """
    Attempt to cancel an order.

    Returns:
        CancelOrderResult reflecting success or failure.
    """
    order = get_order(order_id)
    if order is None:
        return CancelOrderResult(ok=False, reason="not_found", order=None)
    if order.status in {"shipped", "canceled"}:
        return CancelOrderResult(ok=False, reason="immutable_status", order=order)
    # Otherwise set override to canceled
    OVERRIDES[str(order_id)] = "canceled"
    updated = Order(order_id=str(order_id), status="canceled", item=order.item)
    return CancelOrderResult(ok=True, reason=None, order=updated)


# Load orders on import
_load_orders()
