const express = require('express');
const webhook = require('./routes/webhook');
const refunds = require('./routes/refunds');
const app = express();
app.use('/api/webhook', express.json(), webhook);
app.use('/api/refunds', express.raw({ type: 'application/json' }), refunds);
app.listen(3001);
