"""Checksum/membership/privacy controls; retain every fixture instead of deleting."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from cargo_registry_context import REGISTRY, inventory, stage


class RegistryContextTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='cargo-registry-control-', dir=os.environ['PATAMAPS_TEST_RETAIN_ROOT']))
        self.home = self.root / 'home'
        self.cache = self.home/'registry/cache/index.crates.io-1949cf8c6b5b557f'
        self.index = self.home/'registry/index/index.crates.io-1949cf8c6b5b557f'
        self.cache.mkdir(parents=True)
        (self.index/'.cache/de/mo').mkdir(parents=True)
        self.archive = self.cache/'demo-1.0.0.crate'
        self.archive.write_bytes(b'controlled checksum bytes; not application acceptance')
        (self.index/'config.json').write_text(json.dumps(dict(dl='https://static.crates.io/crates', api='https://crates.io')))
        (self.index/'.cache/de/mo/demo').write_bytes(b'controlled opaque index bytes')
        self.lock = self.root/'Cargo.lock'
        self.lock.write_text('version = 4\n[[package]]\nname="demo"\nversion="1.0.0"\nsource='+json.dumps(REGISTRY)+'\nchecksum="'+hashlib.sha256(self.archive.read_bytes()).hexdigest()+'"\n')

    def refused(self, code):
        with self.assertRaisesRegex(ValueError, code):
            inventory(self.home, self.lock)

    def test_exact_checksum_inventory_and_copy(self):
        value = inventory(self.home, self.lock)
        self.assertEqual(value['packageCount'], 1)
        self.assertEqual(value['fileCount'], 3)
        target = self.root/'staged'
        stage(self.home, target, value)
        self.assertEqual(inventory(target, self.lock), value)

    def test_corrupt_archive(self):
        self.archive.rename(self.root/'original.crate')
        self.archive.write_bytes(b'corrupt')
        self.refused('ARCHIVE_CHECKSUM')

    def test_missing_archive(self):
        self.archive.rename(self.root/'original.crate')
        self.refused('ARCHIVE_SET')

    def test_extra_archive(self):
        (self.cache/'unexpected-1.0.0.crate').write_bytes(b'extra')
        self.refused('ARCHIVE_SET')

    def test_credentials_injection(self):
        (self.home/'credentials.toml').write_text('controlled dummy; no credential')
        self.refused('HOME_INJECTION')

    def test_configuration_injection(self):
        (self.home/'config.toml').write_text('controlled source override')
        self.refused('HOME_INJECTION')

    def test_alternative_registry(self):
        self.lock.write_text(self.lock.read_text().replace(REGISTRY, 'registry+https://example.invalid'))
        self.refused('REGISTRY_SOURCE')

    def test_download_endpoint_injection(self):
        (self.index/'config.json').write_text(json.dumps(dict(dl='https://example.invalid', api='https://crates.io')))
        self.refused('REGISTRY_CONFIGURATION')

    def test_duplicate_configuration(self):
        (self.index/'config.json').write_text('{"dl":"https://example.invalid","dl":"https://static.crates.io/crates","api":"https://crates.io"}')
        self.refused('CONFIGURATION_DUPLICATE')

    def test_archive_symlink(self):
        original = self.root/'original.crate'
        self.archive.rename(original)
        self.archive.symlink_to(original)
        self.refused('SYMLINK')

    def test_index_missing(self):
        (self.index/'.cache/de/mo/demo').rename(self.root/'retained-index')
        self.refused('INDEX_MISSING')

    def test_changed_between_inventory_and_stage(self):
        value = inventory(self.home, self.lock)
        self.archive.rename(self.root/'original.crate')
        self.archive.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'SOURCE_CHANGED'):
            stage(self.home, self.root/'refused-stage', value)

    def test_registry_byte_bound(self):
        from unittest.mock import patch
        with patch('cargo_registry_context.MAXIMUM_BYTES', 8):
            self.refused('BYTE_LIMIT')


if __name__ == '__main__':
    unittest.main()
