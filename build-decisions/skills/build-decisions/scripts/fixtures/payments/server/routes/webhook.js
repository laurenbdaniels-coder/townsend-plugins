const express = require('express');
const router = express.Router();
const db = require('../db');
router.post('/', async (req, res) => {
  const event = req.event;
  if (event.type === 'checkout.session.completed') {
    await db.user.update({ where: { id: event.data.object.client_reference_id }, data: { is_paid: true } });
  }
  res.json({ received: true });
});
module.exports = router;
