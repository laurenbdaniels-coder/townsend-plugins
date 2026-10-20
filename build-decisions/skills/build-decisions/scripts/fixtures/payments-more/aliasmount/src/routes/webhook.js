const router = require('express').Router();

router.post('/', (req, res) => {
  if (req.event.type === 'checkout.session.completed') {
    res.json({ received: true });
  }
});
module.exports = router;
