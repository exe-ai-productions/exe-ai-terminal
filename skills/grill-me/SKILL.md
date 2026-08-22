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

**Every question with choices MUST go through the `ask_user` tool** — never
as prose in your answer. Prose asking is not asking: it leaves the user
typing out what a click should have settled, and it does not stop the run
to wait for them. One question per call, at most two options, the one you
would recommend first and marked as recommended in its label. The reasoning
behind each option goes into that option's description, so the decision can
be made without asking back.

Only a question that genuinely cannot be put into options — a number, a
name, a free sentence — may be asked as plain text.

A question the project's own files can answer is not a question for the
user: look it up instead, and move on to the next one that is truly theirs.

Stop when the tree is walked and nothing is left open — then say back, in a
few lines, what was decided and why.
