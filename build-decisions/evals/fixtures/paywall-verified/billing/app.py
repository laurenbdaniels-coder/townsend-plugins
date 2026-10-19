import os

import stripe
from flask import Flask, request

app = Flask(__name__)


@app.route("/stripe/events", methods=["POST"])
def stripe_events():
    event = stripe.Webhook.construct_event(request.data, request.headers.get("Stripe-Signature"), os.environ["STRIPE_WEBHOOK_SECRET"])
    if event["type"] == "invoice.paid":
        print("invoice paid", event["id"])
    return "", 200
