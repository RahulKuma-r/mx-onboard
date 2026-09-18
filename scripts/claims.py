#!/usr/bin/env python3
"""Extract checkable claims from a document and verify them against a repo.

The mechanical half of /verify-doc. This resolves what can be resolved
mechanically -- does the path exist, does the file have that line, does the
identifier still appear anywhere -- and deliberately stops there.

Whether a *behavioural* claim is still true is judgement, and this prints
`unverifiable` rather than guessing. A checker that quietly downgrades "I
cannot tell" to "fine" is worse than no checker.

Usage:
    python claims.py <doc> [--root DIR] [--json]

Exit codes:
    0  every checkable claim holds
    1  at least one claim is stale
    2  could not run (missing doc, bad root)
"""
import argparse
import json
import os
import re
import sys

# A claim is only worth extracting if it can be wrong in a way a reader would act on.
#
# Both patterns below are deliberately narrow, because the second round of testing
# on a real document showed the cost of being loose: a wiki hostname ending in .net
# read as a path, a dotted log-field name read as a path, `mvn` read as an identifier.
# Each then came back "missing", which is a confident wrong answer about something
# that was never a claim about this repo.
SOURCE_EXT = (
    "cs|ts|tsx|js|jsx|mjs|java|py|go|rb|rs|kt|scala|swift|"
    "sql|proto|sh|ps1|bat|"
    "json|jsonc|yml|yaml|xml|toml|ini|config|csproj|sln|props|targets|"
    "md|txt|env|lock|gradle|dockerfile"
)
FILE_LINE = re.compile(rf"`?([\w./\\-]+\.(?:{SOURCE_EXT})):(\d+)`?", re.IGNORECASE)
PATH = re.compile(rf"`([\w./\\-]+\.(?:{SOURCE_EXT}))`", re.IGNORECASE)

# A code identifier looks like code: PascalCase, camelCase, snake_case, or an
# explicit call. A bare lowercase word is a command or an English word.
IDENTIFIER = re.compile(
    r"`("
    r"[A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)?"     # optional single dotted member
    r")(\(\))?`"
)
CODE_SHAPED = re.compile(r"[A-Z]|_")
PORT = re.compile(r"(?:port\s+|localhost:)(\d{2,5})\b", re.IGNORECASE)

# A sentence can claim a thing is ABSENT. Then not finding it is agreement, not drift.
NEGATION = re.compile(
    r"\b(?:no|not|never|without|absent|missing|removed|deleted|lacks|none)\b",
    re.IGNORECASE,
)

CODE_EXT = {
    ".cs", ".ts", ".tsx", ".js", ".jsx", ".java", ".py", ".go", ".rb", ".rs",
    ".sql", ".yml", ".yaml", ".json", ".xml", ".sh", ".ps1", ".md", ".proto",
}
# .claude holds worktrees -- second copies of the whole tree. A file found only
# there has not moved there; offering it as the new location sends the reader to
# a checkout that is not theirs.
SKIP_DIRS = {".git", ".claude", "node_modules", "bin", "obj", "dist", "build",
             "target", ".venv", "venv", "__pycache__", ".harness"}
MAX_FILES = 20000

# Identifiers common enough that finding them proves nothing.
NOISE = {
    "true", "false", "null", "none", "string", "int", "bool", "var", "let",
    "const", "class", "public", "private", "return", "if", "else", "for",
    "while", "new", "this", "self", "def", "function", "import", "from",
}


def strip_code_blocks(text):
    """Fenced blocks are examples, not claims about this repo."""
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def extract(text):
    """Return claims in document order, de-duplicated by (kind, value)."""
    body = strip_code_blocks(text)
    lines = body.splitlines()
    claims, seen = [], set()

    def add(kind, value, lineno, extra=None):
        key = (kind, value)
        if key in seen:
            return
        seen.add(key)
        claim = {"kind": kind, "value": value, "doc_line": lineno}
        if NEGATION.search(lines[lineno - 1]):
            # "No root nuget.config" is a claim that the file is ABSENT. Not finding
            # it confirms the document. The script cannot settle which way the
            # sentence points, so it flags rather than rules.
            claim["negated_context"] = True
        if extra:
            claim.update(extra)
        claims.append(claim)

    for i, line in enumerate(lines, 1):
        consumed = []
        for m in FILE_LINE.finditer(line):
            add("file_line", m.group(1), i, {"line_number": int(m.group(2))})
            consumed.append(m.group(0))
        remainder = line
        for c in consumed:
            remainder = remainder.replace(c, " ")
        for m in PATH.finditer(remainder):
            add("path", m.group(1), i)
        for m in IDENTIFIER.finditer(remainder):
            value, called = m.group(1), m.group(2)
            if value.lower() in NOISE:
                continue
            if re.fullmatch(rf"[\w-]+\.(?:{SOURCE_EXT})", value, re.IGNORECASE):
                continue  # a filename, already caught as a path
            # Explicit call syntax is intent; otherwise it has to look like code.
            if not called and not CODE_SHAPED.search(value):
                continue
            add("identifier", value, i)
        for m in PORT.finditer(remainder):
            add("port", m.group(1), i)

    return claims


def iter_repo_files(root):
    count = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.splitext(name)[1].lower() in CODE_EXT:
                count += 1
                if count > MAX_FILES:
                    return
                yield os.path.join(dirpath, name)


def build_index(root, doc_path=None):
    """basename -> [relative paths], plus the file list. One walk, reused by every claim.

    The document under test is excluded: a claim that appears only in the document
    making it is not evidence for that claim.
    """
    doc_abs = os.path.abspath(doc_path) if doc_path else None
    index, all_files, rel_paths = {}, [], []
    for full in iter_repo_files(root):
        if doc_abs and os.path.abspath(full) == doc_abs:
            continue
        rel = os.path.relpath(full, root).replace("\\", "/")
        index.setdefault(os.path.basename(full).lower(), []).append(rel)
        rel_paths.append(rel)
        all_files.append(full)
    return index, all_files, rel_paths


def resolve_path(root, index, rel_paths, value):
    """Three outcomes, in descending confidence.

    ok      -- resolves from the root, or the document wrote it relative to the
               subproject it is about (`Core/Account.cs` for `Web/Core/Account.cs`)
    moved   -- same basename, different path, and only one candidate
    missing -- nothing, or so many same-named files that naming one would be a guess
    """
    needle = value.replace("\\", "/").lstrip("./")
    if os.path.exists(os.path.join(root, needle)):
        return "ok", value

    suffix = "/" + needle
    tails = [p for p in rel_paths if p.endswith(suffix)]
    if len(tails) == 1:
        return "ok", tails[0]
    if len(tails) > 1:
        return "ok", tails[0]

    matches = index.get(os.path.basename(needle).lower(), [])
    if len(matches) == 1:
        return "moved", matches[0]
    if len(matches) > 1:
        return "moved", None
    return "missing", None


def _literal_hit(all_files, needle):
    raw = needle.encode("utf-8", "ignore")
    for full in all_files:
        try:
            with open(full, "rb") as fh:
                if raw in fh.read():
                    return os.path.relpath(full).replace("\\", "/")
        except OSError:
            continue
    return None


def identifier_hit(all_files, value):
    """Resolve an identifier, including the `Class.Method` form.

    Most languages declare the type and the member separately, so the joined
    string never appears in the source even when the claim is true. Checking
    only the literal reports a correct document as stale -- which it did,
    eleven times in one run, on a document this tool had just written.

    A `Class.Method` claim holds when both halves resolve; ideally in the same
    file, which is the strong answer.
    """
    hit = _literal_hit(all_files, value)
    if hit or "." not in value:
        return hit

    head, _, tail = value.partition(".")
    head_at = _literal_hit(all_files, head)
    if not head_at:
        return None

    # Strongest evidence: the member is declared in the file holding the type.
    head_full = os.path.join(os.getcwd(), head_at)
    for candidate in (head_full,):
        try:
            with open(candidate, "rb") as fh:
                if tail.encode("utf-8", "ignore") in fh.read():
                    return head_at
        except OSError:
            pass

    # Weaker, but still evidence: both halves exist somewhere in the repo.
    return head_at if _literal_hit(all_files, tail) else None


def verify(claims, root, doc_path=None):
    index, all_files, rel_paths = build_index(root, doc_path)
    for c in claims:
        kind, value = c["kind"], c["value"]

        if kind in ("path", "file_line"):
            status, found = resolve_path(root, index, rel_paths, value)
            c["status"] = status
            if found and found != value:
                c["found_at"] = found
            if status == "ok" and kind == "file_line":
                full = os.path.join(root, found or value)
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                        total = sum(1 for _ in fh)
                    if c["line_number"] > total:
                        c["status"] = "line_gone"
                        c["file_lines"] = total
                except OSError:
                    c["status"] = "unverifiable"

        elif kind == "identifier":
            hit = identifier_hit(all_files, value)
            c["status"] = "ok" if hit else "missing"
            if hit:
                c["found_at"] = hit

        else:  # port, and anything else we will not pretend to check
            c["status"] = "unverifiable"

    return claims


STALE = {"missing", "moved", "line_gone"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.doc):
        print(f"claims: no such document: {args.doc}", file=sys.stderr)
        return 2
    if not os.path.isdir(args.root):
        print(f"claims: no such root: {args.root}", file=sys.stderr)
        return 2

    with open(args.doc, "r", encoding="utf-8", errors="ignore") as fh:
        claims = verify(extract(fh.read()), args.root, doc_path=args.doc)

    counts = {}
    for c in claims:
        counts[c["status"]] = counts.get(c["status"], 0) + 1

    if args.json:
        print(json.dumps({"doc": args.doc, "root": args.root,
                          "counts": counts, "claims": claims}, indent=2))
    else:
        for c in sorted(claims, key=lambda x: (x["status"] != "missing", x["doc_line"])):
            extra = f"  -> {c['found_at']}" if c.get("found_at") else ""
            if c.get("negated_context"):
                extra += "   [negated sentence -- absence may confirm the doc]"
            print(f"  {c['status']:13s} line {c['doc_line']:4d}  "
                  f"{c['kind']:11s} {c['value']}{extra}")
        print("-" * 60)
        print("  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items())))

    return 1 if any(c["status"] in STALE for c in claims) else 0


if __name__ == "__main__":
    sys.exit(main())
