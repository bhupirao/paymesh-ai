"""Offline guard/protocol checks, not execution of the real container suite."""
from decimal import Decimal
from unittest.mock import patch
import ast,os,unittest
from pathlib import Path
from ci_fixture_setup import runner_project
from container_e2e import require,Failure,money,Session,Suite
class GuardTests(unittest.TestCase):
    def test_host_invocation_rejected(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):runner_project()
    def test_macos_even_with_ci_variable_rejected(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','RUNNER_OS':'macOS'},clear=True):
            with self.assertRaises(RuntimeError):runner_project()
    def test_exact_disposable_project(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','GITHUB_RUN_ID':'123','GITHUB_RUN_ATTEMPT':'2'},clear=True):self.assertEqual(runner_project(),'paymesh-e2e-123-2')
    def test_untrusted_run_id_rejected(self):
        with patch.dict(os.environ,{'GITHUB_ACTIONS':'true','RUNNER_OS':'Linux','GITHUB_RUN_ID':'../../host','GITHUB_RUN_ATTEMPT':'2'},clear=True):
            with self.assertRaises(RuntimeError):runner_project()
    def test_exact_money(self):self.assertEqual(money('13.25')-money('3.25'),Decimal('10.00'))
    def test_absolute_or_external_paths_rejected_before_network(self):
        for path in ('https://example.test/api/v1/payments','//evil/api/v1/payments','/actuator/env'):
            with self.assertRaises(Failure):Session().call('GET',path)
    def test_fixed_assertion_code(self):
        with self.assertRaisesRegex(Failure,'TEST_ONLY_CODE'):require(False,'TEST_ONLY_CODE')
    def test_http_client_no_automatic_retry(self):
        source=(Path(__file__).parent/'container_e2e.py').read_text();tree=ast.parse(source)
        method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='call')
        self.assertFalse(any(isinstance(n,(ast.For,ast.While)) for n in ast.walk(method)))
    def test_workflow_has_no_registry_or_volume_publication(self):
        source=(Path(__file__).parents[1]/'.github/workflows/container-e2e.yml').read_text()
        self.assertNotIn('docker/login-action',source);self.assertNotIn('push: true',source)
        self.assertNotIn('--volumes',source);self.assertNotIn('down -v',source)
        self.assertIn('DISPOSABLE',source.upper());self.assertIn('workflow_dispatch:',source)
if __name__=='__main__':unittest.main()
