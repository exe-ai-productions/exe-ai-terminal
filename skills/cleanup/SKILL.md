---
description: Clears out a folder, but looks before it deletes
auto: true
---

Tidying a folder means deciding what may go, and that decision is not yours
to make silently.

First look: list the folder and read what is actually in it. Names lie —
`neu2.txt` can be the only copy of something that matters, and `backup/` can
be three years of nothing.

Then sort what you found into three groups and show them:

- **Rubbish** — what the system leaves behind and nobody wrote: `.DS_Store`,
  `Thumbs.db`, `__pycache__`, `node_modules`, build output that can be
  regenerated, empty folders.
- **Probably rubbish** — old attempts, duplicates, downloads that were opened
  once. Say why you think so.
- **Keep** — anything with content you cannot replace.

Delete the first group. Ask about the second, in one message with everything
in it, not one question per file. Never touch the third.

Two things that are not tidying up and need saying instead of doing: emptying
a folder because it looks messy, and deleting something you did not open.

What the user asked for in the same message wins over any of this. If they
said "just delete all of it", delete all of it and say what went.
