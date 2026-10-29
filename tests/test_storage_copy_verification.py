"""Storage copy verification fails closed without printing original data."""
from pathlib import Path
import hashlib
import os
import shutil
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_consolidated_storage import verify


class StorageCopyTests(unittest.TestCase):
    def fixture(self, root, protected=False):
        source, target = root / 'home', root / 'data'
        source.mkdir()
        target.mkdir()
        f = source / 'record'
        f.write_bytes(b'fixture only\n')
        f.chmod(0o600)
        shutil.copy2(f, target / 'record')
        s = f.stat()
        row = {'relative_path': 'record', 'source_path': str(f), 'source_root': 'home', 'type': 'file',
               'mode': oct(stat.S_IMODE(s.st_mode)), 'uid': s.st_uid, 'gid': s.st_gid,
               'mtime_ns': s.st_mtime_ns, 'size_bytes': s.st_size, 'xattr_sha256': {},
               'hash_status': 'protected_metadata_only' if protected else 'verified_at_scan'}
        if not protected:
            row['sha256'] = hashlib.sha256(f.read_bytes()).hexdigest()
        return row, source, target

    def test_verified_copy_matches_snapshot_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, source, target = self.fixture(Path(tmp))
            self.assertEqual(verify(row, target, source, set()), 'sha256_equal')

    def test_wrong_bytes_fail_even_when_size_and_mtime_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, source, target = self.fixture(Path(tmp))
            f = target / 'record'
            f.write_bytes(b'x' * row['size_bytes'])
            os.utime(f, ns=(row['mtime_ns'], row['mtime_ns']))
            with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
                verify(row, target, source, set())

    def test_protected_copy_uses_byte_equality_without_published_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            row, source, target = self.fixture(Path(tmp), protected=True)
            self.assertNotIn('sha256', row)
            self.assertEqual(verify(row, target, source, set()), 'protected_bytes_equal')
            f = target / 'record'
            f.write_bytes(b'x' * row['size_bytes'])
            os.utime(f, ns=(row['mtime_ns'], row['mtime_ns']))
            with self.assertRaisesRegex(RuntimeError, 'protected byte comparison mismatch'):
                verify(row, target, source, set())


if __name__ == '__main__':
    unittest.main()
