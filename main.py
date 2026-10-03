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

import os, time, random

_POOL = [
    "Hi {name}, thanks for reaching out. I'm sorry your refund hasn't arrived yet. "
    "I've asked our team to look into your order and someone will follow up shortly.",
    "Hi {name}, good news - your refund has been approved and will be processed today.",
    "Hi {name}, refunds usually take 5-7 business days after processing.",
]

def draft_reply(event: "TicketEvent") -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        from anthropic import Anthropic           # real SDK, only when a key exists
        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-5", max_tokens=300, temperature=0.7,
            system="You are a support agent. Never promise refunds you can't keep.",
            messages=[{"role": "user",
                       "content": f"Subject: {event.subject}\n\n{event.message}"}])
        return resp.content[0].text
    time.sleep(0.1)                                # mock: offline + free
    return random.choice(_POOL).format(name=event.customer_name)


