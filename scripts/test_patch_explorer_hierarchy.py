import tempfile
import unittest
from pathlib import Path

from patch_explorer_hierarchy import patch_file


class PatchExplorerHierarchyTests(unittest.TestCase):
    def test_uses_file_path_for_tree_and_keeps_slug_for_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.js"
            path.write_text(
                'class X{add(e){this.insert(e.slug.split("/"),e)}}', encoding="utf-8"
            )

            self.assertTrue(patch_file(path))
            result = path.read_text(encoding="utf-8")
            self.assertIn("e.filePath||e.slug", result)
            self.assertIn('replace(/\\.md$/,"")', result)
            self.assertNotIn('this.insert(e.slug.split("/"),e)', result)

    def test_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.js"
            path.write_text(
                'class X{add(e){this.insert(e.slug.split("/"),e)}}', encoding="utf-8"
            )
            self.assertTrue(patch_file(path))
            self.assertFalse(patch_file(path))


if __name__ == "__main__":
    unittest.main()
