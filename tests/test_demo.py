import os, re, tempfile, unittest
from plantsim import demo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

class DemoTest(unittest.TestCase):
    def test_readme_flags_exist_in_cli(self):
        readme = open(os.path.join(ROOT, "README.md")).read()
        cli = open(os.path.join(ROOT, "plantsim", "cli.py")).read()
        flags = set(re.findall(r"`?python3? -m plantsim[.a-z]*[^\n`]*", readme))
        used = set(f for l in flags for f in re.findall(r"(--[a-z][a-z-]+)", l))
        self.assertTrue(used)
        for f in used:
            self.assertIn('"%s"' % f, cli, f)

    def test_demo_builds_all_pages(self):
        with tempfile.TemporaryDirectory() as d:
            res = demo.build(d)
            self.assertTrue(all(ok for _, _, ok in res), res)
            self.assertEqual(len(res), len(demo.PAGES))
            self.assertIn("index.html", os.listdir(d))
            self.assertIn("illustrative", open(os.path.join(d, "index.html")).read())

if __name__ == "__main__":
    unittest.main()
