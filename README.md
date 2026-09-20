# mx-onboard

Three skills, three agents, two hooks, two scripts. Makes a subsystem legible **to a person**.

## Why this exists

There is tooling that measures how legible a repo is to an *agent* — retrieval surface, an
instruction file, a verification contract. There is none that asks whether a human can learn it.

They are not the same target. An agent needs an index. A person needs a route: where to start,
what the words mean, and which three things will mislead them.

**And the value of a written explanation is not its coverage. It is its surprises.** A document
that lists every file and contains nothing a competent reader could not have found has told them
nothing. So that is the pass condition, and a hook enforces it.

## The three skills

| | Use when | Produces |
|---|---|---|
| **`/explain`** | Someone has to understand a subsystem they did not write | A document with a route, a vocabulary, the surprises, and five files in reading order |
| **`/verify-doc`** | One document might have gone stale | A per-claim verdict — still true, moved, gone, or not mechanically checkable |
| **`/survey`** | You need the state of *all* the documentation | Every document audited in parallel, ranked by what goes wrong if it is trusted |

`/explain` writes. `/verify-doc` checks one page. `/survey` asks the question nobody asks: **of
everything we have written down, what is the most dangerous thing to believe today?**

## The three agents

Each is an agent for a reason that is about **context, not capability**.

| Agent | Sees | Never sees | Why isolated |
|---|---|---|---|
| **`tracer`** | The repository | — | Following a value through four services means reading twenty files. They stay in its context, not yours. |
| **`doc-auditor`** | **One** document + the repo | Any other document | Disjoint by construction, so `/survey` can dispatch one per document in a single message |
| **`doc-reviewer`** | A finished document + the repo | **The session that wrote it** | A reviewer that watched you reason agrees with you |

**None of them can write.** Their tool lists are `Read`, `Grep`, `Glob` — no `Write`, no `Edit`,
no `Bash`. Read-only is enforced by withholding the tools, not by asking in the prompt. A test
fails if that ever changes.

## The hook that closes the loop

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

Both hooks self-gate: a repository with no onboarding documents sees nothing.

## The rule that carries the weight

**Never report "unverifiable" as "fine."**

Most interesting claims are behavioural, and no script settles those. `claims.py` resolves what
is mechanical — does the path exist, does the file still have that line, does the identifier
appear anywhere — and stops. What it cannot settle, it marks, and a human reads.

A checker that rounds "I could not tell" up to "correct" is worse than no checker, because the
staleness is now certified.

## Install

See [INSTALL.md](INSTALL.md).

```bash
/plugin marketplace add <repo-url>
/plugin install mx-onboard
```

The hooks wire themselves through `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}` — no
`settings.json` edit.

## Layout

```
mx-onboard/
├── .claude-plugin/{plugin,marketplace}.json
├── skills/explain/SKILL.md          route, vocabulary, surprises, reading order
├── skills/verify-doc/SKILL.md       per-claim verdicts for one document
├── skills/survey/SKILL.md           every document, in parallel, ranked
├── agents/tracer.md                 ownership, with file:line evidence
├── agents/doc-auditor.md            one document, one strict verdict
├── agents/doc-reviewer.md           argues with a finished document
├── hooks/hooks.json
├── hooks/require_surprises.py       blocks a document with no surprises
├── hooks/doc_drift.py               notifies when an edit lands on a documented file
├── scripts/claims.py                the mechanical half of verify-doc
├── scripts/doc_index.py             which documents cite which source files
└── tests/                           78 across four suites
```

## Running the tests

```bash
python tests/test_claims.py            # 36  extraction, verification, and the false positives
python tests/test_require_surprises.py # 11  deny cases and, as importantly, allow cases
python tests/test_doc_drift.py         # 16  the index, and the self-gating that keeps it quiet
python tests/test_plugin.py            # 15  manifest, frontmatter, agent tool lists, README drift
```

Most of them exist because the tool gave a confident wrong answer about a real document and that
answer became a test.

## Composes with

**`mx-integrators-method`** covers ticket-to-merge — forward, when you already know what you are
building. This covers understanding something that already exists. `/score` there measures
agent-legibility; this is the human half, and it is deliberately not scored, because a rubric for
whether a person learned something is a different and harder problem.

## What this is not

**It does not teach.** A document is ordered by structure; a lesson is ordered by difficulty.
That is a real gap and a possible next version, not something this quietly does badly.

**It does not keep documents up to date.** `/verify-doc` and `/survey` report; the fixing is a
decision a person makes, because a document worth auto-fixing was probably not worth writing.
