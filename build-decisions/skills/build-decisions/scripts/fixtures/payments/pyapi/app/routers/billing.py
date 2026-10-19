from fastapi import APIRouter, Depends
from app.deps import stripe_event

router = APIRouter()


@router.post("/webhooks/stripe")
async def webhook(event=Depends(stripe_event)):
    if event["type"] == "checkout.session.completed":
        await db.execute("UPDATE users SET is_paid = true WHERE id = :id")
    return {"ok": True}
