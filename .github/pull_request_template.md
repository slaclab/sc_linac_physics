## What this changes

<!-- One or two sentences. What the reviewer needs to know before reading the diff. -->

## Operator-visible

<!--
Does this change what a user sees or how an application behaves by default?
New or reordered UI, changed defaults, renamed commands, altered PV usage,
different launch behavior, new required steps.

If yes: describe it in plain language an operator would understand. This text
becomes the #srf-software note when the release goes out.

If no: write "None."
-->

None.

## Scope

<!--
Target is under 400 changed lines excluding tests; hard stop around 800.
The "PR size" check comments the count on this PR automatically — no need to
work it out by hand.

If this is over target, say why it could not be split — "the phase framework
and its first phase are not independently testable" is a reason; "it grew"
is not.

If this is one of a planned series, say which part: "2 of 4".
-->

## Decisions worth recording

<!--
Did you choose between real alternatives? Reuse vs. reimplement, staged vs.
all-at-once rollout, deferring something, a schema shape you'll be stuck with.

Write the reasoning, not just the outcome. The code shows what was chosen; it
never shows what was rejected or why. Delete this section if nothing applies.
-->

## Learning reviewer

<!--
Tag anyone who should read this to learn the area, and say what to focus on.
They are not a required approver and should not be treated as one — this is
deliberate exposure, not a gate.

Example: "@hmarts9 — worth reading the phase base class to see how a phase
declares its prerequisites. No approval needed."
-->

## Testing

<!-- What you ran, and anything a reviewer should verify by hand. -->

- [ ] `pytest` passes
- [ ] Coverage still clears 80%
- [ ] Checked against simulation (`PYDM_DEFAULT_PROTOCOL=fake` / `sc-sim`) where applicable
