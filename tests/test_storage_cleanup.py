"""Synthetic, CPU-only checks for migration cleanup guards."""
import importlib.util
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('storage_cleanup', ROOT / 'scripts/finish_storage_migration.py')
cleanup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup)


def row_for(path, relative):
    s = path.lstat()
    return {'relative_path': relative, 'device': s.st_dev, 'inode': s.st_ino,
            'type': cleanup.kind(s), 'mode': oct(s.st_mode & 0o7777),
            'uid': s.st_uid, 'gid': s.st_gid, 'size_bytes': s.st_size,
            'mtime_ns': s.st_mtime_ns, 'ctime_ns': s.st_ctime_ns}


class StorageCleanupTests(unittest.TestCase):
    def test_root_rename_preserves_identity_but_changes_ctime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'source'
            root.mkdir()
            row = row_for(root, '')
            renamed = Path(tmp) / 'renamed'
            root.rename(renamed)
            cleanup.unchanged(renamed.lstat(), row)

    def test_directory_identity_survives_child_unlink_only_in_cleanup_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / 'child'
            child.write_text('fixture')
            os.utime(root, ns=(1_000_000_000, 1_000_000_000))
            row = row_for(root, 'dir')
            child.unlink()
            with self.assertRaises(RuntimeError):
                cleanup.unchanged(root.lstat(), row)
            cleanup.unchanged(root.lstat(), row, directory_after_unlink=True)

    def test_replaced_file_is_rejected_even_if_size_and_mtime_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'entry'
            path.write_bytes(b'one')
            row = row_for(path, 'entry')
            replacement = root / 'replacement'
            replacement.write_bytes(b'two')
            os.utime(replacement, ns=(row['mtime_ns'], row['mtime_ns']))
            os.replace(replacement, path)
            with self.assertRaises(RuntimeError):
                cleanup.unchanged(path.lstat(), row)

    def test_final_byte_check_rejects_mutation_even_when_receipt_looks_equal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'destination'
            path.write_bytes(b'one')
            original = path.stat()
            receipt = cleanup.identity(original)
            row = row_for(path, 'destination')
            row.update(xattr_sha256=cleanup.attributes(path), hash_status='verified_at_scan',
                       sha256=hashlib.sha256(b'one').hexdigest(), source_root='home')
            path.write_bytes(b'two')
            os.utime(path, ns=(original.st_atime_ns, original.st_mtime_ns))
            self.assertEqual(path.stat().st_size, original.st_size)
            self.assertEqual(path.stat().st_mtime_ns, original.st_mtime_ns)
            # Simulate an unchanged ctime receipt on a coarse-clock filesystem.
            with patch.object(cleanup, 'identity', return_value=receipt):
                with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
                    cleanup.verify_before_unlink(row, root, root, set(), {}, receipt)

    def test_destination_same_size_and_mtime_replacement_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'destination'
            path.write_bytes(b'one')
            original = path.stat()
            receipt = cleanup.identity(original)
            replacement = root / 'replacement'
            replacement.write_bytes(b'two')
            os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
            os.replace(replacement, path)
            self.assertEqual(path.stat().st_size, original.st_size)
            self.assertEqual(path.stat().st_mtime_ns, original.st_mtime_ns)
            with self.assertRaises(RuntimeError):
                cleanup.destination_unchanged(path, receipt)

    def test_enumeration_records_symlink_without_following_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / 'source'
            outside = base / 'outside'
            root.mkdir()
            outside.mkdir()
            (outside / 'hidden').write_text('fixture')
            (root / 'link').symlink_to(outside, target_is_directory=True)
            self.assertEqual(cleanup.enumerate_tree(root), {'', 'link'})

    def test_hard_linked_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / 'source'
            path.write_bytes(b'fixture')
            os.link(path, root / 'alias')
            with self.assertRaises(RuntimeError):
                cleanup.unchanged(path.lstat(), row_for(path, 'source'))


if __name__ == '__main__':
    unittest.main()
