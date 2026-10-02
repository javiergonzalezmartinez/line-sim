import os, re, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class T(unittest.TestCase):
    def setUp(self):
        self.readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        self.refs = set(re.findall(r"docs/img/([\w\-]+\.png)", self.readme))
        self.files = set(f for f in os.listdir(os.path.join(ROOT, "docs", "img")) if f.endswith(".png"))

    def test_every_reference_exists(self):
        self.assertEqual(self.refs - self.files, set())

    def test_every_image_is_shown_in_readme(self):
        self.assertEqual(self.files - self.refs, set())

    def test_images_are_small(self):
        for f in self.files:
            self.assertLess(os.path.getsize(os.path.join(ROOT, "docs", "img", f)), 150_000, f)
