---
description: Grills the user about a plan until it holds up
auto: true
---

Question the user relentlessly about this plan or design until the two of
you share one understanding of it. Walk every branch of the decision tree
and resolve dependencies between decisions one at a time — a choice made
early often decides three questions further down, so take them in the order
they depend on each other.

One question at a time. Never a list.

Ask every question with the `ask_user` tool — never as plain prose. The
user should only have to choose, not type. One question per call, at most
two options, and the one you would recommend comes first, marked as
recommended in its label. The reasoning behind each option goes into that
option's description, so the decision can be made without asking back. Only
a question that genuinely cannot be put into options — a number, a name —
may come as free text.

A question that the project's own files can answer is not a question for
the user: look it up instead, and move on to the next one that is truly
theirs.

Stop when the tree is walked and nothing is left open — then say back, in a
few lines, what was decided and why.
