---
name: survey
description: >-
  Use when you need to know the state of a repository's documentation as a whole rather than one
  page at a time — before onboarding someone, after a release or a large refactor, when taking
  over a codebase, or when deciding which documents are worth fixing first. Audits every
  onboarding document in parallel and ranks them by how dangerous they are to trust. Triggers on:
  "are our docs still accurate", "audit the documentation", "which docs are stale", "what state
  is our documentation in", "check all the onboarding docs", "where should I start fixing docs".
---

# survey

Audit every onboarding document in a repository at once, and rank them.

## The one idea

`/verify-doc` answers *"is this page still true"* — but it only runs when someone already
suspects a page. Nobody suspects the page that is quietly wrong, which is exactly the page that
does harm.

So this asks the question nobody asks: **of everything we have written down, what is the most
dangerous thing to believe today?**

The output is a ranking, not a list. A document that is wrong in ways a reader would notice is a
nuisance. One that is wrong in a way a reader would *believe* is the problem, and it should be at
the top.

## Why this fans out

One audit per document, dispatched **in a single message**, so they run in parallel.

That is safe here for a structural reason, not an optimistic one: **each `doc-auditor` is given
exactly one document.** Two instances cannot reach each other's work, so there is no coordination
to get wrong. Disjoint by construction, not by instruction.

It is also the only way this finishes. Ten documents audited one after another is ten times the
wall-clock for no extra information.

## How to run it

### 1. Find the documents

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/doc_index.py" --root . --json
```

A document is anything carrying the `What will surprise you` heading, wherever it was filed. If
the index is empty, say so and stop — this repository has no onboarding documents, and that is
the finding.

### 2. Run the mechanical pass for each, before dispatching

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/claims.py" <doc> --root . --json
```

Do this yourself, once per document. It is deterministic and fast, and it keeps the agents
read-only — they get the results rather than the ability to run things.

### 3. Dispatch one `doc-auditor` per document, in one message

Cap at **twelve**. Past that, audit the twelve largest or most-cited and say plainly which ones
you did not cover. A survey that silently skipped half the repository is worse than one that
admits its edge.

Give each agent:
- its document path
- the repository root
- that document's mechanical results, verbatim

Each returns a five-key verdict.

### 4. Rank and report

## The report

```markdown
# Documentation survey: <repo>

## The one to fix first
<The single most dangerous document, and why that one — in two sentences.>

## Ranked

| Document | Verdict | Stale | What goes wrong if trusted |
|---|---|---|---|
<dangerous first, then stale, then trustworthy>

## Undocumented
<Subsystems with no onboarding document at all. Absence is a finding — and often a
bigger one than a stale page, because nobody is even aware of the gap.>

## Not covered
<Documents beyond the cap, or that failed to audit, and why.>
```

## Rules

1. **Rank by danger, not by count.** A document with one believable falsehood outranks one with
   nine obvious ones. The question is what a reader would *act on*.
2. **One agent per document, one message.** Dispatching them one at a time is the same work,
   serialised, for no gain.
3. **Never let a `risk` field through as a hedge.** "May cause confusion" is not an answer. If an
   agent returns one, say that verdict is unsupported rather than passing it on.
4. **Report the cap.** If you audited twelve of twenty, the report says twelve of twenty.
5. **Missing documents count.** A subsystem nobody wrote up does not appear in any index — go
   looking for it, and list it.
6. **Do not fix anything.** This is a survey. The fixing is a separate decision, and it is the
   reader's.

## When not to use this

A repository with one or two documents — just run `/verify-doc` on them. The fan-out earns its
complexity somewhere around four.
