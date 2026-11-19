import tempfile
import os
import unittest
from pathlib import Path
from package_source import SourcePayload, PackageScopeError, include_linked_evidence

class PackageScope(unittest.TestCase):
    def setUp(self):
        self.retain_root = os.environ.get("PATAMAPS_TEST_RETAIN_ROOT")
        self.root = Path(tempfile.mkdtemp(prefix="patamaps-package-scope-test-", dir=self.retain_root))
    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p
    def seed(self, text):
        p = self.write("README.md", text)
        result = SourcePayload(self.root)
        result.add("README.md", p)
        return result
    def test_links_preserve_bytes_transitive_markdown_and_ignore_unreferenced_history(self):
        p = self.seed("[e](docs/acceptance/one.md)")
        self.write("docs/acceptance/one.md", "[receipt](sub/two.json#anchor)")
        self.write("docs/acceptance/sub/two.json", '{"passed":true}')
        self.write("docs/acceptance/unrelated-large.log", "not a source input")
        result = include_linked_evidence(p)
        self.assertEqual(result["files"], 2)
        self.assertEqual(p.files["docs/acceptance/sub/two.json"], b'{"passed":true}')
        self.assertNotIn("docs/acceptance/unrelated-large.log", p.files)
    def test_deduplicates_encoded_links_and_ignores_external_and_absolute_paths(self):
        p = self.seed("[one](docs/acceptance/a%20b.json) [two](docs/acceptance/a%20b.json?raw=1#x) [web](https://example.invalid/file) [host](/private/file)")
        self.write("docs/acceptance/a b.json", "{}")
        self.assertEqual(include_linked_evidence(p)["files"], 1)
    def test_current_receipt_stays_outside_payload(self):
        p = self.seed("[current](docs/acceptance/current/receipt.json)")
        result = include_linked_evidence(p, self.root / "docs/acceptance/current")
        self.assertEqual(result["files"], 0)
    def test_missing_references_refuse_instead_of_silently_breaking_navigation(self):
        p = self.seed("[missing](docs/acceptance/missing.json)")
        with self.assertRaises(PackageScopeError): include_linked_evidence(p)
    def test_evidence_count_and_bytes_refuse_before_loading_large_payload(self):
        p = self.seed("[a](docs/acceptance/a.json) [b](docs/acceptance/b.json)")
        self.write("docs/acceptance/a.json", "12")
        self.write("docs/acceptance/b.json", "34")
        with self.assertRaises(PackageScopeError): include_linked_evidence(p, maximum_files=1)
        p = self.seed("[a](docs/acceptance/a.json)")
        with self.assertRaises(PackageScopeError): include_linked_evidence(p, maximum_bytes=1)
    def test_total_source_budget_and_replacement_accounting(self):
        p = SourcePayload(self.root, maximum_bytes=3)
        f = self.write("a", "12")
        p.add("a", f); p.add("a", f)
        self.assertEqual(p.total_bytes, 2)
        with self.assertRaises(PackageScopeError): p.add("b", self.write("b", "34"))
    def test_source_symlink_escape_refuses(self):
        p = SourcePayload(self.root)
        other = Path(tempfile.mkdtemp(prefix="patamaps-package-scope-external-", dir=self.retain_root))
        file = other / "outside"; file.write_text("private")
        (self.root / "link").symlink_to(file)
        with self.assertRaises(PackageScopeError): p.add("link", self.root / "link")
    def test_directory_link_keeps_an_index_not_the_whole_tree(self):
        p = self.seed("[case](docs/acceptance/case/)")
        self.write("docs/acceptance/case/receipt.json", "{}")
        self.write("docs/acceptance/case/bulky.log", "unrelated")
        self.assertEqual(include_linked_evidence(p)["files"], 1)
        self.assertNotIn("docs/acceptance/case/bulky.log", p.files)

    def test_evidence_symlink_escape_refuses(self):
        p = self.seed("[unsafe](docs/acceptance/link.json)")
        other = self.write("outside.json", "private")
        link = self.root / "docs/acceptance/link.json"
        link.parent.mkdir(parents=True)
        link.symlink_to(other)
        with self.assertRaises(PackageScopeError): include_linked_evidence(p)
    def test_source_count_is_bounded_separately_from_bytes(self):
        p = SourcePayload(self.root, maximum_files=1)
        p.add("a", self.write("a", ""))
        with self.assertRaises(PackageScopeError): p.add("b", self.write("b", ""))

    def test_internal_evidence_alias_keeps_the_linked_member_name(self):
        p = self.seed("[alias](docs/acceptance/alias.json)")
        target = self.write("docs/acceptance/original.json", "{}")
        (target.parent / "alias.json").symlink_to(target.name)
        include_linked_evidence(p)
        self.assertIn("docs/acceptance/alias.json", p.files)

    def test_directory_index_cannot_escape_the_evidence_root(self):
        p = self.seed("[case](docs/acceptance/case/)")
        target = self.write("outside.json", "private")
        folder = self.root / "docs/acceptance/case"
        folder.mkdir(parents=True)
        (folder / "receipt.json").symlink_to(target)
        with self.assertRaises(PackageScopeError): include_linked_evidence(p)
    def test_directory_index_respects_the_excluded_current_receipt(self):
        p = self.seed("[case](docs/acceptance/case/)")
        target = self.write("docs/acceptance/current/receipt.json", "{}")
        folder = self.root / "docs/acceptance/case"
        folder.mkdir(parents=True)
        (folder / "receipt.json").symlink_to(target)
        self.assertEqual(include_linked_evidence(p, target.parent)["files"], 0)

if __name__ == "__main__": unittest.main()
