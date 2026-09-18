---
name: verify-doc
description: >-
  Use when a document might have gone stale — a README, an onboarding page, a Confluence export,
  a RESEARCH.md, an architecture note — and you need to know which parts are still true before
  anyone acts on them. Also before handing a document to someone new, and after a refactor that
  moved files. Triggers on: "is this doc still accurate", "check this README", "has this gone
  stale", "verify this documentation", "does this still match the code", "can I trust this page".
---

# verify-doc

Report which claims in a document are still true.

## The one idea

Documents do not announce that they have rotted. They read exactly the same on the day they stop
being true, which is why a stale document is more dangerous than a missing one — **a missing
document sends the reader to the code; a wrong one sends them somewhere confidently and
incorrectly.**

So the output is not a score. It is a list of claims with verdicts.

## The one thing this must never do

**Never report "unverifiable" as "fine."**

Most interesting claims are behavioural — *"the connector enriches the payload before it lands"* —
and no script settles that. The script resolves what is mechanical; you settle the rest by
reading; and what neither of you can establish stays marked unverified.

A checker that quietly rounds "I could not tell" up to "correct" has done worse than nothing,
because now the staleness is certified.

## How to run it

Mechanical pass first. Use this path exactly — do not go looking for the script:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/claims.py" <doc> --root . --json
```

Run it from the repo root. `--root .` is almost always right; pass something else only when the
document describes a different checkout.

Each claim comes back as one of:

| Status | Meaning |
|---|---|
| `ok` | The path, line, or identifier resolves today |
| `missing` | It does not exist anywhere in the repo |
| `moved` | Gone from the stated path, found elsewhere — `found_at` says where |
| `line_gone` | The file exists; it no longer has that line number |
| `unverifiable` | Nothing mechanical settles it — **your job, not the script's** |

Exit code `1` means at least one claim is stale.

Then, for every `unverifiable` claim, and for every prose statement the script never extracted:
read the code and decide. This is the part that takes the time and it is the part that matters.

## The report

```markdown
# Doc check: <path>

## Verdict
<Is this safe to hand to someone new? One sentence, answering yes or no.>

## No longer true
<Each with: the claim, the document line, and what is actually the case now.>

## Moved
<Claims that are still true but point at the old location.>

## Still true
<Count, plus anything worth noting. Do not list all of them.>

## Could not verify
<Claims nobody has settled, and what would settle each. This section is not
padding — it is the honest boundary of the check.>
```

## Rules

1. **Never mark a behavioural claim `ok` because the file it mentions exists.** The file existing
   and the file still doing that are different facts.
2. **Read the sentence before calling a `missing` claim stale.** A document that says *"there is
   no root `nuget.config`"* is confirmed by that file's absence, not contradicted by it. The
   script flags these with `negated_context` because it cannot tell which way a sentence points —
   you can.
3. **A `moved` claim is still stale.** The reader follows the path in the document, not the one in
   your report.
4. **Read the `unverifiable` ones.** Skipping them and reporting only the script's output is
   reporting a grep as a review.
5. **Give the verdict first.** The reader wants to know whether to trust the page, not to work it
   out from a table.
6. **Do not fix the document unless asked.** Report first. Rewriting a page while reporting on it
   destroys the thing being reported on.
7. **Count honestly.** "9 of 12 still true" is only true if you checked 12.

## When not to use this

A document you wrote in this session, or one with no claims about code in it — a decision record,
a meeting note. There is nothing to check against.
