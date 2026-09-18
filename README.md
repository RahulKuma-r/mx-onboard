# mx-onboard

Two skills, two hooks, two scripts. Makes a subsystem legible **to a person**.

## Why this exists

There is tooling that measures how legible a repo is to an *agent* — retrieval surface, an
instruction file, a verification contract. There is none that asks whether a human can learn it.

They are not the same target. An agent needs an index. A person needs a route: where to start,
what the words mean, and which three things will mislead them.

**And the value of a written explanation is not its coverage. It is its surprises.** A document
that lists every file and contains nothing a competent reader could not have found has told them
nothing. So that is the pass condition, and a hook enforces it.

## The two skills

| | Use when | Produces |
|---|---|---|
| **`/explain`** | Someone has to understand a subsystem they did not write | A document with a route, a vocabulary, the surprises, and five files in reading order |
| **`/verify-doc`** | A document might have gone stale | A per-claim verdict — still true, moved, gone, or not mechanically checkable |

They are two halves of one job. `/explain` writes; `/verify-doc` stops what was written from
quietly rotting.

## And the hook that closes the loop

`/verify-doc` only runs when someone already suspects a document has gone stale. The problem is
that nobody suspects it — that is the whole nature of the failure.

So the drift hook watches edits. When one lands on a file a document describes, it says so:

```
mx-onboard: you just edited Connector/Services/EntityInputResolver.cs,
which onboarding docs describe:
  - docs/onboarding/connector.md (line 78)
If this change altered what those documents claim, run /verify-doc on them.
```

**It notifies. It does not block, and the difference is the design.**

`require_surprises` blocks, because an empty surprises section is definitely wrong and the fix is
entirely in the author's hands. Drift is a *maybe* — the edit may not touch what the document
claims. Blocking every edit to a documented file would train people to delete the documents,
which is the opposite of the point.

## The rule that carries the weight

**Never report "unverifiable" as "fine."**

Most interesting claims are behavioural, and no script settles those. `claims.py` resolves what
is mechanical — does the path exist, does the file still have that line, does the identifier
appear anywhere — and stops. What it cannot settle, it marks, and a human reads.

A checker that rounds "I could not tell" up to "correct" is worse than no checker, because the
staleness is now certified.

## Install

```bash
/plugin marketplace add ~/.claude/mx-onboard
/plugin install mx-onboard
```

The hook wires itself through `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}` — no
`settings.json` edit.

## Layout

```
mx-onboard/
├── .claude-plugin/{plugin,marketplace}.json
├── skills/explain/SKILL.md          route, vocabulary, surprises, reading order
├── skills/verify-doc/SKILL.md       per-claim verdicts
├── hooks/hooks.json
├── hooks/require_surprises.py       blocks a document with no surprises
├── hooks/doc_drift.py               notifies when an edit lands on a documented file
├── scripts/claims.py                the mechanical half of verify-doc
├── scripts/doc_index.py             which documents cite which source files
└── tests/                           63 across three suites
```

## Running the tests

```bash
python tests/test_claims.py            # 36  extraction, verification, and the false positives
python tests/test_require_surprises.py # 11  deny cases and, as importantly, allow cases
python tests/test_doc_drift.py         # 16  the index, and the self-gating that keeps it quiet
```

Most of them exist because the tool gave a confident wrong answer about a real document and that
answer became a test.

## Composes with

- **`repo-mapper`** — `/explain` calls it for ownership questions rather than re-deriving them.
- **`mx-integrators-method`** — that package covers ticket-to-merge, forward. This covers
  understanding something that already exists. `/score` measures agent-legibility; this is the
  human half, and it is not scored, because a rubric for whether a person learned something is a
  different and harder thing.

## What this is not

It does not teach. A document is not a lesson — a lesson is ordered by difficulty, a document by
structure. That is a real gap and a possible second version, not something this quietly does
badly.

It also does not keep documents up to date. `/verify-doc` reports; the fixing is a decision a
person makes, because a document worth auto-fixing was probably not worth writing.
