#!/usr/bin/env python3
"""PostToolUse hook: say so when an edit lands on a file a document describes.

`/verify-doc` only runs when someone already suspects a document has rotted.
This is the half that tells you *when* to suspect it -- at the moment the code
changes, not months later when a new joiner is misled by it.

It notifies. It does not block, and that difference is deliberate:

  require_surprises blocks, because an empty surprises section is definitely
  wrong and the fix is entirely in the author's hands.

  Drift is a *maybe*. The edit may not touch what the document claims. Blocking
  every edit to a documented file would train people to delete the documents,
  which is the opposite of the point.

Self-gating: a repository with no onboarding documents produces an empty index
and this exits silently. It costs one directory walk on repos that use the
plugin and nothing on repos that don't.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(os.path.dirname(HERE), "scripts", "doc_index.py")
MAX_SHOWN = 5


def git_root(start):
    """Nearest ancestor holding .git, or None."""
    d = os.path.abspath(start)
    if os.path.isfile(d):
        d = os.path.dirname(d)
    while True:
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def resolve_root(path, payload_cwd):
    """Where to look for documents.

    The session's cwd first: it is the project the person is working in, and it
    is right even when the checkout has no .git -- a worktree, an export, a
    temp directory. Falling straight to a .git walk resolved to the *file's own
    directory* when no .git existed, so the index came back empty and the hook
    silently did nothing.
    """
    ap = os.path.abspath(path)
    if payload_cwd and os.path.isdir(payload_cwd):
        cwd = os.path.abspath(payload_cwd)
        if os.path.commonpath([ap, cwd]) == cwd:
            return cwd
    return git_root(ap) or os.path.dirname(ap)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    path = (data.get("tool_input") or {}).get("file_path") or ""
    if not path or not os.path.isfile(path):
        return 0

    # Editing the document itself is not drift.
    if path.lower().endswith(".md"):
        return 0

    root = resolve_root(path, data.get("cwd"))
    try:
        out = subprocess.run(
            [sys.executable, INDEX, "--root", root, "--for", path, "--json"],
            capture_output=True, text=True, timeout=20,
        )
        if out.returncode != 0 or not out.stdout.strip():
            return 0
        hits = json.loads(out.stdout).get("citations", [])
    except Exception:
        return 0  # a hook that breaks the session is worse than a hook that misses

    if not hits:
        return 0

    rel = os.path.relpath(path, root).replace("\\", "/")
    by_doc = {}
    for h in hits:
        by_doc.setdefault(h["doc"], []).append(h["doc_line"])

    lines = [f"mx-onboard: you just edited {rel}, which onboarding docs describe:"]
    for doc in sorted(by_doc)[:MAX_SHOWN]:
        where = ", ".join(f"line {n}" for n in sorted(set(by_doc[doc]))[:4])
        lines.append(f"  - {doc} ({where})")
    if len(by_doc) > MAX_SHOWN:
        lines.append(f"  - and {len(by_doc) - MAX_SHOWN} more")
    lines.append("If this change altered what those documents claim, run /verify-doc on them.")

    print(json.dumps({"systemMessage": "\n".join(lines)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
