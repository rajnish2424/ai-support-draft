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
