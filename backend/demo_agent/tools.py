"""Four demo tools, each protected by @shield.protect.

These mimic a customer-support agent's capabilities:
  - read_order      (safe)
  - read_customer   (sensitive — PII)
  - send_email      (external effect)
  - delete_customer (destructive)
"""
from shield import protect


# Simulated data — replace with real DB calls in a real deployment.
_ORDERS = {
    "8211": {"id": "8211", "status": "out_for_delivery", "eta": "today 6pm"},
    "8212": {"id": "8212", "status": "processing", "eta": "tomorrow"},
}

_CUSTOMERS = {
    "4821": {
        "id": "4821",
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "phone": "9876543210",
        "pan": "ABCDE1234F",
    },
}

_SENT_EMAILS = []


@protect(tool="read_order", resource_type="order")
def read_order(order_id: str) -> dict:
    """Read an order by ID."""
    key = str(order_id)
    return _ORDERS.get(key, {"id": key, "status": "not_found"})


@protect(tool="read_customer", resource_type="customer", data_classification="confidential")
def read_customer(customer_id: str) -> dict:
    """Read a customer record (contains PII)."""
    key = str(customer_id)
    return _CUSTOMERS.get(key, {"id": key, "error": "not_found"})


@protect(tool="send_email", resource_type="email", data_classification="confidential")
def send_email(to: str, body: str) -> dict:
    """Send an email. Externally visible action."""
    _SENT_EMAILS.append({"to": to, "body": body})
    return {"sent": True, "to": to, "length": len(body)}


@protect(tool="delete_customer", resource_type="customer")
def delete_customer(customer_id: str) -> dict:
    """Delete a customer record. Destructive and irreversible."""
    key = str(customer_id)
    if key in _CUSTOMERS:
        del _CUSTOMERS[key]
        return {"deleted": True, "id": key}
    return {"deleted": False, "id": key, "reason": "not_found"}


TOOL_REGISTRY = {
    "read_order": read_order,
    "read_customer": read_customer,
    "send_email": send_email,
    "delete_customer": delete_customer,
}