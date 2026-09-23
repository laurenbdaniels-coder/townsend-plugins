# The eleven questions

The handout's eleven gut-check questions, what counts as Yes / No / Don't know, which scanner checks feed each one, and the by-hand test you can run in about sixty seconds when the answer is Don't know. Every question also names the gate where it bites (the nine gates: Define, Audit, Plan, Plan review, Build, Verify, Diff review, Ship, Watch).

The scanner answers only what a file tree can prove. A scanner **no** is evidence of a real problem and is never softened. A scanner **yes** is an inference and renders at medium confidence. Everything else is Don't know until you answer it, and "Don't know" is the useful answer: it is the next thing to find out, not a failure.

## Q1. Where do my secrets live? None in the browser. (Audit)

- **No** when a key lives where the browser can see it: a value under a browser-exposed prefix (`NEXT_PUBLIC_`, `VITE_`, `REACT_APP_`, `EXPO_PUBLIC_`, `PUBLIC_`, `NUXT_PUBLIC_`, `GATSBY_`) that is a named key, a service-role JWT, or a token whose variable name contains SECRET or SERVICE_ROLE / SERVICE_KEY / SERVICE_TOKEN; a tracked `.env*` or `*.env` file in git (templates excluded; a committed `.env.test`/`.env.development`/`.env.vault` is evidence instead). When git cannot be read at all, `git-index-unread` says so and the scan is partial; a token in `.mcp.json`, any `mcp.json` or `mcp_config.json`; a named key or service-role JWT hardcoded in client code.
- **Yes** only from you: every secret is server-side, in an environment variable or a secrets manager, and `.env` is ignored by git.
- **Don't know** otherwise. Public-by-design values (Supabase anon key, `pk_live_`, `pk_test_`, `sb_publishable_`, Firebase web `apiKey`) are listed as evidence, never as a No.
- Scanner checks: `browser-prefix-*`, `client-*`, `tracked-env-file`, `mcp-token` (No); `tracked-env-file-nonprod` (a committed `.env.test`, `.env.development`, `.env.ci` or an encrypted `.env.vault`/`.env.enc` is evidence, not a No: scaffolds commit those on purpose), `placeholder-key-literal`, `test-path-key-literal` (never change the answer).
- **By hand (60 s):** open your deployed site, open the browser's developer tools, search the loaded sources and the network responses for `sk-`, `service_role`, `AKIA`, `ghp_`. Then run `git ls-files | grep -i env`. Anything found: rotate that key now, then move it server-side.

## Q2. Client or server? Anything the browser can see, a stranger can see. (Plan)

- **Yes** only from you: you can point at the line that separates what runs in the browser from what runs on your server, and every privileged call is on the server side of it.
- **No** only from you: the browser calls the database, the AI provider, or a third-party API directly with a privileged key.
- Scanner hints: `api-route-dir`, `framework-config` show that a server side exists; they prove nothing about what crosses the line.
- **By hand (60 s):** list the three most sensitive things your app does (charge, write to the database, call the model). For each, say out loud whether the browser or your server makes that call. If you cannot say, the answer is Don't know.

## Q3. Who can read this: logged out, the wrong user, the right user? Files too. (Audit)

- **No** when a table or bucket is open by construction: `disable row level security`, a policy `using (true)`, Firebase or Realtime Database rules that allow writes `if true` (`allow read, write: if true`, `".write": true`). A rule that only allows public reads (`allow read: if true`) is evidence, not a No: some collections are meant to be public.
- **Yes** only from you, after the boundary test below passes for the API, the database, and file storage.
- Scanner checks: `rls-disabled`, `policy-using-true`, `firebase-rules-open` (No); `policy-select-true` (a `for select using (true)` policy is public read by design, like a public Firebase read: evidence, the by-hand test decides), `policy-with-check-true`, `policy-to-anon`, `firebase-rules-public-read`, `storage-bucket-public` (evidence).
- **By hand (the boundary triad, 3 × 60 s):**
  1. **Logged out:** in a private window, request one record's URL or API endpoint directly. It should refuse.
  2. **Wrong user:** log in as user B and request a record that belongs to user A, by changing the id in the URL or the request. It should refuse. The UI hiding it does not count; the API must refuse.
  3. **Right user:** log in as user A and confirm the same request works.
  Then the **file-URL test:** take the URL of one uploaded file and open it in the private window. If it opens, files are public.
  This skill never collects your URL; you run these yourself.

## Q4. Who is allowed to do this? Logged in is not allowed. (Plan)

- **Yes** only from you: every write, delete, admin action, and payment action checks a role or ownership on the server, not just a session.
- **No** only from you: any logged-in user can perform an action meant for owners or admins.
- Scanner evidence: `auth-path`, `auth-dependency` show that auth code exists; they never change the answer.
- **By hand (60 s):** pick one admin or owner-only action. As an ordinary logged-in user, replay its request (copy it from the network tab, change nothing but the session). It should refuse.

## Q5. Can I get the code back in five minutes, and the data back from a restored backup? (Before build)

Two halves, scored separately; the verdict shows the lower one.

- **Code half.** Scanner **yes (medium)** when the repository has real history (a tag or ten or more commits), is not a shallow clone, and a deploy configuration exists (`vercel.json`, `netlify.toml`, `fly.toml`, `render.yaml`, `railway.json`, `Dockerfile`, `Procfile`, or a GitHub workflow). That proves a previous version exists and a redeploy path exists, not that you have rehearsed a rollback. **High** only from you, after you have rolled back once.
  - `git-not-a-repo`: the folder is not a git repository (a zip export, for example). Nothing to do here; answer from what your platform offers.
  - `git-unavailable`: git is not installed (on macOS, install the Command Line Tools). Answer by hand.
  - `git-timeout`: git did not answer in time; try again.
  - `git-subdir`: the app lives inside a larger repository; the history counts belong to the whole repository.
- **Data half.** Always Don't know until you answer `q5_data`: **yes** only if you have restored a backup into a non-live database and read a record from it; **no** if there is no backup; Don't know otherwise.
- **By hand (60 s + a rehearsal):** open your host's deployments page and find the previous build's "redeploy" or "promote" button. For data, open your database provider's backups page and check the newest backup's date. A deploy rollback does not undo a migration, a payment, or an email.

## Q6. Is there a copy that isn't the live one? (Ship)

- **Yes (medium)** from the scanner when two named environments are configured (`.env.staging` and `.env.production`, `netlify.toml [context.*]`, `wrangler.toml [env.*]`, `vercel.json` `production` / `preview`, `fly.<name>.toml`). That proves names, not a running staging site.
- **Yes (high)** from you: a non-live copy exists that you deploy to first.
- **No** only from you: every change goes straight to the live site.
- Scanner check: `env-name`.
- **By hand (60 s):** open your host's dashboard. Is there a second URL, a preview deployment, or a staging project? Have you ever opened it?

## Q7. What changed that I didn't ask for? Read the diff, not the summary. (Diff review)

- Never answered by the scanner. **Yes** only from you: on your last change you read the diff line by line and found nothing you did not ask for. **No**: you shipped the summary without reading the diff.
- **By hand (60 s):** run `git diff HEAD~1 --stat`, then open the two files you least expected to see in the list.

## Q8. What does one user cost me? A number or "I don't know". (Watch)

- **Yes** only from you, with a number: cost per user or per action, and a cap that stops spending.
- **No** only from you: no cap, and the bill is a surprise.
- Scanner hints: `ai-sdk-dependency`, `model-env-var`, `model-literal`, `spend-cap-word` show that a model is called and whether cap-shaped words appear; they never change the answer.
- **By hand (60 s):** open your AI provider's billing page and your host's usage page. Write down last month's total and divide by your user count. Then find the spend cap setting and set one.

## Q9. How would I find out it's broken? One real alert to a named person. (Watch)

- **Yes** only from you: a specific failure sends a message to a specific person, and you have seen that message once.
- **No** only from you: you would find out from a user.
- Scanner hints: `monitoring-dependency`, `sentry-config`, `health-route`, `cron-schedule` show that monitoring code exists; the alert is the question.
- **By hand (60 s):** break something on purpose in the non-live copy (rename an environment variable). Did anyone get a message? Put it back.

## Q10. What am I storing, and could I explain it out loud? (Define)

- **Yes** only from you: you can list every kind of personal data you store and why, in one breath.
- **No** only from you: you found fields you cannot explain.
- Scanner evidence: `pii-field`, `pii-form-input` list field names that look personal (email, phone, address, date of birth, government id, card). A field named `ssn`, `dob`, `medical`, `card_number`, or similar also raises the **stop-line**: get a person who does this for a living.
- **By hand (60 s):** open your schema or your database's table view and read the column names aloud to someone. Every hesitation is a Don't know.

## Q11. Can I export code and data and leave, and what did the platform default to? (Define)

- **Yes** only from you: you have the code on your own machine and you have exported the data once.
- **No** only from you: the platform holds the only copy of either.
- Scanner evidence: `builder-file`, `builder-dependency`, `builder-readme`, `container-config` name the platform; the defaults are the question.
- **By hand (60 s):** find the export or download button for both the code and the data. Click the data one and open the file.

# If AI drives part of your product: keeping it on rails

Ask these **only when the app calls a model**, and ask the founder that question rather than inferring it. The scanner's Q8 hints (`ai-sdk-dependency`, `model-env-var`, `model-literal`) are worth leading with, but they miss a plain HTTP call to a provider and they fire on an unused dependency or a model name in a comment. A model is not a library that does the same thing every time. It is a moving part inside the product, and these are the six ways it wanders off without anything turning red.

The eleven already cover the ones that are really software questions wearing an AI hat: rollback is Q5, the bill is Q8, would-you-notice-it-is-down is Q9, and who-can-read-this is Q1, Q3, Q4 and Q10. These six are what is left.

Two rules of thumb when you ask them. **The founder's own AI tool can run most of these tests** (it can search their project, print what their code actually sends, and find a model name faster than they can), so offer that phrasing first. And **every one ends with a fix**, not an observation: a founder who learns they are broken and is handed nothing puts the paper down.

## A1. How slow is too slow, and what happens then? (Plan)

Past a few seconds a user assumes it is broken and refreshes. Unless the server cancels the first call when the browser goes away, and most do not by default, you now pay for both. And because the model is not deterministic, the second answer is not even the same one.

- **Yes** only from you: you can say the number ("four seconds") and what the app does when it is exceeded (a timeout, a cached answer, a smaller model, or a waiting state that tells the user what is happening).
- **No** only from you: there is no timeout, so a stuck call to the provider leaves the user staring at a spinner.
- Scanner hints: `spend-cap-word` picks up `maxDuration` and its relatives; it shows a limit exists somewhere, never that it is the right one.
- **By hand (60 s):** use the slowest real path in your app and count out loud. Then turn your wifi off mid-request and watch what a user would see.
- **The fix, if it spins forever:** set a timeout and show a message when it trips. One line and one sentence of copy.

## A2. Where do your prompts live? (Diff review)

The same instruction pasted into three files and edited in place is the AI version of code with no source control. When an answer comes out wrong you cannot tell which wording caused it, and you cannot go back.

- **Yes** only from you: prompts live in one place, in version control.
- **No** only from you: the same instruction is copy-pasted in more than one place, or prompts are edited live in a dashboard and nothing ties the version to the answer it produced.
- Scanner hints: none that are decisive. A prompt is just a string, and the scanner will not read your app's instruction files by design.
- **By hand (60 s):** copy one distinctive sentence out of your main prompt and ask your AI tool: "find every place in this project that contains this sentence." More than one hit is your answer. No project it can search is also your answer.
- **The fix:** move the instruction to one file and import it everywhere else. Then, when you can, log which prompt version produced each answer, which is what makes "why did it say that?" answerable at all.

## A3. Is production running what you actually tested? (Verify)

The prompt you tried in the playground is not the prompt your code sends. Your code wraps it in other text, adds settings you never saw (including the creativity setting, temperature), and fills it with real user input you did not have in front of you.

- **Yes** only from you: you have seen the exact final text and settings one real request sent, and it matches what you evaluated.
- **No** only from you: you tuned it in a playground, shipped something your code assembles, and have never compared the two.
- Scanner hints: `model-literal` shows which model names appear in the code. Two different model names in two places is worth a look.
- **By hand (60 s):** ask your AI tool: "show me the exact final text and settings you send to the model for one request, printed in full, not summarised." Read it next to what you tested. People are usually surprised.
- **The fix:** whatever differs, make the tested version the shipped one. If you cannot tell them apart, that is the finding.
- *If you also train a model, this one has a name: training and serving skew. Without training, it is the same shape with a smaller blast radius, because only the input differs and the fix is a diff rather than a retrain.*

## A4. Did that change actually make it better? (Verify)

"It looked good" is one person being the green light. And if you kept editing the prompt until your saved examples passed, those examples stopped telling you anything: you were steering against them, a few bits at a time, which is what makes a test set stop being a test set.

- **Yes** only from you: a set of real inputs with a note on what a good answer looks like, run before and after a change, with a count you write down, and some of them you never edit the prompt against.
- **No** only from you: changes ship on a read-through of one or two outputs, or every example you have is one you tuned until it passed.
- **By hand (60 s):** open a document. Paste five real things users have typed into your app, and next to each, one line on what a good answer looks like. Next time you change the prompt, paste those five back in by hand and count how many still look right. Four out of five is your number. Keep two you never tune against.
- **The fix:** the document is the fix. Five examples in a doc beats nothing, and you can write it in the session.
- *Two honest caveats to say out loud. Five or ten examples is a smoke alarm, not a measurement: one flipped answer moves the number a long way, so it catches a disaster and nothing smaller. And because the model is not deterministic, running each example once measures the dice as well as the change.*
- *If you also train a model, the trained version of this is called overfitting the validation set. Their term "data leakage" means something narrower: information that will not be there at answer time getting into the input. You can have that too, and the common shape is an eval whose retrieved context already contains the answer.*

## A5. When the model is wrong, refuses, or is down, what does the user see? (Build)

It will be wrong. The question is only whether the wrongness has somewhere to go.

- **Yes** only from you: there is a defined path (a retry with a delay, a cached or default answer, a human to escalate to, or an honest error that says what to do next), and you have seen it happen.
- **No** only from you: the failure path is a spinner, a blank screen, or a made-up answer presented as fact.
- Scanner hints: none. A fallback is behaviour, not a file.
- **By hand (60 s):** no non-live copy? Turn your wifi off mid-request, which is a provider being down and costs you nothing. If you do have a non-live copy, put a wrong API key in it and use your own app as a user. Whatever you see is your fallback.
- **The fix:** whatever you saw, replace it with a sentence that tells the user what happened and what to do next. That is the smallest honest fallback and it takes minutes.
- *A bad key tests "down", and only its fastest form. The two you will actually meet are a rate limit or an overloaded provider, which needs a retry with a delay, and a call that times out halfway. "Wrong" no key can fake: write a confidently wrong answer into the response by hand and see where it goes.*

## A6. Is your model pinned, and is the provider about to move you? (Watch)

You changed nothing and the answers changed anyway. If the model name in your code carries no date or version, you are on whatever the provider ships today.

- **Yes** only from you: the model name names a specific version, you re-run the examples from A4 when you change it, and you know when that version is scheduled to go away.
- **No** only from you: the name has no version in it and nothing re-runs when the answers move.
- Scanner hints: `model-literal` shows which model names appear in the code; a name without a date or version is worth a look.
- **By hand (60 s):** find the model name in your code. No date or version means you are on today's. Better still, read the `model` field the provider sends back on one real response, which names what actually served rather than what you asked for.
- **The fix:** pin the version. It is a one-line edit, and then subscribe to your provider's deprecation notices.
- *A pin is a dated lease, not a freeze. Versions are retired on a schedule, so pinning buys you notice and a planned re-run rather than permanence. Pinning is straightforward on Anthropic and OpenAI, where dated names are the normal shape; on some other providers the stable names roll forward and you cannot pin the same way.*

## When your product moves and your examples do not

This is A4's twin and it belongs to whoever owns the product, not the model. You change your pricing, your policy or your copy, and the examples you check against still describe the old version.

Usually they start failing for the wrong reason, and the danger is that you "fix" the product back toward last quarter's answer. Sometimes they are loose enough to keep passing while measuring something you no longer sell. Either way they have stopped being evidence.

- **The fix:** update the examples in the same change that moves the product. It is a habit, not a tool.
- *People who train models meet this as concept drift, or plainly a stale eval set.*

## If you do train or fine-tune your own model

Most founders with a prototype do not, and everything above still applies to them, which is the point. If you do train, three of these have a training-shaped version, and each has its own test.

- **Skew (A3).** Find the two places your inputs are prepared, once for training and once for serving. If that is two separate pieces of code, assume they differ until you have checked.
- **Leakage (A4).** Open your training script and find the line where the data is split. If it shuffles data that has a time order, or if rows belonging to the same user or document land on both sides, that is your answer. Note that shuffling is not itself the problem: for rows that are genuinely independent of each other and of time, a random split is the correct choice rather than a shortcut.
- **Stale labels (A6's twin).** Find the date your labels were last reviewed. If you cannot find one, that is your answer.

## All check names

Every `check` the scanner can emit, by question. The skill accepts scanner output only when every check is on this list; `scan-summary` is the placeholder row for a question with zero hits. Effect: **no** flips the answer to no; **yes-part** contributes to a yes; **hint** and **evidence** never change the answer.

- **Q1:** `browser-prefix-anon-jwt` (evidence), `browser-prefix-authenticated-jwt` (evidence), `browser-prefix-named-key` (no), `browser-prefix-privileged-jwt` (no), `browser-prefix-public-key` (evidence), `browser-prefix-service-or-secret-name` (no), `browser-prefix-token-shaped` (evidence), `browser-prefix-unknown-role-jwt` (evidence), `client-anon-jwt` (evidence), `client-authenticated-jwt` (evidence), `client-key-literal` (no), `client-keyish-ident-token` (evidence), `client-privileged-jwt` (no), `client-secret-ident-token` (no), `client-secret-name-token` (no), `client-unknown-role-jwt` (evidence), `env-file-on-disk` (evidence), `git-index-unread` (evidence), `mcp-token` (no), `mcp-token-shaped` (evidence), `non-client-key-literal` (evidence), `placeholder-key-literal` (evidence), `scan-summary` (evidence), `server-path-key-literal` (evidence), `test-path-key-literal` (evidence), `tracked-env-file` (no), `tracked-env-file-nonprod` (evidence)
- **Q2:** `api-route-dir` (hint), `framework-config` (hint)
- **Q3:** `firebase-rules-open` (no), `firebase-rules-public-read` (evidence), `policy-altered-true` (evidence), `policy-select-true` (evidence), `policy-to-anon` (evidence), `policy-using-true` (no), `policy-with-check-true` (evidence), `rls-disabled` (no), `storage-bucket-public` (evidence), `storage-bucket-public-sql` (evidence)
- **Q4:** `auth-dependency` (evidence), `auth-path` (evidence)
- **Q5 (code half):** `backup-script` (evidence), `deploy-config` (yes-part), `git-config-not-vouched` (evidence), `git-history` (evidence), `git-not-a-repo` (evidence), `git-shallow` (evidence), `git-subdir` (evidence), `git-timeout` (evidence), `git-unavailable` (evidence), `migration-path` (evidence)
- **Q6:** `env-name` (yes-part)
- **Q8:** `ai-sdk-dependency` (hint), `model-env-var` (hint), `model-literal` (hint), `spend-cap-word` (hint)
- **Q9:** `cron-schedule` (hint), `health-route` (hint), `monitoring-dependency` (hint), `sentry-config` (hint)
- **Q10:** `pii-field` (evidence), `pii-form-input` (evidence)
- **Q11:** `builder-dependency` (evidence), `builder-file` (evidence), `builder-readme` (evidence), `container-config` (evidence)
