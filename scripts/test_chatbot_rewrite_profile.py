"""Controlled overlay refusal cases; actual owner hash/runtime is a separate CI gate."""
import copy
import json
import os
import stat
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import chatbot_rewrite_profile as profile

CONTROLLED = b"const nextConfig = {\n  cacheComponents: true,\n};\nexport default withBotId(nextConfig);\n"

class RewriteOverlayControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent = Path(os.environ['PATAMAPS_TEST_RETAIN_ROOT'])
        cls.root = Path(tempfile.mkdtemp(prefix='rewrite-overlay-', dir=parent))

    def prepare(self, content=CONTROLLED):
        root = self.root / self._testMethodName
        root.mkdir()
        (root / 'next.config.ts').write_bytes(content)
        (root / 'next.config.ts').chmod(0o644)
        rows = [dict(path='next.config.ts', digest=profile.digest(content), bytes=len(content),
                     gitBlob='controlled-unit-blob', symlink=False, mode='100644')]
        return root, rows

    def test_unknown_config_refuses_before_writes(self):
        root, rows = self.prepare()
        with self.assertRaisesRegex(AssertionError, 'UNKNOWN_ORIGINAL'):
            profile.apply(root, rows, canonical_port=39123)
        self.assertEqual((root/'next.config.ts').read_bytes(), CONTROLLED)
        self.assertFalse((root/profile.PROFILE_PATH).exists())

    def test_existing_profile_preserved(self):
        root, rows = self.prepare()
        target = root/profile.PROFILE_PATH
        target.write_bytes(b'preserve existing')
        with patch.object(profile, 'ORIGINAL_CONFIG_SHA', profile.digest(CONTROLLED)):
            with self.assertRaisesRegex(AssertionError, 'PROFILE_EXISTS'):
                profile.apply(root, rows, canonical_port=39123)
        self.assertEqual(target.read_bytes(), b'preserve existing')
        self.assertEqual((root/'next.config.ts').read_bytes(), CONTROLLED)

    def test_broken_profile_symlink_refuses(self):
        root, rows = self.prepare()
        target = root/profile.PROFILE_PATH
        target.symlink_to('missing-preserved-target')
        with patch.object(profile, 'ORIGINAL_CONFIG_SHA', profile.digest(CONTROLLED)):
            with self.assertRaisesRegex(AssertionError, 'PROFILE_EXISTS'):
                profile.apply(root, rows, canonical_port=39123)
        self.assertTrue(target.is_symlink())
        self.assertFalse((root/'missing-preserved-target').exists())
        self.assertEqual((root/'next.config.ts').read_bytes(), CONTROLLED)

    def test_ambiguous_inventory_refuses_before_writes(self):
        root, rows = self.prepare()
        rows.append(copy.deepcopy(rows[0]))
        with patch.object(profile, 'ORIGINAL_CONFIG_SHA', profile.digest(CONTROLLED)):
            with self.assertRaises(AssertionError):
                profile.apply(root, rows, canonical_port=39123)
        self.assertFalse((root/profile.PROFILE_PATH).exists())
        self.assertEqual((root/'next.config.ts').read_bytes(), CONTROLLED)

    def test_unknown_shape_refuses_before_writes(self):
        bad = b'const nextConfig = {};\n'
        root, rows = self.prepare(bad)
        with patch.object(profile, 'ORIGINAL_CONFIG_SHA', profile.digest(bad)):
            with self.assertRaisesRegex(AssertionError, 'CONFIG_SHAPE'):
                profile.apply(root, rows, canonical_port=39123)
        self.assertFalse((root/profile.PROFILE_PATH).exists())
        self.assertEqual((root/'next.config.ts').read_bytes(), bad)

    def test_invalid_port_refuses_before_writes(self):
        root, rows = self.prepare()
        for port in [True, 0, 1024, 65536, '39123', None]:
            with self.assertRaisesRegex(AssertionError, 'OWNER_PORT'):
                profile.apply(root, rows, canonical_port=port)
        self.assertFalse((root/profile.PROFILE_PATH).exists())
        self.assertEqual((root/'next.config.ts').read_bytes(), CONTROLLED)

    def test_real_port_reservation_and_handoff(self):
        reservation = profile.reserve_owner_port()
        address = reservation.getsockname()
        try:
            self.assertEqual(address[0], '127.0.0.1')
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as contender:
                with self.assertRaises(OSError):
                    contender.bind(address)
        finally:
            reservation.close()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as owner:
            owner.bind(address)
        self.assertEqual(reservation.fileno(), -1)

    def test_derived_bytes_and_provenance_are_separate(self):
        root, rows = self.prepare()
        before = copy.deepcopy(rows)
        with patch.object(profile, 'ORIGINAL_CONFIG_SHA', profile.digest(CONTROLLED)):
            derived, record = profile.apply(root, rows, canonical_port=39123)
        self.assertEqual(rows, before)
        changed = next(row for row in derived if row['path']=='next.config.ts')
        self.assertNotIn('gitBlob', changed)
        self.assertEqual(changed['derivedFromGitBlob'], 'controlled-unit-blob')
        self.assertNotEqual(changed['digest'], rows[0]['digest'])
        self.assertEqual(changed['digest'], profile.digest((root/'next.config.ts').read_bytes()))
        self.assertEqual(record['profileDigest'], profile.digest((root/profile.PROFILE_PATH).read_bytes()))
        self.assertFalse(record['upstreamBehaviorClaim'])
        self.assertEqual(stat.S_IMODE((root/profile.PROFILE_PATH).stat().st_mode), 0o644)
        self.assertEqual(json.loads((root/profile.PROFILE_PATH).read_text())['rules'], profile.rules_for_port(39123))


    def test_standalone_output_is_explicit_and_captured(self):
        root, rows = self.prepare()
        before = copy.deepcopy(rows)
        with patch.object(profile, "ORIGINAL_CONFIG_SHA", profile.digest(CONTROLLED)):
            derived, record = profile.apply(root, rows, canonical_port=39123, standalone=True)
        text = (root/"next.config.ts").read_text()
        self.assertIn('qualifiedNextConfig.output = "standalone";\nconst originalRewrites', text)
        self.assertNotIn(chr(92)+"n", text)
        self.assertEqual(record["profile"]["profile"],"patamaps-chatbot-standalone-proxy-3")
        self.assertEqual(record["profile"]["output"],"standalone")
        self.assertEqual(record["profileDigest"],profile.digest((root/profile.PROFILE_PATH).read_bytes()))
        self.assertEqual(record["profile"]["rules"],profile.rules_for_port(39123))
        self.assertEqual(rows,before)
        self.assertEqual(next(v for v in derived if v["path"]=="next.config.ts")["digest"],profile.digest(text.encode()))

    def test_non_boolean_standalone_refuses_before_writes(self):
        root, rows = self.prepare()
        with self.assertRaisesRegex(AssertionError,"STANDALONE_PROFILE"):
            profile.apply(root,rows,canonical_port=39123,standalone="true")
        self.assertEqual((root/"next.config.ts").read_bytes(),CONTROLLED)
        self.assertFalse((root/profile.PROFILE_PATH).exists())

if __name__ == '__main__':
    unittest.main()
