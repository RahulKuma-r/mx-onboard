#!/usr/bin/env python3
"""Tests for the document index and the drift hook.

The self-gating cases matter most. This hook runs on every Edit and Write, so
a repository that does not use the plugin must pay nothing and see nothing.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import doc_index  # noqa: E402

HOOK = os.path.join(ROOT, "hooks", "doc_drift.py")

DOC = """# Connector

## What it does
It connects things.

## The path
Entry point is `src/Worker.cs:42`, then `src/Router.cs`.

## What will surprise you
Exception type is the retry contract.

## Where to start
`src/Worker.cs`
"""

NOT_A_DOC = """# Meeting notes

We talked about `src/Worker.cs` and agreed to leave it alone.
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.write("src/Worker.cs", "class Worker {}\n")
        self.write("src/Router.cs", "class Router {}\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, body):
        full = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)
        return full


class TestIndex(Base):
    def test_finds_a_document_by_its_marker_not_its_path(self):
        self.write("anywhere/notes.md", DOC)
        self.assertEqual(len(doc_index.find_docs(self.root)), 1)

    def test_markdown_without_the_marker_is_not_a_document(self):
        self.write("docs/notes.md", NOT_A_DOC)
        self.assertEqual(doc_index.find_docs(self.root), [])

    def test_repo_with_no_documents_gives_an_empty_index(self):
        # The self-gate. No documents, no cost, no output.
        self.assertEqual(doc_index.build(self.root), {})

    def test_index_maps_cited_file_to_the_document(self):
        self.write("docs/onboarding/connector.md", DOC)
        idx = doc_index.build(self.root)
        self.assertIn("src/Worker.cs", idx)
        self.assertEqual(idx["src/Worker.cs"][0]["doc"], "docs/onboarding/connector.md")

    def test_file_line_and_plain_path_both_index_the_same_file(self):
        self.write("docs/onboarding/connector.md", DOC)
        idx = doc_index.build(self.root)
        self.assertGreaterEqual(len(idx["src/Worker.cs"]), 1)

    def test_citation_lookup_matches_a_subproject_relative_path(self):
        self.write("docs/onboarding/c.md", "## What will surprise you\nx\n\n`Core/App.cs`\n")
        self.write("apps/web/Core/App.cs", "class App {}\n")
        idx = doc_index.build(self.root)
        hits = doc_index.citations_for(idx, self.root,
                                       os.path.join(self.root, "apps/web/Core/App.cs"))
        self.assertEqual(len(hits), 1)

    def test_uncited_file_has_no_citations(self):
        self.write("docs/onboarding/connector.md", DOC)
        self.write("src/Unrelated.cs", "class Unrelated {}\n")
        idx = doc_index.build(self.root)
        hits = doc_index.citations_for(idx, self.root,
                                       os.path.join(self.root, "src/Unrelated.cs"))
        self.assertEqual(hits, [])


class TestHook(Base):
    def run_hook(self, path, cwd=None):
        payload = json.dumps({"tool_name": "Edit", "cwd": cwd or self.root,
                              "tool_input": {"file_path": path}})
        out = subprocess.run([sys.executable, HOOK], input=payload,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, "hook must always exit 0")
        return out.stdout.strip()

    def test_works_without_cwd_when_the_checkout_has_a_git_dir(self):
        os.makedirs(os.path.join(self.root, ".git"), exist_ok=True)
        self.write("docs/onboarding/connector.md", DOC)
        out = self.run_hook(os.path.join(self.root, "src/Worker.cs"), cwd="")
        self.assertIn("connector.md", json.loads(out)["systemMessage"])

    def test_cwd_outside_the_edited_file_is_ignored(self):
        # A cwd that does not contain the file must not be used as the root.
        self.write("docs/onboarding/connector.md", DOC)
        other = tempfile.mkdtemp()
        try:
            self.assertEqual(
                self.run_hook(os.path.join(self.root, "src/Worker.cs"), cwd=other), "")
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_notifies_when_the_edited_file_is_cited(self):
        self.write("docs/onboarding/connector.md", DOC)
        out = self.run_hook(os.path.join(self.root, "src/Worker.cs"))
        self.assertTrue(out, "expected a notice")
        msg = json.loads(out)
        self.assertIn("systemMessage", msg)
        self.assertIn("connector.md", msg["systemMessage"])

    def test_it_notifies_rather_than_blocking(self):
        # The design decision: drift is a maybe, so it must not stop the turn.
        self.write("docs/onboarding/connector.md", DOC)
        msg = json.loads(self.run_hook(os.path.join(self.root, "src/Worker.cs")))
        self.assertNotIn("decision", msg)

    def test_silent_when_no_document_cites_the_file(self):
        self.write("docs/onboarding/connector.md", DOC)
        self.assertEqual(self.run_hook(self.write("src/Other.cs", "class Other {}\n")), "")

    def test_silent_in_a_repo_with_no_onboarding_documents(self):
        self.assertEqual(self.run_hook(os.path.join(self.root, "src/Worker.cs")), "")

    def test_editing_the_document_itself_is_not_drift(self):
        doc = self.write("docs/onboarding/connector.md", DOC)
        self.assertEqual(self.run_hook(doc), "")

    def test_missing_file_is_ignored(self):
        self.write("docs/onboarding/connector.md", DOC)
        self.assertEqual(self.run_hook(os.path.join(self.root, "src/Gone.cs")), "")

    def test_malformed_stdin_does_not_crash(self):
        out = subprocess.run([sys.executable, HOOK], input="not json",
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
