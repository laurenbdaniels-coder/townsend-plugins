const express = require('express');
const router = express.Router();

router.post('/', async (req, res) => {
  const event = req.body;
  if (event.type === 'checkout.session.completed') {
    res.json({ received: true });
  }
});
module.exports = router;
