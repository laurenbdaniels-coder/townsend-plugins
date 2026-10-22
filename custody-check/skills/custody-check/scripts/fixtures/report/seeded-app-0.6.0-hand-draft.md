# Custody check: seeded-app

**We found 2 problems in your code, and 4 things your code can't tell us.**
Why this matters: a stranger can reach what your app does not protect. That can be a key, someone else's record, or an admin button. Nothing on screen shows it until someone tries.
We read all 6 of your code files.

**Your app keeps personal data that carries extra risk.**
What it means for you: it stores government ID numbers and dates of birth, and your answers did not mention them. If this data leaks, the people it belongs to can be harmed, and laws on this data can apply to you.
Where: `prisma/schema.prisma:4`, `prisma/schema.prisma:5`

**Do today:** replace 2 secret keys with new ones. Treat the old ones as already stolen.

## What we found in your code

**1. Anyone who visits your site can see your secret keys.**
What it means for you: a stranger can copy them, run up your bills on paid services, and read your whole database.
Where: `src/components/Config.tsx:2`, `src/lib/supabaseAdmin.ts:2`

**2. Some of your data can be read without logging in.**
What it means for you: a stranger can read every user's profile and other people's notes.
Where: `supabase/migrations/001_init.sql:1`, `supabase/migrations/001_init.sql:2`

## What your code can't tell us
These are not problems we found. The code can't answer them, so they are still open.
- **Can a regular user do things only you should do,** like delete accounts or change prices?
- **What each user costs you,** and whether you have a spending cap.
- **Whether you'd hear about it if your app broke.**
- **Whether your app talks to an AI model.** Your app includes an AI library, so it might.

We also can't see your live site, your hosting and database dashboards, or settings stored outside your code. Not found does not mean it isn't there.

---
custody-check v0.6.0 · read-only · a review, not an audit
