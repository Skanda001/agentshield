"""
Test Autonomous Email Support Agent HITL Execution Loop
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Setup email-support-agent path
AGENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "email-support-agent"))
if AGENT_DIR not in sys.path:
    sys.path.insert(0, AGENT_DIR)

import run

def test_hitl_loop_execution():
    print("\n" + "=" * 60)
    print("TEST 5: Email Support Agent Closed-Loop Execution")
    print("=" * 60)

    # Mock approval from AgentShield
    mock_approved_task = {
        "id": "appr-test-12345",
        "tool": "get_customer_orders",
        "request_context": {
            "arguments": {"customer_id": 1008, "email": "customer@example.com"}
        },
        "decided_by": "security-operator",
        "decision_note": "Approved by supervisor after identity verification",
    }

    # Clean test state file
    test_state_file = os.path.join(AGENT_DIR, ".resolved_approvals.json")
    if os.path.exists(test_state_file):
        try:
            os.remove(test_state_file)
        except:
            pass

    # Mock urllib response for AgentShield GET /approvals?status=approved
    class MockResponse:
        def read(self):
            return json.dumps([mock_approved_task]).encode("utf-8")
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    with patch("urllib.request.urlopen", return_value=MockResponse()):
        with patch("agent.shield._default_client._ensure_token", return_value="mock-token-abc"):
            with patch("agent.tools.get_customer_orders", return_value={"orders": [{"id": 8211, "status": "shipped"}]}) as mock_tool:
                count = run.process_approved_hitl_tasks()
                print(f"Executed approved tasks: {count}")
                assert count == 1, f"Expected 1 task executed, got {count}"
                mock_tool.assert_called_once()
                print("  [PASS] Tool get_customer_orders executed with approval authorization!")

    # Verify duplicate prevention
    with patch("urllib.request.urlopen", return_value=MockResponse()):
        with patch("agent.shield._default_client._ensure_token", return_value="mock-token-abc"):
            count_repeat = run.process_approved_hitl_tasks()
            assert count_repeat == 0, "Duplicate execution prevention failed!"
            print("  [PASS] Duplicate execution successfully prevented by state tracker.")

    # Cleanup test state file
    if os.path.exists(test_state_file):
        try:
            os.remove(test_state_file)
        except:
            pass

    print("\nALL HITL LOOP TESTS PASSED! (100% OK)")

if __name__ == "__main__":
    test_hitl_loop_execution()
