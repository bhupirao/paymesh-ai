"""Offline presentation/history synchronization; no browser or network."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class HistoryStateTests(unittest.TestCase):
    def test_shared_merchant_admin_presentation_lifecycle(self):
        result = subprocess.run(
            ['node', '--experimental-vm-modules', str(ROOT/'frontend/tests/history-state.test.mjs')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for marker in ['# tests 12', '# pass 12', '# fail 0', '# skipped 0']:
            self.assertIn(marker, result.stdout)


if __name__ == '__main__':
    unittest.main()
