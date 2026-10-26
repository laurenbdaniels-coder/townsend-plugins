Fixture apps for the unused-parts warning (build-decisions 0.8.0, S-070): `seeded` has two parts nothing
uses, `fine` uses every part it lists (a script, a config, a stylesheet, a pair and a lockfile need), `nolock`
has no lockfile so the check stays quiet.
