const express = require('express');
const verifyStripe = require('./middleware/stripeWebhook');
const webhookRouter = require('./routes/webhook');
const db = require('./db');
const app = express();
app.use('/api/webhook', express.raw({ type: 'application/json' }), verifyStripe, webhookRouter);
app.listen(3000);
