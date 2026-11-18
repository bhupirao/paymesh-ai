"""Deployment preparation checks; no live operations."""
import unittest,tempfile
from pathlib import Path
from unittest.mock import Mock,patch
import phase681_deployment as d
class DeploymentTests(unittest.TestCase):
    def test_existing_v11_only_and_exact_operator_gate(self):
        s=Path(d.__file__).read_text();self.assertIn("history!='1,2,3,4,5,6,7,8,9,10,11|true'",s);self.assertIn('DEPLOY_PHASE681_V11_OTP_DISABLED',s);self.assertIn('MerchantPortalController.class',s);self.assertNotIn('flyway.repair',s)
    def test_safe_content_fingerprints_are_read_only(self):
        x=object.__new__(d.Deployment);x.sql=Mock(return_value='fixture');self.assertEqual(13,len(x.integrity()))
        for call in x.sql.call_args_list:self.assertTrue(call.args[0].startswith('SELECT '));self.assertNotIn('password_hash',call.args[0])
    def test_backup_before_restart_and_financial_count_checks_remain(self):
        s=Path(d.__file__).read_text();self.assertLess(s.index('self.backup()'),s.index('self.restart(False)'));self.assertIn('[6,4,4,2,6,4]',s);self.assertIn('self.unchanged_other_services()',s);self.assertIn("'false'",s)
    def test_preflight_failures_never_backup_or_restart(self):
        for broken in ('target','history','otp','counts','confirmation'):
            with tempfile.TemporaryDirectory() as tmp:
                obj=object.__new__(d.Deployment);obj.repo=Path(tmp);obj.private=Path(tmp);obj.evidence={};(obj.repo/'.git').mkdir();(obj.repo/'.git/index').write_bytes(b'fixture')
                obj.env={k:'test-only' for k in ('PAYMESH_JWT_ISSUER','PAYMESH_JWT_AUDIENCE','PAYMESH_RAZORPAY_WEBHOOK_SECRET','PAYMESH_STRIPE_WEBHOOK_SECRET','PAYMESH_SETTLEMENT_ADMIN_TOKEN')}
                obj.service=Mock(return_value={'pid':'1'});obj.launch=Mock(side_effect=lambda:setattr(obj,'flags',{'paymesh.demo.password-recovery.enabled':'false'}));obj.command=Mock(side_effect=lambda args,**kw:'PostgreSQL 16.3' if '--version' in args else 'fixture')
                def sql(q):
                    if 'current_database()' in q:return 'wrong' if broken=='target' else 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432'
                    if 'string_agg(version' in q:return 'wrong' if broken=='history' else '1,2,3,4,5,6,7,8,9,10,11|true'
                    return '0'
                obj.sql=Mock(side_effect=sql);obj.http_json=Mock(return_value=(200,{'localDemoEnabled':broken=='otp'}));obj.counts=Mock(return_value=[0]*6 if broken=='counts' else [6,4,4,2,6,4]);obj.integrity=Mock(return_value={});obj.backup=Mock();obj.restart=Mock()
                with patch.object(d,'protected',side_effect=lambda p,*a:p),patch.object(d,'hidden',return_value='synthetic'),patch('builtins.input',return_value='NO' if broken=='confirmation' else 'DEPLOY_PHASE681_V11_OTP_DISABLED'):
                    with self.assertRaises(d.Stop):obj.run()
                obj.backup.assert_not_called();obj.restart.assert_not_called()

if __name__=='__main__':unittest.main()
