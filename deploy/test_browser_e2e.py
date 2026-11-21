"""Offline browser tooling policy/contract tests: no Docker or real browser."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
HERE=ROOT/'deploy/browser-e2e'
sys.path.insert(0,str(ROOT/'deploy'))
import browser_bootstrap


def yaml(name):
    return json.loads(subprocess.check_output(['ruby','-rjson','-ryaml','-e','puts JSON.generate(YAML.load_file(ARGV[0]))',str(ROOT/name)]))


class BrowserPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow=yaml('.github/workflows/browser-e2e.yml')
        cls.steps=cls.workflow['jobs']['browser']['steps']
        cls.config=(HERE/'playwright.config.js').read_text()
        cls.journey=(HERE/'journey.spec.js').read_text()

    def test_manual_only_main_read_only_hosted_bounded(self):
        self.assertEqual(self.workflow.get('on',self.workflow.get('true')),{'workflow_dispatch':None})
        self.assertEqual(self.workflow['permissions'],{'contents':'read'})
        job=self.workflow['jobs']['browser']
        self.assertEqual(job['runs-on'],'ubuntu-24.04');self.assertEqual(job['timeout-minutes'],55)
        self.assertIn("refs/heads/main",job['if']);self.assertEqual(job['env']['E2E_VERIFY_QWEN'],'true')
        self.assertFalse(self.workflow['concurrency']['cancel-in-progress'])

    def test_actions_use_only_existing_approved_shas(self):
        allowed={'actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803','actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9'}
        for step in self.steps:
            if 'uses' in step:self.assertIn(step['uses'],allowed)
        self.assertFalse(self.steps[0]['with']['persist-credentials'])

    def test_no_build_push_login_environment_secrets_or_paid_services(self):
        source=(ROOT/'.github/workflows/browser-e2e.yml').read_text()
        for forbidden in ['docker build','buildx','login-action','build-push','docker push','secrets.','environment:','workflow_run','schedule:']:
            self.assertNotIn(forbidden,source)
        start=next(s for s in self.steps if s.get('id')=='startup')['run']
        for flag in ['--no-build','--pull never','--wait-timeout 240']:self.assertIn(flag,start)
        self.assertIn('deploy/compose.release-verify.yaml',start)
        self.assertNotIn('build:',(ROOT/'deploy/compose.release-verify.yaml').read_text())

    def test_real_model_download_only_on_runner_checksum_bounded(self):
        step=next(s for s in self.steps if 'checksum-verified Qwen' in s.get('name',''))
        for text in ['--max-filesize 550000000','--max-time 600','sha256sum --check --status','74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db']:
            self.assertIn(text,step['run'])
        self.assertNotIn('--retry',step['run'])

    def test_exact_playwright_dependency_and_integrity_lock(self):
        package=json.loads((HERE/'package.json').read_text());lock=json.loads((HERE/'package-lock.json').read_text())
        self.assertEqual(package['devDependencies'],{'@playwright/test':'1.65.1'})
        self.assertEqual(package['engines'],{'node':'>=22'})
        self.assertEqual(lock['packages']['']['devDependencies'],package['devDependencies'])
        for name in ['@playwright/test','playwright','playwright-core']:
            item=lock['packages']['node_modules/'+name]
            self.assertEqual(item['version'],'1.65.1');self.assertTrue(item['resolved'].startswith('https://registry.npmjs.org/'))
            self.assertTrue(item['integrity'].startswith('sha512-'))
        installation=next(s for s in self.steps if s.get('working-directory')=='deploy/browser-e2e' and 'npm ci' in s.get('run',''))
        self.assertIn('--ignore-scripts',installation['run']);self.assertIn('install --with-deps chromium',installation['run'])

    def test_one_worker_zero_retries_no_sensitive_recording(self):
        for text in ['workers: 1','retries: 0',"browserName: 'chromium'","trace: 'off'","video: 'off'","screenshot: 'off'",'forbidOnly: true']:
            self.assertIn(text,self.config)
        combined='\n'.join(p.read_text() for p in HERE.glob('*.js'))
        for forbidden in ['storageState(','.screenshot(','.tracing.start(','.routeFromHAR(','.request.post(','.request.get(']:self.assertNotIn(forbidden,combined)
        self.assertIn('node_modules/',(HERE/'.gitignore').read_text())

    def test_diagnostics_before_cleanup_and_cleanup_evidence_after(self):
        diagnostic=next(i for i,s in enumerate(self.steps) if s.get('run','').endswith('.py diagnostics'))
        cleanup=next(i for i,s in enumerate(self.steps) if s.get('run','').endswith('.py cleanup'))
        self.assertLess(diagnostic,cleanup);self.assertIn('failure()',self.steps[diagnostic]['if'])
        self.assertIn('always()',self.steps[cleanup]['if']);self.assertEqual(self.steps[cleanup]['timeout-minutes'],5)
        artifact=self.steps[cleanup+1]
        self.assertIn('always()',artifact['if']);self.assertEqual(artifact['with']['if-no-files-found'],'error')
        self.assertEqual(artifact['with']['path'],'${{ env.E2E_DIR }}/sanitized-cleanup.json')

    def test_artifact_allowlist_excludes_browser_output_and_auth(self):
        for step in self.steps:
            if 'upload-artifact@' not in step.get('uses',''):continue
            artifact=step['with'];self.assertEqual(artifact['retention-days'],3)
            self.assertFalse(artifact['include-hidden-files'])
            for line in artifact['path'].splitlines():
                self.assertTrue(any(line.endswith(s) for s in ['sanitized-browser.json','sanitized-browser-bootstrap.json','sanitized-browser-final.json','diagnostics/*.log','diagnostics/status.json','sanitized-cleanup.json']))
                for forbidden in ['.auth','trace','test-results','playwright-report','container.env','secrets']:self.assertNotIn(forbidden,line)

    def test_actual_ui_actions_cover_required_journey(self):
        for stage in ['MERCHANT_REGISTRATION_VALIDATION','ADMIN_LOGIN_AND_NATIVE_APPROVAL','DASHBOARD_SESSION_AND_ROLE_PROTECTION','PAYMENT_CREATION_PROCESSING_AND_LIST','MERCHANT_OWNERSHIP_ISOLATION','NATIVE_INVESTIGATION_REAL_QWEN','PARTIAL_AND_FULL_REFUND_UI','PAYMENT_LINK_AND_CUSTOMER_CHECKOUT','MERCHANT_ADMIN_CHAT_AND_SAVED_HISTORY','CROSS_TAB_LOGOUT_AND_PROTECTED_ROUTE']:
            self.assertIn("test.step('"+stage+"'",self.journey)
        for control in ['#signup-check','#confirm-create','#confirm-process','#confirm-refund','#investigate-button','Confirm approve','Confirm Pay (simulation only)','Rename saved conversation','Delete saved conversation']:
            self.assertIn(control,self.journey)
        self.assertIn('modelSuccess(await body',self.journey);self.assertIn('await p.reload()',self.journey)
        self.assertIn('Shift+Enter',self.journey);self.assertIn('0 accessible matches',self.journey)

    def test_selector_ids_exist_in_actual_frontend(self):
        html=(ROOT/'frontend/index.html').read_text()
        used=set(re.findall(r"locator\('#([a-zA-Z][a-zA-Z0-9-]+)'\)",self.journey))
        for name in used:self.assertIn('id="'+name+'"',html)
        view=(ROOT/'frontend/assets/js/admin/view.js').read_text()
        for label in ['External ownership review reference','Review ','Confirm ','I attest that ownership was reviewed for this exact Merchant.']:self.assertIn(label,view)

    def test_bootstrap_only_seeds_admin_without_replacing_browser_actions(self):
        suite=Mock();suite.folder=Path('/tmp/offline-browser-fixture')
        with patch.object(browser_bootstrap,'ReleaseSuite',return_value=suite),patch.object(browser_bootstrap.os,'open',return_value=9),patch.object(browser_bootstrap.os,'fdopen') as opened:
            self.assertEqual(browser_bootstrap.main('seed'),0)
        self.assertEqual(suite.check.call_count,2)
        self.assertEqual(suite.check.call_args_list[0].args[1],suite.identity)
        self.assertEqual(suite.check.call_args_list[1].args[1],suite.seed)
        suite.authentication.assert_not_called();suite.payment.assert_not_called();suite.ai_and_conversations.assert_not_called()

    def test_final_counts_reject_extra_business_records(self):
        suite=Mock();suite.sql.return_value=json.dumps({'users':99})
        with patch.object(browser_bootstrap,'ReleaseSuite',return_value=suite),self.assertRaises(Exception):browser_bootstrap.main('final')
        self.assertIn('SELECT count(*) FROM payments',suite.sql.call_args.args[0])

    def test_failure_diagnostics_have_no_raw_error_or_artifact_exports(self):
        source=(HERE/'sanitized-reporter.js').read_text()
        for name in ['classifyFailure','HOOK_OR_FIXTURE_SETUP','chromiumLaunchStatus','elapsedMs','timeoutCategory','assertionCategory']:
            self.assertIn(name,source)
        for forbidden in ['JSON.stringify(error','error.stack','result.attachments','error.snippet']:
            self.assertNotIn(forbidden,source)
        self.assertIn("browser.isConnected()",(HERE/'fixtures.js').read_text())
        self.assertIn("browser.browserType().name()==='chromium'",(HERE/'fixtures.js').read_text())
        for step in self.steps:
            if 'upload-artifact@' in step.get('uses',''):
                self.assertNotIn('browser-launch-',step['with']['path'])

    def test_private_output_security_is_descriptor_scoped(self):
        source=(HERE/'fixtures.js').read_text()
        helper=source[source.index('export function privateDirectory('):source.index('export function credential(')]
        for token in ['fs.realpathSync(run)','path.relative(run, folder)','isSymbolicLink()','process.getuid()','O_DIRECTORY','O_NOFOLLOW','fs.fstatSync','fs.fchmodSync(fd, 0o700)','opened.ino === before.ino','after.ino === secured.ino']:
            self.assertIn(token,helper)
        self.assertNotIn('recursive: true',helper)
        self.assertNotIn('fs.chmodSync',helper)
        self.assertNotIn('fs.rm',helper)

    def test_all_fixed_fixture_guards_are_classifiable(self):
        fixture=(HERE/'fixtures.js').read_text()
        reporter=(HERE/'sanitized-reporter.js').read_text()
        allowlist=reporter[reporter.index('const SAFE_ERRORS'):reporter.index('export function classifyFailure')]
        codes=set(re.findall(r",\s*'([A-Z][A-Z0-9_]+)'\s*\)",fixture))
        self.assertIn('PRIVATE_OUTPUT_REQUIRED',codes)
        for code in codes:self.assertIn("'"+code+"'",allowlist)
        self.assertIn('BROWSER_FAILURE_DIAGNOSTIC=',reporter)
        self.assertIn("SAFE_ERRORS.has(firstLine)",reporter)

    def test_js_and_python_syntax(self):
        for source in list(HERE.glob('*.js'))+list(HERE.glob('*.mjs')):subprocess.run(['node','--check',str(source)],check=True,capture_output=True)
        ast.parse((ROOT/'deploy/browser_bootstrap.py').read_text())

    def test_real_offline_helpers_and_reporter(self):
        result=subprocess.run(['node',str(HERE/'offline.test.mjs')],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('# pass 26',result.stdout)
        self.assertNotIn('NATIVE_CHROMIUM_E2E_PASS',result.stdout)


if __name__=='__main__':unittest.main()
