import os, re, unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


class ReadmeTests(unittest.TestCase):
    def test_local_links_and_images_exist(self):
        txt = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        refs = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", txt)
        self.assertGreaterEqual(len(refs), 9)
        for r in refs:
            if not r.startswith("http"):
                self.assertTrue(os.path.exists(os.path.join(ROOT, r)), r)

    def test_example_commands_use_existing_files(self):
        txt = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        for f in set(re.findall(r"examples/[\w.-]+\.json", txt)):
            self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)

    def test_honesty_statements_present(self):
        txt = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        for needle in ("not a real SAP integration", "illustrative", "synthetic", "Not modelled"):
            self.assertIn(needle.lower(), txt.lower())
