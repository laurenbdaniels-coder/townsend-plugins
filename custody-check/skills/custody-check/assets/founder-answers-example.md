# Founder answers block

Paste a block like this in the chat (or in a file the agent can read) to answer the questions the scanner and your code cannot. Any line you leave out is asked one at a time, unless your code already answered it. Questions the code should answer (q1 to q4) are never asked; you may still answer them here. Values are `yes`, `no`, or `dont-know`, then an optional dash and a note.

```
Founder answers
q1: dont-know — I think the keys are on the server but I never checked the browser
q2: yes — the browser only calls my /api routes
q3: dont-know — never tried the logged-out test
q4: no — any logged-in user can hit the admin delete route
q5_code: yes — rolled back once on Vercel last month
q5_data: no — no backup configured yet
q6: yes — there is a preview deployment I use first
q7: no — I ship the summary, I don't read the diff
q8: dont-know — no idea what one user costs me
q9: no — I'd hear it from a user
q10: yes — email, name, and their notes; nothing else
q11: yes — code is on my laptop; I exported the data once
stores: emails, names, notes
users: about 40 people
next_change: add Stripe subscriptions
stop_line: none
```

Field notes:

- `q5_code` and `q5_data` replace `q5:`; the report uses the lower of the two.
- `stores:` is free text: what the app keeps about people.
- `users:` is free text: who uses it and roughly how many.
- `next_change:` is the change you are about to make. The report has no tier; the check reads it only for stop-line words.
- `stop_line:` is comma-separated from `none`, `card-numbers`, `moves-money`, `health`, `sensitive`, `scale`.
- `card-numbers` means the app stores or handles card numbers or other card details itself. `moves-money` means it holds or moves money for other people (payouts, Connect, escrow, stored balances, wallets).
- Payments your payment company runs, like the Stripe subscriptions above (or its invoices and refunds), are not a stop-line item when that is all the app does with money.
- `payments` is the old word. The agent asks one question about it, or about any other money handling, and it still ticks the stop-line if the answer is unclear.
- You cannot turn a scanner `no`, or a `no` from your code, into a `yes`. Only a new run of the check, after the thing has changed, can change it.
