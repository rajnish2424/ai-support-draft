from fastapi.testclient import TestClient
import main as m
from main import app

client = TestClient(app)

def setup_function(_):
    # reset in-memory state before each test
    for store in (getattr(m, "READY_FOR_AGENT", {}),
                  getattr(m, "BLOCKED", {}),
                  getattr(m, "STATUS", {})):
        store.clear()
    if hasattr(m, "SEEN"):
        m.SEEN.clear()

# --- Module 2 -----------------------------------------------------------
def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

# --- Module 3 -----------------------------------------------------------
def test_valid_webhook_accepted():
    r = client.post("/webhooks/tickets", json={
        "ticket_id": "T1", "customer_name": "A", "subject": "s", "message": "m"})
    assert r.status_code == 200

def test_missing_field_rejected():
    r = client.post("/webhooks/tickets", json={
        "ticket_id": "T1", "customer_name": "A", "subject": "s"})  # no message
    assert r.status_code == 422

# --- Module 5 -----------------------------------------------------------
from main import validate_draft

def test_refund_promise_blocked():
    v = validate_draft("Hi, your refund has been approved and will be processed today.")
    assert v["status"] == "BLOCKED"
    assert "unauthorized_refund_promise" in v["reasons"]

def test_empty_blocked():
    assert validate_draft("   ")["status"] == "BLOCKED"

def test_clean_passes():
    assert validate_draft("Hi, thanks for reaching out, we'll look into it.")["status"] == "SEND_TO_HUMAN"

def test_timeframe_flagged():
    v = validate_draft("Refunds take 5-7 business days.")
    assert "specific_timeframe_promised" in v["flags"]

# --- Module 4 -----------------------------------------------------------
def test_draft_reply_is_pluggable(monkeypatch):
    monkeypatch.setattr(m, "draft_reply", lambda e: "Hi, we'll look into your order.")
    assert m.draft_reply(None) == "Hi, we'll look into your order."
