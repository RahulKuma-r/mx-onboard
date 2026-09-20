---
name: explain
description: >-
  Use when someone has to understand a subsystem they did not write — onboarding a new joiner,
  handing over a service, writing up a module nobody has documented, or answering "how does X
  actually work" in a way that outlives the conversation. Produces a document a person reads,
  not a structure dump. Triggers on: "explain this module", "document this service", "how does
  X work", "onboard someone onto", "write this up for the team", "nobody knows how this works",
  "I keep explaining this".
---

# explain

Write a subsystem explanation **for a person**.

## The one idea

Tooling already measures how legible a repo is **to an agent**. Nothing checks whether a human
can learn it.

Those are not the same target. An agent needs retrieval surface — file names, structure, an
index. A person needs a *route*: where to start, what the words mean, and which three things
will mislead them. A structure dump serves the first and fails the second.

**So the pass condition is not coverage. It is surprises.**

A document that lists every file and contains nothing that would surprise a competent reader has
told them what they could have found themselves. The value is the part they could not.

This is the same gate as `RESEARCH.md`'s *"What would surprise me"*, pointed at teaching instead
of investigating.

## What goes wrong without it

| Failure | What it looks like |
|---|---|
| Structure, not behaviour | "There are four services. Here are their folders." |
| Complete but unread | Forty pages nobody opens twice |
| Surprises omitted | The thing that actually trips people up is missing |
| Silently stale | Nobody knows which half is still true — use `/verify-doc` |
| Explains what it *is*, not how to *change* it | The reader still cannot make the first edit |

## Before writing anything

1. **Name the target and cite the evidence.** Which folder, service or flow — and the path that
   proves it. Several repos sit side by side; confirm before reading.
2. **Read. Do not skim structure.** Glob the layout, then grep for the domain term, then read the
   files where the behaviour actually lives. Tests often explain intent better than source.
3. **For any "who owns this data" question, dispatch the `tracer` agent.** It answers ownership
   with `file:line` evidence, it cannot edit anything, and — the reason it is an agent — the
   twenty files it reads stay in its context rather than filling yours. Do not re-derive
   ownership by hand.
4. **Write down the things that contradicted your expectations as you go.** They are the
   document. If you wait until the end you will have forgotten them.

## The document

Write to `docs/onboarding/<subsystem>.md` unless told otherwise.

```markdown
# <Subsystem>

## What it does
<One paragraph. Domain language, not code language. A reader who does not know the
codebase should understand the purpose. No file names in this section.>

## Vocabulary
<This team's words and what they actually mean. Include the ones that are misleading —
a name that suggests the wrong thing is worth more here than an obvious one.>

## The path
<The flow in execution order, with file:line. Follow the behaviour, not the folder tree.
Mark each hop as read or write where data is involved.>

## What will surprise you
<Facts that contradict what a competent reader would assume. Duplicated logic, a name
that means something else, an ordering that matters, a cache that never expires, a
field two services both write. If this section is empty, you have not understood the
subsystem yet — go back and read more.>

## Where to start
<Five files, in reading order, with one line each on why that one and why in that
position. This is the section people actually use.>

## What I could not determine
<Open questions, and what would answer them. "Not in this repo" is a real finding.>
```

## After the document is written, have it argued with

Dispatch the `doc-reviewer` agent on the finished file.

It sees the document and the repository and **not this conversation** — which is the point. A
reviewer that watched you reason will agree with you, because every conclusion already looks
earned. One that arrives cold can be surprised by the document, and being surprised is the job.

It will attack the surprises section hardest: *would a competent reader have assumed otherwise?*
A "surprise" anyone could find with one grep is a fact wearing the wrong label.

Report what it found. Fix what it got right. If it says a surprise is weak and it is right,
delete the surprise rather than defending it — a thin surprises section that is honest is worth
more than a padded one.

## Rules

1. **Never write the document from structure alone.** If you have not read the files where the
   behaviour lives, you are describing a folder tree.
2. **An empty "What will surprise you" blocks the write.** A hook enforces this. Do not remove
   the heading to get around it — that is working around the gate, not passing it.
3. **Every claim in "The path" carries a `file:line`.** A claim without one is a guess, and a
   guess in an onboarding document is worse than a gap, because the reader will trust it.
4. **Five files in "Where to start", not fifteen.** A reading list nobody finishes teaches
   nothing. If five will not do it, the subsystem needs splitting, and say so.
5. **Say what you could not determine.** The section is not an admission of failure; it is the
   part that stops the next person repeating your search.
6. **Write for someone who is competent but new.** Not a beginner, not the author. Assume they
   can read code and know nothing about this domain.
7. **If the user asks for Hinglish, write the prose in Hinglish** and keep code, identifiers,
   commands and file paths in English.

## When not to use this

A single file, a function, or a question answerable in two sentences. Answer it directly. This
skill produces a document, and a document nobody needed is worse than no document.
