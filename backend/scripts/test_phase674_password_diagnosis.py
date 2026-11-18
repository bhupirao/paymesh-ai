"""Mocked diagnostic evidence only; no database, service, credential or archive access."""
import json
from pathlib import Path
import unittest
import phase674_password_diagnosis as d
from test_phase674_closeout import fixture
from phase674_closeout import evaluate
from phase673_otp_ops import REVIEWER

class PasswordDiagnosisTests(unittest.TestCase):
    targets={'admin':'1','merchant':'5'}
    def analyze(self,s,b):return d.analyze(s,b,self.targets,s['baselineAt'])
    def password_event(self,s,uid='1'):
        u=next(u for u in s['app_users'] if u['user_id']==uid)
        s['audit'].append(dict(event_type='ADMIN_PASSWORD_CHANGED',resource_id=uid,resource_type='ACCOUNT',outcome='SUCCESS',occurred_at='2026-11-15T09:00:00Z',actor_user_id=uid,actor_identifier=u['login_normalized'],metadata={}))
        return u
    def test_documented_disposable_changes_do_not_match_failure(self):
        s,b=fixture();u=self.password_event(s);u['password_hash']='new-admin-synthetic-hash';u['authorization_version']+=1
        r=self.analyze(s,b);self.assertEqual([],r['accountsMatchingExactVerifierFailure'])
        for login in (d.ADMIN,d.MERCHANT):self.assertEqual('MATCHES_DOCUMENTED_DISPOSABLE_ACTIVITY_AND_AUDIT',next(x for x in r['accounts'] if x['login']==login)['explanation'])
        with self.assertRaises(d.Stop):evaluate(s,b) # Final scope now requires independent authorization for any Admin change.
    def test_operational_admin_change_matches_exact_strict_failure(self):
        s,b=fixture();u=self.password_event(s,'0');u['password_hash']='unexpected-new-hash';u['authorization_version']+=1
        r=self.analyze(s,b);self.assertEqual([REVIEWER],r['accountsMatchingExactVerifierFailure']);self.assertIn(REVIEWER,r['accountsRequiringOperatorExplanation'])
        with self.assertRaisesRegex(d.Stop,'Unexpected operational account password change; documented review required'):evaluate(s,b)
    def test_event_target_check_can_fail_without_hash_inequality(self):
        s,b=fixture();self.password_event(s,'0')
        r=self.analyze(s,b);row=next(x for x in r['accounts'] if x['login']==REVIEWER)
        self.assertEqual('NO',row['passwordHashChanged']);self.assertEqual([REVIEWER],r['accountsMatchingExactVerifierFailure'])
        with self.assertRaisesRegex(d.Stop,'Unexpected operational account password change'):evaluate(s,b)
    def test_lifecycle_versions_are_not_password_changes(self):
        s,b=fixture();s['app_users'][5]['password_hash']=b['app_users'][5]['password_hash']
        r=self.analyze(s,b);row=next(x for x in r['accounts'] if x['login']==d.MERCHANT)
        self.assertEqual('NO',row['passwordHashChanged']);self.assertEqual(3,len(row['lifecycleAuditEvents']));self.assertEqual(2,row['previousAuthorizationVersion']);self.assertEqual(6,row['currentAuthorizationVersion'])
    def test_missing_or_wrong_actor_does_not_explain_disposable_change(self):
        s,b=fixture();u=self.password_event(s);u['password_hash']='new';s['audit'][-1]['actor_user_id']='0'
        row=next(x for x in self.analyze(s,b)['accounts'] if x['login']==d.ADMIN)
        self.assertEqual('UNEXPLAINED_OR_NOT_AUTHORIZED_BY_DOCUMENTED_SCOPE',row['explanation'])
    def test_manifest_mismatch_fails_closed(self):
        s,b=fixture()
        with self.assertRaises(d.Stop):d.analyze(s,b,{'admin':'0','merchant':'5'},s['baselineAt'])
    def test_no_hash_or_raw_metadata_in_diagnostic_result(self):
        s,b=fixture();s['audit'][1]['metadata']['unused_private_fixture']='do-not-print-fixture'
        raw=json.dumps(self.analyze(s,b));self.assertNotIn('synthetic-hash',raw);self.assertNotIn('new-synthetic-hash',raw);self.assertNotIn('do-not-print-fixture',raw);self.assertNotIn('password_hash',raw)
    def test_unlogged_operational_hash_change_requires_review(self):
        s,b=fixture();s['app_users'][2]['password_hash']='new';r=self.analyze(s,b)
        self.assertIn('merchant-a',r['accountsRequiringOperatorExplanation']);self.assertEqual([],r['accountsMatchingExactVerifierFailure'])
    def test_no_activation_baseline_for_new_rejected_account(self):
        s,b=fixture(True);r=self.analyze(s,b);row=next(x for x in r['accounts'] if x['login']=='reject-demo@example.test');self.assertEqual('NOT_COMPARABLE_NEW_ACCOUNT',row['passwordHashChanged'])
    def test_readonly_guard_rejects_write(self):
        obj=object.__new__(d.Diagnosis)
        with self.assertRaises(d.Stop):obj.sql('SELECT 1',write=True)
    def test_no_mutation_or_original_database_path(self):
        source=Path(d.__file__).read_text()
        for token in ('self.restart(', 'self.backup(', 'write=True', 'os.kill(', 'paymesh_db', ':8080','mvn '):self.assertNotIn(token,source)

if __name__=='__main__':unittest.main()
