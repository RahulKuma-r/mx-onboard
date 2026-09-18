#!/usr/bin/env python3
"""Tests for the require-surprises hook.

The allow cases matter more than the deny cases here. This hook runs on every
Edit and Write, so a false positive is a tax on unrelated work.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "require_surprises.py")

FULL = """# Entity migration

## What it does
It moves entities.

## What will surprise you
`Reporter` writes the same table the API writes. Neither name says so.

## Where to start
`Program.cs`
"""

EMPTY = """# Entity migration

## What will surprise you

## Where to start
`Program.cs`
"""

PLACEHOLDER = """# Entity migration

## What will surprise you
<facts that contradict what a reader would assume>

## Where to start
`Program.cs`
"""

TRAILING = """# Entity migration

## What will surprise you
"""

NO_HEADING = """# Some other document

## What it does
Ordinary notes with no onboarding heading at all.
"""


class TestHook(unittest.TestCase):
    def run_hook(self, body, suffix=".md", write=True):
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            if write:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
            payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": path}})
            out = subprocess.run([sys.executable, HOOK], input=payload,
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, "hook must always exit 0")
            return out.stdout.strip()
        finally:
            os.unlink(path)

    def assertBlocked(self, body, **kw):
        out = self.run_hook(body, **kw)
        self.assertTrue(out, "expected a block, got silence")
        self.assertEqual(json.loads(out)["decision"], "block")

    def assertAllowed(self, body, **kw):
        self.assertEqual(self.run_hook(body, **kw), "", "expected silence, got a block")

    # --- deny ---
    def test_empty_section_blocks(self):
        self.assertBlocked(EMPTY)

    def test_placeholder_counts_as_empty(self):
        self.assertBlocked(PLACEHOLDER)

    def test_section_at_end_of_file_with_nothing_after_it(self):
        self.assertBlocked(TRAILING)

    # --- allow ---
    def test_populated_section_passes(self):
        self.assertAllowed(FULL)

    def test_document_without_the_heading_is_not_our_business(self):
        self.assertAllowed(NO_HEADING)

    def test_non_markdown_is_ignored(self):
        self.assertAllowed(EMPTY, suffix=".cs")

    def test_missing_file_is_ignored(self):
        self.assertAllowed(EMPTY, write=False)

    def test_heading_match_is_case_insensitive(self):
        self.assertBlocked(EMPTY.replace("What will surprise you", "WHAT WILL SURPRISE YOU"))

    def test_deeper_heading_level_still_matches(self):
        self.assertBlocked(EMPTY.replace("## What will", "#### What will"))

    def test_prose_mentioning_the_phrase_is_not_a_heading(self):
        self.assertAllowed("# Doc\n\nHere is what will surprise you: nothing.\n")

    def test_malformed_stdin_does_not_crash(self):
        out = subprocess.run([sys.executable, HOOK], input="not json",
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
