"""Offline bootstrap regressions; no real browser, upstream or database."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]


class SessionBootstrapTests(unittest.TestCase):
    def test_actual_bootstrap_router_and_bookmark_module_graph(self):
        result = subprocess.run(
            ['node', '--experimental-vm-modules', str(ROOT/'frontend/tests/session-bootstrap.test.mjs')],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for marker in ['# tests 13', '# pass 13', '# fail 0', '# skipped 0']:
            self.assertIn(marker, result.stdout)

    def test_restore_finishes_before_router_and_eager_store_construction(self):
        source = (ROOT/'frontend/assets/js/app.js').read_text()
        restore = source.index('await persistence.restore()')
        for construction in ['const workspace = createWorkspace(', 'const detailsUI = mountRefunds(',
                             'paymentChatUI=mountPaymentAI(', 'portalUI = mountPortals(']:
            self.assertLess(restore, source.index(construction))
        self.assertEqual(source.count('installPersistence()'), 1)
        self.assertEqual(source.count('persistence.restore()'), 1)
        self.assertIn("clearSession('refresh-failed')", source)
        self.assertNotIn('localStorage', source)
        self.assertNotIn('sessionStorage', source)
        self.assertNotIn('history.state =', source)


if __name__ == '__main__':
    unittest.main()
