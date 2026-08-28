import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from ensure_publish_metadata import ensure_metadata


class EnsurePublishMetadataTests(unittest.TestCase):
    def test_assigns_data_and_global_sequence_slug_to_new_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "existing.md").write_text(
                "---\ndate: 2026-08-20\nslug: '082006'\n---\nExisting\n",
                encoding="utf-8",
            )
            note = root / "new.md"
            note.write_text("New note\n", encoding="utf-8")

            changed = ensure_metadata(
                root,
                creation_date=lambda path: date(2026, 8, 27),
                now=datetime(2026, 8, 27, 12, 0, 0),
            )

            self.assertEqual(changed, [note])
            self.assertTrue(
                note.read_text(encoding="utf-8").startswith(
                    "---\ndate: 2026-08-27\nslug: '082707'\n---\n"
                )
            )

    def test_preserves_existing_metadata_and_assigns_next_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            existing = root / "existing.md"
            existing.write_text(
                "---\naliases:\n  - old-name\ndate: 2026-08-20\nslug: '082007'\n---\nBody\n",
                encoding="utf-8",
            )

            changed = ensure_metadata(root, creation_date=lambda path: date(2026, 8, 27))

            self.assertEqual(changed, [])
            self.assertIn("aliases:\n  - old-name", existing.read_text(encoding="utf-8"))

    def test_rejects_duplicate_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a.md", "b.md"):
                (root / name).write_text(
                    "---\ndate: 2026-08-27\nslug: '082701'\n---\nBody\n",
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "duplicate slug"):
                ensure_metadata(root, creation_date=lambda path: date(2026, 8, 27))

    def test_migrates_legacy_data_field_to_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            note = root / "legacy.md"
            note.write_text(
                "---\ndata: 2026-08-27\nslug: '082707'\n---\nBody\n",
                encoding="utf-8",
            )

            changed = ensure_metadata(root, creation_date=lambda path: date(2026, 8, 27))

            self.assertEqual(changed, [note])
            text = note.read_text(encoding="utf-8")
            self.assertIn("date: 2026-08-27", text)
            self.assertNotIn("data:", text)

    def test_skips_index_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            index = root / "index.md"
            index.write_text("Home\n", encoding="utf-8")

            changed = ensure_metadata(root, creation_date=lambda path: date(2026, 8, 27))

            self.assertEqual(changed, [])
            self.assertEqual(index.read_text(encoding="utf-8"), "Home\n")


if __name__ == "__main__":
    unittest.main()
