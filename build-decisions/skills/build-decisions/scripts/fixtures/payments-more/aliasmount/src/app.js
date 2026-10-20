require('module-alias/register');
const express = require('express');
const verifyStripe = require('@/middleware/verify');
const webhook = require('@/routes/webhook');
const app = express();
app.use('/webhook', express.raw({ type: 'application/json' }), verifyStripe, webhook);
app.listen(3002);
