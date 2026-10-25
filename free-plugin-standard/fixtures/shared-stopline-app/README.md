# shared-stopline-app

A test app for `free-plugin-standard/agreement_test.py` (S-062). Both plugins read its two schema files and must
find the same extra-risk field names in the same files. Comments and quoted values that name a field must not count.
`public/signup.html` holds a browser form field named `bday`: only custody-check reads browser forms, so that is the
one listed difference.
