
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load env vars
from pathlib import Path
from dotenv import load_dotenv

for candidate in [Path(".env"), Path("backend/.env")]:
    if candidate.exists():
        load_dotenv(candidate)

from shield import protect, ShieldBlocked, ShieldEscalated

print("=" * 65)
print("🛡️  TESTING AGENTSHIELD OPTION A (@protect decorator)")
print("=" * 65)

# 1. Define dummy tools representing an external agent
@protect(tool="read_order", resource_type="order")
def read_order(order_id: str):
    return {"order_id": order_id, "status": "Shipped", "item": "Noise-Cancelling Headphones"}

@protect(tool="get_customer", resource_type="customer", data_classification="restricted")
def get_customer(customer_id: int):
    return {"customer_id": customer_id, "name": "Rahul Verma", "aadhaar": "9876 5432 1098"}

@protect(tool="delete_customer", resource_type="customer")
def delete_customer(customer_id: int):
    return {"deleted": True, "customer_id": customer_id}

# 2. Test ALLOW
print("\n[1] Testing Safe Call (ALLOW): read_order(order_id='8211')...")
try:
    res = read_order(order_id="8211")
    print(f"  ✅ Execution Allowed: {res}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 3. Test BLOCK
print("\n[2] Testing Destructive Action (BLOCK): delete_customer(customer_id=1042)...")
try:
    res = delete_customer(customer_id=1042)
    print(f"  ⚠️ UNEXPECTED ALLOW: {res}")
except ShieldBlocked as e:
    print(f"  ⛔ Correctly BLOCKED: {e}")
except Exception as e:
    print(f"  ❌ Error: {e}")

# 4. Test HITL (Sensitive PII)
print("\n[3] Testing Sensitive PII (HITL): get_customer(customer_id=1008)...")
try:
    res = get_customer(customer_id=1008)
    print(f"  ⚠️ UNEXPECTED ALLOW: {res}")
except ShieldEscalated as e:
    print(f"  ⏸️  Correctly ESCALATED (HITL): {e}")
    print(f"     Approval ID: {e.approval_id} -> Check http://localhost:5173/app/approvals")
except Exception as e:
    print(f"  ❌ Error: {e}")

print("\n" + "=" * 65)
print("🎉 Verified! Now check the UI dashboard at: http://localhost:5173/app")
print("=" * 65)
