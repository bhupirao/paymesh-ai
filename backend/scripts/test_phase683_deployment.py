import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import phase683_deployment as d
class CombinedDeploymentTests(unittest.TestCase):
 def test_distinct_evidence_and_explicit_confirmation(self):
  s=Path(d.__file__).read_text();self.assertIn("super().__init__('activate-phase682-683')",s);self.assertIn('ACTIVATE_PHASE682_683_V12_V13_OTP_DISABLED',s);self.assertIn('ENABLE_PRIVATE_CHECKOUT_CONTROLS',s);self.assertIn('NO_PUBLIC_PROXY_OR_TUNNEL',s)
 def test_v11_to_v13_only_and_empty_checkout_tables(self):
  s=Path(d.__file__).read_text();self.assertIn('set(range(1, 14))',s);self.assertIn('1,2,3,4,5,6,7,8,9,10,11|true',s);self.assertIn('1,2,3,4,5,6,7,8,9,10,11,12,13|true',s);self.assertIn("!='0|0'",s);self.assertLess(s.index('self.backup()'),s.index('self.restart(False)'));self.assertIn('merchant_administration',s);self.assertIn("'app_users'",s)
 def test_stops_before_any_change_on_unreviewed_startup_override(self):
  op=object.__new__(d.Deployment);op.env={'JAVA_TOOL_OPTIONS':'unexpected'};op.stage='';op.backup=Mock();op.restart=Mock()
  with self.assertRaises(d.Stop):op.run()
  op.backup.assert_not_called();op.restart.assert_not_called()
 def test_otp_disabled_service_preservation_and_no_pay_requests(self):
  s=Path(d.__file__).read_text();self.assertIn('localDemoEnabled',s);self.assertIn('self.unchanged_other_services()',s);self.assertIn('[6,4,4,2,6,4]',s);self.assertNotIn('/pay\'',s);self.assertNotIn('write=True',s);self.assertIn('no automatic rollback/retry',s)

class CombinedPreflightBehaviorTests(unittest.TestCase):
 def stopped(self,case):
  import tempfile
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);(root/'.git').mkdir();(root/'.git/index').write_bytes(b'test-index')
   op=object.__new__(d.Deployment);op.repo=root;op.private=root/'private';op.env={k:'test-only' for k in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN')};op.evidence={};op.stage='';op.flags={'paymesh.demo.password-recovery.enabled':'false'}
   op.service=Mock(return_value={'pid':'123'});op.launch=Mock();op.command=Mock(return_value='PostgreSQL 16.3');op.backup=Mock();op.restart=Mock();op.counts=Mock(return_value=[6,4,4,2,6,4] if case!='counts' else [7,4,4,2,6,4]);op.http_json=Mock(return_value=(200,{'localDemoEnabled':case=='otp'}))
   def sql(query):
    if query.startswith('SELECT current_database()'):return 'wrong|target|127.0.0.1|5432' if case=='identity' else 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432'
    if 'string_agg(version' in query:return '1,2,3|true' if case=='history' else '1,2,3,4,5,6,7,8,9,10,11|true'
    if 'to_regclass' in query:return 't'
    return '0'
   op.sql=Mock(side_effect=sql)
   with patch.object(d,'protected'),patch.object(d,'hidden',return_value='test-only'):
    with self.assertRaises(d.Stop):op.run()
   op.backup.assert_not_called();op.restart.assert_not_called()
 def test_wrong_actual_identity_stops_before_backup_or_restart(self):self.stopped('identity')
 def test_wrong_migration_baseline_stops_before_backup_or_restart(self):self.stopped('history')
 def test_otp_enabled_stops_before_backup_or_restart(self):self.stopped('otp')
 def test_changed_counts_stop_before_backup_or_restart(self):self.stopped('counts')

if __name__=='__main__':unittest.main()
