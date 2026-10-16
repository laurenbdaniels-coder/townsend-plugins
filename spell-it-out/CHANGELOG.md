# Changelog

## 0.1.0 (2026-10-16)

- First release. Before a technical stop (a yes/no, choice or approval that turns on code, tools, data or deploys), Claude writes a short brief: the ask, where we are, if yes / if no, undo, my pick, not sure?, an optional one-minute check, and a TL;DR. Stops about taste, wording, people or dates stay plain questions.
- The safe answer always changes nothing or can be undone. An undo Claude hasn't checked counts as "can't undo". When only you know the answer (what your app stores, who uses it), Claude doesn't pick for you, and "Don't know" is fine. A reply that doesn't clearly pick an option gets asked again. When another skill gives the exact words of its questions, those words win.
