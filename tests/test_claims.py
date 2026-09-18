#!/usr/bin/env python3
"""Tests for the claims extractor and verifier."""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import claims  # noqa: E402


class TestExtract(unittest.TestCase):
    def kinds(self, text):
        return [(c["kind"], c["value"]) for c in claims.extract(text)]

    def test_file_line_is_one_claim_not_two(self):
        got = claims.extract("See `src/app.ts:42` for the handler.")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["kind"], "file_line")
        self.assertEqual(got[0]["value"], "src/app.ts")
        self.assertEqual(got[0]["line_number"], 42)

    def test_backticked_path(self):
        self.assertIn(("path", "src/Widget/Foo.cs"),
                      self.kinds("Lives in `src/Widget/Foo.cs` today."))

    def test_identifier(self):
        self.assertIn(("identifier", "resolveAddress"),
                      self.kinds("The `resolveAddress()` method does the work."))

    def test_filename_in_backticks_is_a_path_not_an_identifier(self):
        got = self.kinds("Config lives in `appsettings.json`.")
        self.assertIn(("path", "appsettings.json"), got)
        self.assertNotIn(("identifier", "appsettings.json"), got)

    def test_code_blocks_are_not_claims(self):
        text = "Real: `src/a.ts`\n\n```\nfake `src/zzz.ts` inside a block\n```\n"
        values = [v for _, v in self.kinds(text)]
        self.assertIn("src/a.ts", values)
        self.assertNotIn("src/zzz.ts", values)

    def test_language_keywords_are_not_claims(self):
        self.assertEqual(self.kinds("Use `true` or `return` here."), [])

    def test_port(self):
        self.assertIn(("port", "5433"), self.kinds("Postgres is on port 5433."))

    def test_duplicates_collapse(self):
        got = self.kinds("`src/a.ts` and again `src/a.ts`")
        self.assertEqual(got.count(("path", "src/a.ts")), 1)

    def test_doc_line_is_recorded(self):
        got = claims.extract("intro\n\nsee `src/a.ts`\n")
        self.assertEqual(got[0]["doc_line"], 3)

    def test_empty_document(self):
        self.assertEqual(claims.extract(""), [])


class TestNotAClaim(unittest.TestCase):
    """Second round of false positives from the same real document.

    Reporting something as stale that was never about this repo is the same
    error as certifying a stale claim: a wrong answer stated confidently.
    """

    def values(self, text):
        return [c["value"] for c in claims.extract(text)]

    def test_hostname_is_not_a_path(self):
        self.assertNotIn("wiki.example.net",
                         self.values("Wiki lives at `wiki.example.net` today."))

    def test_dotted_field_name_is_not_a_path(self):
        for v in ("app.entity.id", "app.tenant.id", "actor.type"):
            self.assertNotIn(v, self.values(f"The `{v}` tag is set downstream."))

    def test_bare_lowercase_word_is_not_a_code_identifier(self):
        for v in ("mvn", "grep", "ex", "dotnet"):
            self.assertNotIn(v, self.values(f"Run `{v}` to check."))

    def test_camel_case_is_still_extracted(self):
        self.assertIn("resolveAddress", self.values("Call `resolveAddress` first."))

    def test_pascal_case_is_still_extracted(self):
        self.assertIn("TokenValidator", self.values("See `TokenValidator`."))

    def test_snake_case_is_still_extracted(self):
        self.assertIn("user_id", self.values("The `user_id` column."))

    def test_explicit_call_syntax_is_extracted_even_if_lowercase(self):
        self.assertIn("grep", self.values("We `grep()` for it."))

    def test_real_source_extension_is_still_a_path(self):
        self.assertIn("src/Foo.cs", self.values("Lives in `src/Foo.cs`."))

    def test_negated_sentence_is_flagged(self):
        # "No root nuget.config" claims absence. Not finding it agrees with the doc.
        got = claims.extract("- No root `nuget.config`; restore uses the default source.")
        self.assertTrue(got[0].get("negated_context"))

    def test_plain_sentence_is_not_flagged(self):
        got = claims.extract("Config lives in `nuget.config` at the root.")
        self.assertFalse(got[0].get("negated_context"))


class TestVerify(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "src", "deep"))
        self._write("src/app.ts", "line1\nline2\nline3\n")
        self._write("src/deep/moved.cs", "public class Widget {}\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel, body):
        full = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)

    def check(self, text):
        return {c["value"]: c for c in claims.verify(claims.extract(text), self.root)}

    def test_existing_path_is_ok(self):
        self.assertEqual(self.check("`src/app.ts`")["src/app.ts"]["status"], "ok")

    def test_absent_path_is_missing(self):
        self.assertEqual(self.check("`src/gone.ts`")["src/gone.ts"]["status"], "missing")

    def test_relocated_file_reports_moved_and_where(self):
        got = self.check("`src/old/moved.cs`")["src/old/moved.cs"]
        self.assertEqual(got["status"], "moved")
        self.assertEqual(got["found_at"], "src/deep/moved.cs")

    def test_line_past_end_of_file_is_stale(self):
        got = self.check("`src/app.ts:99`")["src/app.ts"]
        self.assertEqual(got["status"], "line_gone")
        self.assertEqual(got["file_lines"], 3)

    def test_line_within_file_is_ok(self):
        self.assertEqual(self.check("`src/app.ts:2`")["src/app.ts"]["status"], "ok")

    def test_identifier_present_in_repo(self):
        got = self.check("The `Widget` class.")["Widget"]
        self.assertEqual(got["status"], "ok")
        self.assertTrue(got["found_at"].endswith("moved.cs"))

    def test_identifier_absent_from_repo(self):
        self.assertEqual(self.check("The `Sprocket` class.")["Sprocket"]["status"], "missing")

    def test_class_dot_method_resolves_when_both_halves_exist(self):
        # Found by pointing the checker at a document the writer had just produced.
        # C# declares the class and the method separately, so the joined string
        # never appears -- but the claim is true. Eleven false positives in one run.
        self._write("Services/Worker.cs",
                    "class QueueConsumer {\n  async Task ExecuteAsync() {}\n}\n")
        got = self.check("See `QueueConsumer.ExecuteAsync`.")["QueueConsumer.ExecuteAsync"]
        self.assertEqual(got["status"], "ok")

    def test_class_dot_method_is_missing_when_the_method_is_not_there(self):
        self._write("Services/Worker.cs", "class QueueConsumer {}\n")
        got = self.check("See `QueueConsumer.NoSuchThing`.")["QueueConsumer.NoSuchThing"]
        self.assertEqual(got["status"], "missing")

    def test_class_dot_method_is_missing_when_the_class_is_not_there(self):
        self._write("Services/Worker.cs", "class Other {\n  void ExecuteAsync() {}\n}\n")
        got = self.check("See `Ghost.ExecuteAsync`.")["Ghost.ExecuteAsync"]
        self.assertEqual(got["status"], "missing")

    def test_port_is_unverifiable_not_ok(self):
        # The important one: we must not pretend to have checked.
        self.assertEqual(self.check("port 5433")["5433"]["status"], "unverifiable")

    def test_stale_set_excludes_unverifiable(self):
        self.assertNotIn("unverifiable", claims.STALE)


class TestFalsePositives(unittest.TestCase):
    """Found by running this on a real document. Each was a wrong answer, not a gap."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self._write("src/Web/Core/Account.cs", "class Account {}\n")
        # A worktree holds a second copy of everything. It is not where anything moved to.
        self._write(".claude/worktrees/flat/src/Web/Core/Account.cs", "class Account {}\n")
        self._write(".claude/worktrees/flat/Only/In/Worktree.cs", "class Ghost {}\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _write(self, rel, body):
        full = os.path.join(self.root, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body)

    def check(self, text, doc_path=None):
        got = claims.verify(claims.extract(text), self.root, doc_path=doc_path)
        return {c["value"]: c for c in got}

    def test_subproject_relative_path_resolves_rather_than_reporting_moved(self):
        # The document writes paths relative to the project it is about.
        got = self.check("`Core/Account.cs`")["Core/Account.cs"]
        self.assertEqual(got["status"], "ok")
        self.assertEqual(got["found_at"], "src/Web/Core/Account.cs")

    def test_worktree_copy_is_never_offered_as_the_new_location(self):
        got = self.check("`Only/In/Worktree.cs`")["Only/In/Worktree.cs"]
        self.assertEqual(got["status"], "missing")
        self.assertIsNone(got.get("found_at"))

    def test_identifier_found_only_in_the_document_itself_proves_nothing(self):
        # The worst possible bug here: certifying a stale claim as fine.
        doc = os.path.join(self.root, "NOTES.md")
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write("The `Sprocket` class does the work.\n")
        got = self.check("The `Sprocket` class does the work.", doc_path=doc)["Sprocket"]
        self.assertEqual(got["status"], "missing")

    def test_identifier_present_in_real_code_still_passes(self):
        doc = os.path.join(self.root, "NOTES.md")
        with open(doc, "w", encoding="utf-8") as fh:
            fh.write("The `Account` class.\n")
        got = self.check("The `Account` class.", doc_path=doc)["Account"]
        self.assertEqual(got["status"], "ok")
        self.assertNotIn("worktrees", got["found_at"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
