"""Mocked final-closeout checks. Actual supplied timelines, no live I/O."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import phase673_closeout as c
from test_phase673_closeout import fixture

NOW='2026-11-15T00:00:00Z'


def family(at,version,revoked=None,status='ACTIVE',roles='ADMIN'):
    return dict(created_at=at,authorization_version=version,revoked_at=revoked,
                account_status=status,roles_snapshot=roles,absolute_expires_at='2026-12-15T00:00:00Z',idle_expires_at='2026-12-15T00:00:00Z')


def user(version=1,status='ACTIVE'):
    return dict(enabled=True,authorization_version=version,account_status=status)


class FinalAuditTests(unittest.TestCase):
    def test_actual_merchant_timeline_excludes_post_reset_lower_version(self):
        row=family('2026-11-14T18:17:25.621579Z',1,'2026-11-14T18:17:43.246398Z','PENDING_APPROVAL','MERCHANT')
        r=c.session_history(user(2,'PENDING_APPROVAL'),['MERCHANT'],[row],'2026-11-14T18:17:03.513322Z',NOW)
        self.assertEqual('HISTORICAL_EVIDENCE_UNAVAILABLE',r['historicalStatus'])
        self.assertEqual(0,r['retainedPreResetFamilies']);self.assertEqual(1,r['postResetFamilies']);self.assertEqual(0,r['currentEligiblePreResetFamilies'])

    def test_actual_admin_timeline_missing_history_is_not_pass(self):
        row=family('2026-11-14T19:02:21.491717Z',1,'2026-11-14T19:03:52.116685Z')
        r=c.session_history(user(),['ADMIN'],[row],'2026-11-14T19:02:03.361913Z',NOW)
        self.assertEqual('HISTORICAL_EVIDENCE_UNAVAILABLE',r['historicalStatus']);self.assertFalse(r['deletedHistoryReconstructed'])

    def test_valid_current_post_reset_family_need_not_be_revoked(self):
        row=family('2026-11-14T19:02:21Z',1)
        r=c.session_history(user(),['ADMIN'],[row],'2026-11-14T19:02:03Z',NOW)
        self.assertEqual('HISTORICAL_EVIDENCE_UNAVAILABLE',r['historicalStatus']);self.assertEqual(0,r['inconsistentPreResetFamilies'])

    def test_revoked_pre_reset_and_post_signin_classify_separately(self):
        rows=[family('2026-11-14T18:00:00Z',0,'2026-11-14T19:00:00Z'),family('2026-11-14T19:10:00Z',1)]
        r=c.session_history(user(),['ADMIN'],rows,'2026-11-14T19:00:01Z',NOW)
        self.assertEqual('VERIFIED_FROM_RETAINED_ROWS',r['historicalStatus']);self.assertEqual(1,r['postResetFamilies'])

    def test_unrevoked_pre_reset_is_inconsistent_even_if_version_blocks_access(self):
        r=c.session_history(user(),['ADMIN'],[family('2026-11-14T18:00:00Z',0)],'2026-11-14T19:00:00Z',NOW)
        self.assertEqual('REVOCATION_INCONSISTENT',r['historicalStatus']);self.assertEqual(0,r['currentEligiblePreResetFamilies'])

    def test_late_revocation_fails_and_equality_creation_is_ambiguous(self):
        r=c.session_history(user(),['ADMIN'],[family('2026-11-14T18:00:00Z',0,'2026-11-14T19:00:00.000001Z')],'2026-11-14T19:00:00Z',NOW)
        self.assertEqual('REVOCATION_INCONSISTENT',r['historicalStatus'])
        r=c.session_history(user(),['ADMIN'],[family('2026-11-14T19:00:00Z',1)],'2026-11-14T19:00:00Z',NOW)
        self.assertEqual('AMBIGUOUS_BOUNDARY',r['historicalStatus']);self.assertEqual(1,r['currentEligibleBoundaryFamilies'])

    def test_currently_usable_pre_reset_is_current_security_failure(self):
        r=c.session_history(user(),['ADMIN'],[family('2026-11-14T18:00:00Z',1)],'2026-11-14T19:00:00Z',NOW)
        self.assertEqual('CURRENT_SECURITY_FAILURE',r['historicalStatus']);self.assertEqual(1,r['currentEligiblePreResetFamilies'])

    def test_missing_history_strict_modes_fail_final_reports_limitation(self):
        data,targets=fixture()
        data['sessions']=[s for s in data['sessions'] if s['authorization_version']==1]
        for e in data['eligibility']:e['enabled']=False
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,False)
        r=c.audit_accounts(data,targets,False,allow_history_limitations=True)
        self.assertTrue(all(e['historicalStatus']=='HISTORICAL_EVIDENCE_UNAVAILABLE' for e in r.values()))

    def test_final_does_not_accept_active_eligibility_or_unconsumed_grants(self):
        data,targets=fixture()
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,False,allow_history_limitations=True)
        for e in data['eligibility']:e['enabled']=False
        data['grants'][0]['consumed_at']=None
        with self.assertRaises(c.Stop):c.audit_accounts(data,targets,False,allow_history_limitations=True)

    def test_additional_version_increment_not_attributed_to_logout_all(self):
        data,targets=fixture();data['app_users'][2]['authorization_version']=2
        r=c.audit_accounts(data,targets,True,allow_history_limitations=True)
        self.assertEqual('ADDITIONAL_INCREMENT_UNEXPLAINED',r['merchant']['versionHistoryStatus'])
        self.assertEqual([],r['merchant']['possibleVersionAuditEvents'])

    def final_object(self,tmp):
        obj=object.__new__(c.Closeout);obj.private=Path(tmp);obj.baseline_file=Path(tmp)/'phase673-closeout-pre.json'
        obj.deactivation={'startedAt':'2026-11-14T20:00:00Z'};obj.evidence={'recoveryAudit':{}}
        obj.compare_backup=Mock();obj.compare_pre_post=Mock()
        return obj

    def test_final_missing_baseline_is_reported_never_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.final_object(tmp);obj.final_comparisons({})
            self.assertEqual('UNAVAILABLE_NO_SUCCESSFUL_PRE_AUDIT',obj.evidence['comparisons']['preAuditFingerprints'])
            self.assertEqual('UNAVAILABLE',obj.evidence['comparisons']['preDeactivationArchive'])
            self.assertFalse(obj.baseline_file.exists());obj.compare_pre_post.assert_not_called()

    def test_available_deactivation_archive_is_exact_compared_not_mislabeled_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.final_object(tmp);archive=Path(tmp)/'archive';archive.write_bytes(b'fixture')
            obj.deactivation['backup']={'path':str(archive)};obj.final_comparisons({})
            obj.compare_backup.assert_called_once_with({},backup={'path':str(archive)},exact_accounts=True,label='preDeactivation')
            self.assertEqual('UNAVAILABLE_NOT_RECORDED',obj.evidence['comparisons']['activationDeactivationFingerprints'])

    def test_fingerprint_requires_successful_authentic_pre_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.final_object(tmp);obj.baseline_file.write_text(json.dumps({'collectedAt':'2026-11-14T19:00:00Z'}));obj.baseline_file.chmod(0o600)
            with self.assertRaises(c.Stop):obj.final_comparisons({})
            directory=Path(tmp)/'otp-step17-verify-pre-test';directory.mkdir()
            file=directory/'evidence.json';file.write_text(json.dumps(dict(success=True,mode='verify-pre',stage='read-only-pre-verified',preBaselineReference=str(obj.baseline_file),startedAt='2026-11-14T18:59:00Z')));file.chmod(0o600)
            obj.final_comparisons({});obj.compare_pre_post.assert_called_once()
            self.assertEqual('VERIFIED_AUTHENTIC_BASELINE',obj.evidence['comparisons']['preAuditFingerprints'])
            record=json.loads(file.read_text());record['success']=False;file.write_text(json.dumps(record))
            with self.assertRaises(c.Stop):obj.final_comparisons({})

    def test_full_mocked_final_mode_already_disabled_without_pre_baseline(self):
        import contextlib,io,uuid
        data,targets=fixture()
        data['sessions']=[s for s in data['sessions'] if s['authorization_version']==1]
        for e in data['eligibility']:e['enabled']=False
        for i in range(3):
            data['app_users'].append(dict(user_id=str(uuid.uuid4()),login_normalized='extra'+str(i),authorization_version=0))
            data['merchants'].append(dict(merchant_id='extra'+str(i)))
            data['merchant_memberships'].append(dict(user_id='extra'+str(i)))
        data['merchant_registrations'].append(dict(user_id='extra'))
        data['payments']=[{} for _ in range(6)];data['refunds']=[{} for _ in range(4)]
        with tempfile.TemporaryDirectory() as tmp:
            obj=self.final_object(tmp);obj.phase='final';obj.targets=targets
            obj.read_evidence=Mock();obj.preflight=Mock();obj.before=list(c.COUNTS);obj.enabled_before=False
            obj.flags={'paymesh.demo.password-recovery.enabled':'false'}
            obj.services={k:dict(pid='1',start='test') for k in ('java','frontend','ai','llm')}
            obj.activation={'beforeServices':obj.services};obj.deactivation={'newJavaPid':1,'artifactSha256':'reviewed'};obj.jar_sha='reviewed'
            obj.repo=Path(tmp);obj.snapshot=Mock(return_value=data);obj.unchanged_other_services=Mock();obj.service=Mock(return_value=obj.services['java'])
            obj.http_json=Mock(side_effect=lambda path:(200,{'localDemoEnabled':False} if 'capabilities' in path else {'status':'UP'}))
            obj.http=Mock();response=Mock(status=200);obj.http.open.return_value.__enter__=Mock(return_value=response);obj.http.open.return_value.__exit__=Mock(return_value=False)
            with contextlib.redirect_stdout(io.StringIO()):obj.run()
            self.assertEqual('VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS',obj.evidence['result'])
            self.assertIsNone(obj.evidence['preBaselineReference']);self.assertFalse(obj.baseline_file.exists())
            self.assertEqual('HISTORICAL_EVIDENCE_UNAVAILABLE',obj.evidence['recoveryAudit']['admin']['historicalStatus'])
            obj.enabled_before=True
            with self.assertRaises(c.Stop):obj.run()

    def test_final_audit_never_calls_mutation_or_auth_http(self):
        import ast
        tree=ast.parse(Path(c.__file__).read_text())
        forbidden={'restart','eligibility','backup','reviewer','create_admin','prepare_accounts'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
                self.assertNotIn(node.func.attr,forbidden)
                if node.func.attr=='http_json':self.assertEqual(1,len(node.args));self.assertFalse(node.keywords)

if __name__=='__main__':unittest.main()
