"""Mocked operational checks. No DB, credential, listener, or live HTTP access."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
import urllib.error
import uuid

spec = importlib.util.spec_from_file_location('otp_ops', Path(__file__).with_name('phase673_otp_ops.py'))
ops = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ops)

class OperationalTests(unittest.TestCase):
    def instance(self):
        obj = object.__new__(ops.Ops)
        obj.stage = 'test'
        obj.evidence = {}
        return obj

    def admin(self):
        return {'id': str(uuid.uuid4()), 'enabled': True, 'status': 'ACTIVE', 'roles': ['ADMIN']}

    def test_authenticated_admin_provisioning_uses_exact_api_and_no_secret_output(self):
        obj = self.instance(); account = self.admin(); obj.account = Mock(return_value=account)
        obj.http_json = Mock(return_value=(201, dict(userId=account['id'], login=ops.ADMIN, enabled=True, accountStatus='ACTIVE', roles=['ADMIN'])))
        secret = 'test-only-private-password'; token = 'test-only-JWT'
        output = io.StringIO()
        with patch('builtins.input', return_value='CREATE_OTP_ADMIN'), patch.object(ops, 'hidden', side_effect=[secret, secret]), contextlib.redirect_stdout(output):
            self.assertEqual(account, obj.create_admin(token))
        obj.http_json.assert_called_once_with('/api/v1/admin/accounts', {'login': ops.ADMIN, 'password': secret, 'confirmPassword': secret}, bearer=token)
        self.assertNotIn(secret, output.getvalue()); self.assertNotIn(token, output.getvalue())
        self.assertNotIn(secret, json.dumps(obj.evidence)); self.assertNotIn(token, json.dumps(obj.evidence))

    def test_wrong_confirmation_prevents_any_request(self):
        obj = self.instance(); obj.http_json = Mock()
        with patch('builtins.input', return_value='CREATE_OTP_ADMIN'), patch.object(ops, 'hidden', side_effect=['test-only-long-password', 'different-long-password']):
            with self.assertRaises(ops.Stop): obj.create_admin('private-token')
        obj.http_json.assert_not_called()

    def test_all_api_errors_stop_without_retry_or_overwrite(self):
        for status in (400, 401, 403, 404, 409, 413, 503):
            obj = self.instance(); obj.http_json = Mock(return_value=(status, {'unsafe': 'private-body'})); obj.account = Mock()
            with patch('builtins.input', return_value='CREATE_OTP_ADMIN'), patch.object(ops, 'hidden', return_value='test-only-long-password'):
                with self.assertRaises(ops.Stop) as error: obj.create_admin('private-token')
            self.assertNotIn('private-body', str(error.exception)); self.assertNotIn('private-token', str(error.exception))
            self.assertEqual(1, obj.http_json.call_count); obj.account.assert_not_called()

    def test_network_uncertainty_has_no_second_submission(self):
        obj = self.instance(); obj.http_json = Mock(side_effect=ops.Stop('Unconfirmed test outcome.'))
        with patch('builtins.input', return_value='CREATE_OTP_ADMIN'), patch.object(ops, 'hidden', return_value='test-only-long-password'):
            with self.assertRaises(ops.Stop): obj.create_admin('private-token')
        self.assertEqual(1, obj.http_json.call_count)

    def test_mismatched_response_or_wrong_role_stops(self):
        for changed in ('id', 'roles', 'status'):
            obj = self.instance(); account = self.admin()
            response = dict(userId=account['id'], login=ops.ADMIN, enabled=True, accountStatus='ACTIVE', roles=['ADMIN'])
            if changed == 'id': response['userId'] = str(uuid.uuid4())
            if changed == 'roles': account['roles'] = ['MERCHANT']
            if changed == 'status': account['status'] = 'PENDING_APPROVAL'
            obj.http_json = Mock(return_value=(201, response)); obj.account = Mock(return_value=account)
            with patch('builtins.input', return_value='CREATE_OTP_ADMIN'), patch.object(ops, 'hidden', return_value='test-only-long-password'):
                with self.assertRaises(ops.Stop): obj.create_admin('private-token')

    def test_http_places_secrets_only_in_header_body_and_drops_raw_errors(self):
        obj = self.instance(); obj.http = Mock(); obj.http.open.side_effect = urllib.error.HTTPError('ignored', 403, 'private-error', {}, io.BytesIO(b'private-body'))
        self.assertEqual((403, {}), obj.http_json('/api/v1/admin/accounts', {'password': 'private-password'}, bearer='private-token'))
        request = obj.http.open.call_args.args[0]
        self.assertEqual('http://127.0.0.1:18080/api/v1/admin/accounts', request.full_url)
        self.assertNotIn('private', request.full_url)
        self.assertEqual('Bearer private-token', request.get_header('Authorization'))
        self.assertIsNone(request.get_header('Cookie')); self.assertIsNone(request.get_header('Origin'))
        self.assertEqual({'password': 'private-password'}, json.loads(request.data))

    def test_eligibility_is_exactly_scoped_and_invalidates_grants(self):
        obj = self.instance(); obj.sql = Mock()
        state = {'admin': str(uuid.uuid4()), 'merchant': str(uuid.uuid4())}
        obj.eligibility(state, False)
        sql = obj.sql.call_args.args[0]
        self.assertIn(state['admin'], sql); self.assertIn(state['merchant'], sql)
        self.assertIn('pg_advisory_xact_lock', sql); self.assertIn('password_reset_authorizations SET consumed_at', sql)
        for forbidden in ('UPDATE public.app_users', 'password_hash', 'DELETE FROM', 'payments', 'refunds'):
            self.assertNotIn(forbidden, sql)

    def test_deploy_does_not_provision_and_requires_disabled_gate(self):
        obj = self.instance(); obj.mode = 'deploy'; obj.preflight = Mock(); obj.enabled_before = False
        obj.sql = Mock(return_value='0'); obj.before = list(ops.BASELINE); obj.counts = Mock(return_value=list(ops.BASELINE))
        obj.backup = Mock(); obj.restart = Mock(); obj.http_json = Mock(return_value=(200, {})); obj.prepare_accounts = Mock()
        with patch('builtins.input', return_value='DEPLOY_ADMIN_API_OTP_DISABLED'): obj.run()
        obj.backup.assert_called_once(); obj.restart.assert_called_once_with(False); obj.prepare_accounts.assert_not_called()
        obj.enabled_before = True; obj.backup.reset_mock(); obj.restart.reset_mock()
        with self.assertRaises(ops.Stop): obj.run()
        obj.backup.assert_not_called(); obj.restart.assert_not_called()

    def test_admin_creation_requires_backup_and_real_reviewer_and_skips_existing(self):
        for exists in (True, False):
            obj = self.instance(); admin = self.admin(); merchant = dict(id=str(uuid.uuid4()), enabled=True, status='PENDING_APPROVAL', roles=['MERCHANT'])
            reviewer = dict(id=str(uuid.uuid4()), version=1, expires=9999999999)
            obj.enabled_before = False; obj.before = [5 + exists, 4, 4, 2, 6, 4]
            obj.account = Mock(side_effect=lambda name: merchant if name == ops.MERCHANT else (admin if exists else None))
            order = []
            obj.backup = Mock(side_effect=lambda: order.append('backup'))
            obj.reviewer = Mock(side_effect=lambda: (order.append('reviewer') or (reviewer, 'private-token')))
            obj.create_admin = Mock(side_effect=lambda token: (order.append('api') or admin))
            obj.sql = Mock(side_effect=['0', '1', '1']); obj.counts = Mock(return_value=[6,4,4,2,6,4])
            obj.private_json = Mock()
            with tempfile.TemporaryDirectory() as tmp:
                obj.manifest = Path(tmp) / 'manifest.json'
                with patch('builtins.input', return_value='DISPOSABLE_OTP_ACCOUNTS_ONLY'):
                    state = obj.prepare_accounts()
            self.assertEqual(['backup', 'reviewer'] + ([] if exists else ['api']), order)
            self.assertEqual(admin['id'], state['admin']); self.assertNotIn('private-token', json.dumps(state))
            if exists: obj.create_admin.assert_not_called()
            else: obj.create_admin.assert_called_once_with('private-token')

if __name__ == '__main__':
    unittest.main()
