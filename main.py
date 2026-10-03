import os
import random
import re
import time
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()


class TicketEvent(BaseModel):
    ticket_id: str
    customer_name: str
    subject: str
    message: str


READY_FOR_AGENT, BLOCKED, STATUS, SEEN = {}, {}, {}, set()

HARD_RULES = {
    "empty_draft": lambda t: len(t.strip()) == 0,
    "exceeds_length_limit": lambda t: len(t) > 1500,
    "unauthorized_refund_promise": lambda t: (
        re.search(
            r"\brefund\b.{0,40}\b(approved|issued|processed|will be)\b",
            t,
            re.I | re.S,
        )
        or re.search(r"\b(will|we'll|you'll)\b.{0,25}\brefund", t, re.I | re.S)
    )
    is not None,
}

SOFT_FLAGS = {
    "specific_timeframe_promised": lambda t: re.search(
        r"\b\d+\s*(-\s*\d+\s*)?(business\s+)?(day|days|week|weeks|hour|hours)\b",
        t,
        re.I,
    )
    is not None,
    "unfilled_placeholder": lambda t: re.search(r"\[[^\]]+\]", t) is not None,
}


def validate_draft(draft: str):
    hard = [n for n, c in HARD_RULES.items() if c(draft)]
    if hard:
        return {"status": "BLOCKED", "reasons": hard}
    return {
        "status": "SEND_TO_HUMAN",
        "flags": [n for n, c in SOFT_FLAGS.items() if c(draft)],
    }


_POOL = [
    (
        "Hi {name}, thanks for reaching out. I'm sorry your refund hasn't"
        " arrived yet. I've asked our team to look into your order and someone"
        " will follow up shortly."
    ),
    (
        "Hi {name}, good news - your refund has been approved and will be"
        " processed today."
    ),
    "Hi {name}, refunds usually take 5-7 business days after processing.",
]


def draft_reply(event: TicketEvent) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=300,
            temperature=0.7,
            system=(
                "You are a support agent. Never promise refunds you can't keep."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Subject: {event.subject}\n\n{event.message}",
                }
            ],
        )
        return resp.content[0].text
    time.sleep(0.1)
    return random.choice(_POOL).format(name=event.customer_name)


def process_ticket(event: TicketEvent):
    draft = draft_reply(event)
    verdict = validate_draft(draft)
    if verdict["status"] == "BLOCKED":
        BLOCKED[event.ticket_id] = {"draft": draft, "reasons": verdict["reasons"]}
        STATUS[event.ticket_id] = "blocked"
    else:
        READY_FOR_AGENT[event.ticket_id] = {
            "draft": draft,
            "flags": verdict["flags"],
        }
        STATUS[event.ticket_id] = "ready_for_agent"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/tickets")
def receive_ticket(
    event: TicketEvent,
    background_tasks: BackgroundTasks,
    x_webhook_token: str | None = Header(default=None),
):
    if x_webhook_token != os.environ.get("WEBHOOK_TOKEN", "test-token"):
        raise HTTPException(status_code=401, detail="unauthorized webhook")

    if event.ticket_id in SEEN:
        return JSONResponse(
            status_code=200,
            content={
                "ticket_id": event.ticket_id,
                "status": "duplicate_ignored",
            },
        )

    SEEN.add(event.ticket_id)
    STATUS[event.ticket_id] = "processing"
    background_tasks.add_task(process_ticket, event)

    return JSONResponse(
        status_code=202,
        content={"ticket_id": event.ticket_id, "status": "accepted"},
    )


@app.get("/tickets/{ticket_id}")
def get_status(
    ticket_id: str, x_api_key: str | None = Header(default=None)
):
    if x_api_key != os.environ.get("AGENT_API_KEY", "test-key"):
        raise HTTPException(status_code=401, detail="unauthorized")

    return {
        "ticket_id": ticket_id,
        "status": STATUS.get(ticket_id, "unknown"),
        "result": READY_FOR_AGENT.get(ticket_id) or BLOCKED.get(ticket_id),
    }
