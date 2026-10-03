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
