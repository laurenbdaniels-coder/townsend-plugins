const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const router = require('express').Router();
router.post('/', (req, res) => {
  const event = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], process.env.REFUND_SECRET);
  res.json({ ok: event.id });
});
module.exports = router;
