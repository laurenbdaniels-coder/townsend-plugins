import stripe
from fastapi import Request, HTTPException


async def stripe_event(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    try:
        return stripe.Webhook.construct_event(payload, sig, SECRET)
    except Exception:
        raise HTTPException(400)
