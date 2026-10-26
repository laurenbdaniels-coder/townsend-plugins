# Evidence phrases

Every "What we saw:" sentence is built only from this list. A helper picks the question, the type and the place; it writes no sentence. The main agent copies the phrase exactly and fills only `<path>:<line>` (and, for `q10`, one field word from the list below).

Shape, one place: `What we saw: <phrase> at `<path>:<line>`; <ending>`
Shape, two places of one question: `What we saw: <phrase 1> at `<p1>:<l1>`, and <phrase 2> at `<p2>:<l2>`; <ending>`
A2 has no line: `What we saw: AI instruction text is kept in `<path>`; <ending>`

| q | type | phrase | does the line hold this? |
|---|---|---|---|
| q5 | migration | database changes are kept as files | a migration file or folder of SQL changes |
| q5 | migrate-cmd | a command applies database changes | a script or code that runs migrations |
| q5 | dump | a script copies the database | a dump or backup command |
| q5 | export-job | a job exports the app's data | code that exports the whole app's data, every user's records; never one user's own download |
| q6 | local-db | a local copy of your database is set up | config that starts a separate local database (such as `supabase/config.toml` or a database service); never a tool config that points at the app's own database |
| q6 | non-live-env | a second environment is configured | staging/preview config or a second env template |
| q6 | preview-deploy | a job deploys changes somewhere other than the live site | a CI deploy without the production target |
| q7 | pr-check | an automatic check runs on each pull request | a workflow triggered by pull requests |
| q7 | codeowners | a file names who reviews changes | CODEOWNERS |
| q7 | pr-template | a pull-request template exists | a PR template |
| q7 | review-bot | a review bot comments on changes | a review-bot workflow or config |
| q8 | rate-limit | a limit on how often someone can send requests is set | a rate limiter on a route that calls the AI or another paid service; never on sign-in, sign-up or settings |
| q8 | usage-cap | a per-user or per-period usage limit is set | a daily, monthly or per-user limit on AI or other paid use |
| q8 | credit-check | the code checks a user's credits before work | a credit or balance check before a costly call |
| q8 | usage-log | the code records how much an AI reply used | token-usage read and stored or logged |
| q9 | error-sdk | error reporting starts | an error-reporting SDK init |
| q9 | health-route | a health page answers requests | a health or status route |
| q9 | scheduled-job | a scheduled job is set | a scheduled job of the running app (host cron config, a schedule in app code, or a workflow that checks the live app); never repo upkeep such as stale-issue, CodeQL, dependency or link-check jobs |
| q9 | alert-webhook | the code sends a message to an alert channel | a post to Slack/Discord/PagerDuty-style alerting |
| q10 | pii-column | a column holds <field> | a schema column |
| q10 | pii-write | the code saves <field> | code that writes the field to storage |
| q10 | pii-form | a form asks for <field> | a form input |
| q11 | db-client | the app connects to its database platform | a database or platform client created in code the running app uses; never a seed or one-off script |
| q11 | export-route | a part of your app gives users their data as a file | a download/export route |
| q11 | builder | the app is built on a builder platform | a builder platform file or library in use |
| a1 | route-limit | a time limit is set on a part of your app that calls the AI | maxDuration or similar on that route |
| a1 | call-timeout | a time limit is set on an AI request | a timeout or abort timer on the call |
| a1 | first-reply-timer | a time limit is set on the first part of an AI answer | a timer cleared when the first part arrives |
| a1 | user-cancel | the user can stop an AI request | an abort signal passed from the user |
| a2 | prompt-file | AI instruction text is kept in | a file whose text is sent to the model |
| a3 | call-site | the code builds and sends the AI request | the model call |
| a3 | call-settings | the code sets how the AI answers | temperature or similar passed to the call |
| a4 | eval | a script runs saved examples through the AI | an eval runner (not mocks, not ordinary tests) |
| a5 | catch | a failed AI request is caught | a catch around the model call |
| a5 | retry | a failed AI request is tried again | a retry around the model call |
| a5 | fallback | another model or a built-in answer is used when the AI fails | a fallback branch |
| a6 | model-named | the code names the AI model it asks for | a model id passed to the call |
| a6 | model-outside | the AI model's name is set outside your code | a model id read from an env variable |

`<field>` is one of: email addresses, phone numbers, names, home addresses, dates of birth, payment details, messages people wrote (chat or messages to people or the AI; never quiz or exam answers), locations, photos of people, health details, ID numbers. If no field fits exactly, there is no q10 finding.

**Where A1 to A6 and q8 `usage-log` may come from:** only code the running app uses. Never `scripts/`, `eval/`, `evals/`, spike or experiment files, seed files or tests, except `a4` `eval`, which is exactly an eval runner.

| q | ending |
|---|---|
| q5 | this does not show a backup you have restored |
| q6 | this does not show that changes go there before your live site |
| q7 | this does not show that a person reads each change |
| q8 | this does not show what each user costs, or a cap on your AI account |
| q9 | this does not show that a named person is told when something fails |
| q10 | this does not show why it is kept |
| q11 | this does not show that you have a full copy of your data |
| a1 | this does not show what users see when the limit is reached |
| a2 | this does not show which version gave each answer |
| a3 | this does not show that it matches what you tested |
| a4 | this does not show that your last change was checked with it |
| a5 | this does not show what users see when an answer is wrong |
| a6 | this does not show that the name always means the same model |
