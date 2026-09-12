"""Git管理集約後も上流revisionと取り込み時の差分を正しく記録する。"""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import source_provenance


class SourceProvenanceTest(unittest.TestCase):
    def test_all_imports_without_git(self):
        sources = json.loads(source_provenance.MANIFEST.read_text())["sources"]
        with patch("subprocess.check_output", side_effect=AssertionError("Gitを呼び出した")):
            for key, record in sources.items():
                with self.subTest(source=key):
                    directory = source_provenance.PROJECT_ROOT / key
                    self.assertEqual(source_provenance.upstream_revision(directory), record["revision"])
                    self.assertEqual(bool(source_provenance.upstream_patch_at_import(directory)),
                                     bool(record["local_patch_at_import"]))

    def test_unknown_source_is_not_parent_revision(self):
        directory = source_provenance.PROJECT_ROOT / "research/unknown-source"
        with self.assertRaises(KeyError):
            source_provenance.upstream_revision(directory)

    def test_source_outside_project_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                source_provenance.upstream_revision(directory)


if __name__ == "__main__":
    unittest.main()
