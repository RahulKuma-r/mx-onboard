# Installing mx-onboard

Two commands. Nothing to configure afterwards.

```bash
/plugin marketplace add <repo-url-or-path>
/plugin install mx-onboard
```

**Restart Claude Code.** Plugins load at session start, so nothing appears until you do.

Then check it took:

```
What mx-onboard skills do I have?
```

You should see `explain` and `verify-doc`.

---

## What you just installed

| | What it does |
|---|---|
| `/explain` | Writes an onboarding document for a subsystem — route, vocabulary, the surprises, five files in reading order |
| `/verify-doc` | Takes a document that already exists and reports which of its claims are still true |
| One hook | Blocks writing an onboarding document whose "What will surprise you" section is empty |
| One script | `claims.py` — the mechanical half of `verify-doc` |

The hook wires itself through `hooks/hooks.json` using `${CLAUDE_PLUGIN_ROOT}`. **It does not touch
your `settings.json`** — that file is yours, and its `permissions` block especially so.

---

## First run

Point it at a document you already distrust:

```
Use verify-doc on README.md and tell me which claims are no longer true.
```

That is the faster way to see whether this is useful to you. `/explain` takes a few minutes
because it actually reads the code; `/verify-doc` gives you a verdict in about one.

---

## Two things it deliberately will not do

**It will not fix a document.** `/verify-doc` reports and stops. Rewriting a page while reporting
on it destroys the thing being reported on, and a document worth auto-fixing was probably not
worth writing.

**It will not tell you a behavioural claim is fine because the file exists.** Most interesting
claims — *"the worker retries before it dead-letters"* — are not settled by any script. Those come
back marked unverified, and a person reads them. A checker that rounds "I could not tell" up to
"correct" is worse than no checker.

---

## Requirements

- **Python 3** on `PATH` as `python`. The script uses only the standard library — no pip install.
- Nothing else.

If `python` on your machine is `python3`, the hook and script still work when invoked directly;
only the `hooks.json` command word would need changing. Raise it and it will be fixed properly
rather than worked around.

---

## Running the tests

```bash
python tests/test_claims.py            # 36  extraction, verification, and the false positives
python tests/test_require_surprises.py # 11  deny cases and, as importantly, allow cases
```

Forty-seven. Most of them exist because the tool gave a confident wrong answer about a real
document and that answer became a test.

---

## Uninstalling

```bash
/plugin uninstall mx-onboard
```

The hook goes with it. Nothing is left behind in `settings.json`, because nothing was put there.

---

## If something is wrong

Two things are known and unsolved, so they are not bugs:

- **The hook runs after the write**, so a document with an empty surprises section lands on disk
  and is then flagged. A before-write hook would prevent it but would not cover edits.
- **The script cannot tell *"there is no `config.json`"* from *"there is a `config.json`"*.** Same
  words, opposite claims. It flags those sentences instead of ruling on them.

Anything else — especially a claim reported as stale that is actually fine — is worth reporting.
Every false positive found so far turned out to be a real bug, and each one is now a test.
