const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
module.exports = function verifyStripe(req, res, next) {
  const sig = req.headers['stripe-signature'];
  try {
    req.event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);
    next();
  } catch (e) {
    res.status(400).send();
  }
};
