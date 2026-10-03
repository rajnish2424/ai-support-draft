from fastapi import FastAPI

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

from pydantic import BaseModel

class TicketEvent(BaseModel):
    ticket_id: str
    customer_name: str
    subject: str
    message: str

@app.post("/webhooks/tickets")
def receive_ticket(event: TicketEvent):
    return {"received": True, "ticket_id": event.ticket_id}

import re

def _refund_commit(t):
    return (re.search(r"\brefund\b.{0,40}\b(approved|issued|processed|will be)\b", t, re.I | re.S)
            or re.search(r"\b(will|we'll|you'll)\b.{0,25}\brefund", t, re.I | re.S)) is not None

HARD_RULES = {
    "empty_draft": lambda t: len(t.strip()) == 0,
    "exceeds_length_limit": lambda t: len(t) > 1500,
    "unauthorized_refund_promise": _refund_commit,
}
SOFT_FLAGS = {
    "specific_timeframe_promised": lambda t: re.search(r"\b\d+\s*(-\s*\d+\s*)?(business\s+)?(day|days|week|weeks|hour|hours)\b", t, re.I) is not None,
    "unfilled_placeholder": lambda t: re.search(r"\[[^\]]+\]", t) is not None,
}

def validate_draft(draft: str):
    hard = [n for n, c in HARD_RULES.items() if c(draft)]
    if hard:
        return {"status": "BLOCKED", "reasons": hard}
    return {"status": "SEND_TO_HUMAN", "flags": [n for n, c in SOFT_FLAGS.items() if c(draft)]}
