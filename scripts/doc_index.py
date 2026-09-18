#!/usr/bin/env python3
"""Which onboarding documents cite which source files.

The mechanical half of the drift hook. `verify-doc` answers "is this document
still true"; this answers the inverse -- "I just changed this file, who claimed
something about it".

Self-gating: a repository with no onboarding documents gets an empty index and
the hook that calls this stays silent. A document is recognised by the heading
`/explain` writes, not by its path, so it is found wherever someone filed it.

Usage:
    python doc_index.py [--root DIR] [--for FILE] [--json]
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from claims import extract  # noqa: E402

# The marker that makes a markdown file an onboarding document rather than a note.
MARKER = re.compile(r"^#{1,6}\s*what\s+will\s+surprise\s+you\s*$", re.IGNORECASE | re.MULTILINE)

SKIP_DIRS = {".git", ".claude", "node_modules", "bin", "obj", "dist", "build",
             "target", ".venv", "venv", "__pycache__", ".harness"}
MAX_DOCS = 200


def find_docs(root):
    """Every markdown file carrying the onboarding marker."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if not name.lower().endswith(".md"):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    head = fh.read(200_000)
            except OSError:
                continue
            if MARKER.search(head):
                found.append((os.path.relpath(full, root).replace("\\", "/"), head))
                if len(found) >= MAX_DOCS:
                    return found
    return found


def build(root):
    """{source file -> [{doc, doc_line, claim}]}, keyed by repo-relative path."""
    index = {}
    for rel_doc, text in find_docs(root):
        for c in extract(text):
            if c["kind"] not in ("path", "file_line"):
                continue
            key = c["value"].replace("\\", "/").lstrip("./")
            index.setdefault(key, []).append({
                "doc": rel_doc,
                "doc_line": c["doc_line"],
                "claim": c["value"],
            })
    return index


def citations_for(index, root, changed):
    """Citations matching a changed file.

    Documents write paths relative to the subproject they describe, so an entry
    matches when the changed path ends with it. Exact-path-only matching missed
    almost everything in practice.
    """
    rel = os.path.relpath(os.path.abspath(changed), root).replace("\\", "/")
    hits = []
    for key, entries in index.items():
        if rel == key or rel.endswith("/" + key):
            hits.extend(entries)
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--for", dest="target", help="report only citations of this file")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isdir(args.root):
        print(f"doc_index: no such root: {args.root}", file=sys.stderr)
        return 2

    index = build(args.root)

    if args.target:
        hits = citations_for(index, args.root, args.target)
        if args.json:
            print(json.dumps({"file": args.target, "citations": hits}, indent=2))
        else:
            for h in hits:
                print(f"  {h['doc']}:{h['doc_line']}  cites  {h['claim']}")
            if not hits:
                print("  no onboarding document cites that file")
        return 0

    if args.json:
        print(json.dumps({"root": args.root, "files_cited": len(index),
                          "index": index}, indent=2))
    else:
        print(f"  {len(index)} source files are cited by onboarding documents")
        for key in sorted(index)[:40]:
            docs = sorted({e["doc"] for e in index[key]})
            print(f"    {key}  <-  {', '.join(docs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
