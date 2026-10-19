Ground truth for the payment section (build-decisions 0.5.0). A Next + Supabase + Stripe app where the
payment handler and a thank-you page both save paid status, the handler has no signature check, screens
save credits and a total straight to the database, and a price is written in the app beside a Stripe
price id; plus labeled negatives. Expectations live in ../expected.json under sections.payment.

Review round 1 (0.5.0) added the layouts reviewers showed: handlers that check one or two imports away
(relative, `@/`, `@lib/`, bare `lib/`), an Express app that checks in middleware before the router, a FastAPI
app that checks in a module imported by absolute name, an edge function with a `_shared` helper, a Vercel
`api/lib` helper, handlers whose only "check" is an unrelated HMAC or sits in a block comment, and screens
that save an expense amount, a role, a trip plan, a project status or a payment extension's checkout request.
