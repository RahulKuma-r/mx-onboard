#!/usr/bin/env python3
"""Manifest, frontmatter and drift tests for the plugin itself.

These catch the failures that do not show up until someone else installs it:
a skill declared in the manifest but never written, an agent whose tool list
quietly includes Write, a README that has fallen out of step with the folder.
"""
import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
KEY = re.compile(r"^(\w+):\s*(.*)$")

# An agent in this plugin reads and reports. None of them may change anything.
FORBIDDEN_TOOLS = {"Write", "Edit", "NotebookEdit", "MultiEdit"}


def frontmatter(path):
    """Parse the subset of YAML these files use, including folded scalars.

    `description: >-` followed by indented lines is the normal way to write a long
    trigger list. A naive line regex captures ">-" as the value, which made this
    suite pass on nothing.
    """
    with open(path, "r", encoding="utf-8") as fh:
        m = FRONTMATTER.match(fh.read())
    if not m:
        return None

    out, key, folded = {}, None, []
    for line in m.group(1).splitlines():
        if line.startswith((" ", "\t")) and key:
            folded.append(line.strip())
            continue
        if key:
            out[key] = " ".join(folded).strip() or out.get(key, "")
            key, folded = None, []
        km = KEY.match(line)
        if not km:
            continue
        k, v = km.group(1), km.group(2).strip()
        if v in (">", ">-", "|", "|-"):
            key = k
            out[k] = ""
        else:
            out[k] = v
    if key:
        out[key] = " ".join(folded).strip() or out.get(key, "")
    return out


def skill_dirs():
    base = os.path.join(ROOT, "skills")
    return sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))


def agent_files():
    base = os.path.join(ROOT, "agents")
    if not os.path.isdir(base):
        return []
    return sorted(f for f in os.listdir(base) if f.endswith(".md"))


class TestManifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            self.plugin = json.load(fh)
        with open(os.path.join(ROOT, ".claude-plugin", "marketplace.json"), encoding="utf-8") as fh:
            self.market = json.load(fh)

    def test_plugin_and_marketplace_agree_on_the_name(self):
        self.assertEqual(self.plugin["name"], self.market["plugins"][0]["name"])

    def test_version_is_semver(self):
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")

    def test_every_declared_skill_exists_on_disk(self):
        for entry in self.plugin["skills"]:
            path = os.path.join(ROOT, entry.replace("./", ""), "SKILL.md")
            self.assertTrue(os.path.isfile(path), f"declared but missing: {entry}")

    def test_every_skill_on_disk_is_declared(self):
        declared = {e.rsplit("/", 1)[-1] for e in self.plugin["skills"]}
        self.assertEqual(set(skill_dirs()), declared,
                         "a skill exists but the manifest does not list it")


class TestSkillFrontmatter(unittest.TestCase):
    def test_every_skill_has_name_and_description(self):
        for d in skill_dirs():
            fm = frontmatter(os.path.join(ROOT, "skills", d, "SKILL.md"))
            self.assertIsNotNone(fm, f"{d}: no frontmatter")
            self.assertIn("name", fm, f"{d}: no name")
            self.assertIn("description", fm, f"{d}: no description")

    def test_skill_name_matches_its_directory(self):
        for d in skill_dirs():
            fm = frontmatter(os.path.join(ROOT, "skills", d, "SKILL.md"))
            self.assertEqual(fm["name"], d)

    def test_description_says_when_to_use_not_what_it_does(self):
        # A description that summarises the workflow gets followed instead of the skill.
        for d in skill_dirs():
            fm = frontmatter(os.path.join(ROOT, "skills", d, "SKILL.md"))
            self.assertIn("use when", fm["description"].lower(), f"{d}: no triggering condition")


class TestAgents(unittest.TestCase):
    def test_there_are_agents(self):
        self.assertTrue(agent_files(), "the plugin ships no agents")

    def test_every_agent_has_name_description_and_tools(self):
        for f in agent_files():
            fm = frontmatter(os.path.join(ROOT, "agents", f))
            self.assertIsNotNone(fm, f"{f}: no frontmatter")
            for key in ("name", "description", "tools"):
                self.assertIn(key, fm, f"{f}: no {key}")

    def test_agent_name_matches_its_filename(self):
        for f in agent_files():
            fm = frontmatter(os.path.join(ROOT, "agents", f))
            self.assertEqual(fm["name"], f[:-3])

    def test_no_agent_can_write(self):
        # Read-only is enforced by the tool list, not by asking nicely in the body.
        for f in agent_files():
            fm = frontmatter(os.path.join(ROOT, "agents", f))
            tools = {t.strip() for t in fm["tools"].split(",")}
            bad = tools & FORBIDDEN_TOOLS
            self.assertFalse(bad, f"{f}: has write access via {bad}")

    def test_no_agent_has_bash(self):
        # Bash is a hole in read-only. The caller runs the scripts and hands over results.
        for f in agent_files():
            fm = frontmatter(os.path.join(ROOT, "agents", f))
            tools = {t.strip() for t in fm["tools"].split(",")}
            self.assertNotIn("Bash", tools, f"{f}: Bash defeats the read-only tool list")


class TestDocsMatchReality(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            self.readme = fh.read()

    def test_readme_mentions_every_skill(self):
        for d in skill_dirs():
            self.assertIn(d, self.readme, f"README does not mention /{d}")

    def test_readme_mentions_every_agent(self):
        for f in agent_files():
            self.assertIn(f[:-3], self.readme, f"README does not mention the {f[:-3]} agent")

    def test_install_doc_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "INSTALL.md")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
