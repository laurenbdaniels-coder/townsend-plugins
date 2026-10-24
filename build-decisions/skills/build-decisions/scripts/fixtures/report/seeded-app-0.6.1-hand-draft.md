# Build decisions: cartwheel

**Your app has 4 rules that are written in more than one place.**

Why this matters: when you or your AI tool change one of these rules, the change may land in one place and miss the others. Then the copies stop agreeing, and your app does things you don't expect. A button shows but fails, two screens show different prices, or something breaks.
We read 9 of your 16 code files. Problems in the others can be missed.

**How your app is built:** This run found that your app runs some of its own code on a server. It saw this in `src/app/api/export/route.ts`, `src/app/api/projects/route.ts`. Anyone can send requests to that server code without using your screens.

**1. Who can see a project** (written in 2 places)
These places give different answers today.
- The server gives each person only the projects they own. `src/app/api/projects/route.ts:6`
- The project list shows projects you own, and also shared projects. `src/components/ProjectList.tsx:7`

What it means for you: a shared project shows for one person but not for another, or a private project shows for the wrong person.

**2. The monthly plan price** (written in 2 places)
- The pricing card shows the Monthly plan at $19 a month. `src/zz-pricing/PlanCard.tsx:1`
- Checkout charges its own copy of the monthly price. `src/zz-checkout/plan.ts:2`

What it means for you: your pricing page shows one price, and checkout charges another.

**3. Whether someone is a paying customer** (written in 2 places)
- Export works only when the person's plan is "pro". `src/app/api/export/route.ts:5`
- Reports open only when the person's subscription is active. `src/lib/access.ts:4`

What it means for you: a paying person can use reports but not export, or the other way round.

**4. How the order total rounds** (written in 2 places)
- The amount charged to the card rounds the order total to the cent. `src/lib/money.ts:3`
- The order screen rounds the total to two decimals in a separate way. `src/components/Total.tsx:2`

What it means for you: the total on screen and the amount charged can differ by one cent.

Not checked: database settings, dashboards, other projects, names this run does not know, and code it did not search. This version also does not check sign-in checks on server code, or library versions. Payment places are found from the files, not tested in the app. This version does not check whether payment messages really come from your payment company. It checks values the browser chooses only in your app's own server code, not in code that runs inside your database service. Not found does not mean it isn't there.
This run used no search tool, so it followed each rule by reading files only.

---
build-decisions v0.6.1 · read-only · a review, not an audit

Does this app do any of these? Store or handle card details itself. Hold or move money for other people. Keep health information, or children's or other sensitive personal data. Run at real scale, or under a contract that needs it to stay up. You can answer 'Don't know'. To skip this next time, start your request with: stop_line: none
