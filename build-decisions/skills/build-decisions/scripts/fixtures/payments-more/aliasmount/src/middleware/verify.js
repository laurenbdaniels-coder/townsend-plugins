const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
module.exports = (req, res, next) => {
  req.event = stripe.webhooks.constructEvent(req.body, req.headers['stripe-signature'], process.env.STRIPE_WEBHOOK_SECRET);
  next();
};
