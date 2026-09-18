#!/usr/bin/env python3
"""PostToolUse hook: an onboarding document with no surprises has not earned its keep.

The /explain skill asks for a "What will surprise you" section, and asking is not
enforcing. This blocks the write when that section is present but empty.

Deliberately narrow: it only fires on a document that *has* the heading. A file
without it is not an onboarding document and is none of this hook's business.
That keeps the false-positive rate at zero for ordinary writes, which matters for
a hook that runs on every Edit and Write.

Removing the heading to get past this is working around the gate, not passing it.
"""
import json
import os
import re
import sys

HEADING = re.compile(r"^#{1,6}\s*what\s+will\s+surprise\s+you\s*$", re.IGNORECASE | re.MULTILINE)
NEXT_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
PLACEHOLDER = re.compile(r"^\s*(?:<.*>|todo|tbd|n/?a|none|-|\*)\s*$", re.IGNORECASE)

REASON = (
    "mx-onboard: the \"What will surprise you\" section is empty. That section is the "
    "pass condition for an onboarding document, not a formality -- a document with no "
    "surprises has told the reader what they could have found themselves. Go back and "
    "read the files where the behaviour lives, then write down what contradicted your "
    "expectations. Removing the heading is not a fix."
)


def section_body(text):
    """Text between the surprises heading and the next heading, or None if absent."""
    m = HEADING.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = NEXT_HEADING.search(rest)
    return rest[:nxt.start()] if nxt else rest


def is_empty(body):
    lines = [ln for ln in body.splitlines() if ln.strip()]
    if not lines:
        return True
    # A template placeholder is an empty section wearing content.
    return all(PLACEHOLDER.match(ln) for ln in lines)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path or not path.lower().endswith(".md") or not os.path.isfile(path):
        return 0

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read(500_000)
    except OSError:
        return 0

    body = section_body(text)
    if body is None or not is_empty(body):
        return 0

    print(json.dumps({"decision": "block", "reason": f"{REASON}\n\nFile: {path}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
