# mx-onboard

Two skills, one hook, one script. Makes a subsystem legible **to a person**.

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
├── hooks/{hooks.json,require_surprises.py}
├── scripts/claims.py                the mechanical half of verify-doc
└── tests/                           30 across two suites
```

## Running the tests

```bash
python tests/test_claims.py            # 19  extraction, and what must NOT be extracted
python tests/test_require_surprises.py # 11  deny cases and, as importantly, allow cases
```

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
