"""Mocked read-only closeout; never connects to services or PostgreSQL."""
import copy
from pathlib import Path
import unittest
from unittest.mock import Mock
import phase674_closeout as v

def fixture(reject=False):
    t='2026-11-15T04:00:00+00:00'
    users=[];roles=[];merchants=[];members=[];registrations=[]
    for i,name in enumerate((v.REVIEWER,v.ADMIN,'merchant-a','merchant-b','pending@example.test',v.MERCHANT)):
        admin=i<2;uid=str(i);mid='m'+str(i)
        users.append(dict(user_id=uid,login_normalized=name,enabled=True,account_status='ACTIVE' if i<4 else 'PENDING_APPROVAL',authorization_version=1 if i<2 else 2 if i==5 else 0,created_at=t,updated_at=t,password_hash='synthetic-hash'))
        roles.append(dict(user_id=uid,role_name='ADMIN' if admin else 'MERCHANT'))
        if not admin:
            merchants.append(dict(merchant_id=mid,verified=i<4,active=i<4,verified_by='0' if i<4 else None,verified_at=t if i<4 else None))
            members.append(dict(user_id=uid,merchant_id=mid,active=i<4))
            if i>=4:registrations.append(dict(user_id=uid,merchant_id=mid,email=name))
    base=dict(app_users=users,user_roles=roles,merchants=merchants,merchant_memberships=members,merchant_registrations=registrations,payments=[{}]*6,refunds=[{}]*4)
    s=copy.deepcopy(base);s.update(collectedAt='2026-11-15T10:00:00Z',baselineAt='2026-11-15T05:00:00Z',eligibility=[],sessions=[],challenges=[],grants=[],audit=[],lifecycle=[])
    for m in s['merchants']:
        s['lifecycle'].append(dict(merchant_id=m['merchant_id'],status='ACTIVE' if m['active'] else 'PENDING_APPROVAL',approved_at=m['verified_at'],approved_by=m['verified_by'],review_reference=None,reason=None))
    u=s['app_users'][5];u['account_status']='ACTIVE';u['authorization_version']=6;u['password_hash']='new-synthetic-hash'
    m=s['merchants'][3];m.update(verified=True,active=True,verified_by='0',verified_at='2026-11-15T06:00:00Z');s['merchant_memberships'][3]['active']=True
    s['lifecycle'][3].update(status='ACTIVE',approved_at=m['verified_at'],approved_by='0',review_reference='review-test')
    def audit(kind,at,resource='5',rtype='ACCOUNT',metadata=None,offline=False):
        return dict(event_type=kind,occurred_at=at,resource_id=resource,resource_type=rtype,outcome='SUCCESS',actor_user_id=None if offline else '0',actor_identifier=None if offline else v.REVIEWER,metadata=metadata or {})
    s['audit']=[audit('LOCAL_DEMO_PASSWORD_RESET',t,offline=True),audit('DISPOSABLE_MERCHANT_PASSWORD_RECOVERED','2026-11-15T05:30:00Z',metadata={'source':'offline_operator_recovery'},offline=True)]
    for kind,at,fr,to in [('APPROVE','06:00:01','PENDING_APPROVAL','ACTIVE'),('SUSPEND','07:00:01','ACTIVE','SUSPENDED'),('REACTIVATE','08:00:01','SUSPENDED','ACTIVE')]:
        meta=dict(from_=fr,to=to);meta['from']=meta.pop('from_')
        meta.update(dict(ownershipAttested=True,reviewReference='review-test') if kind=='APPROVE' else dict(reason='operator test'))
        s['audit'].append(audit('MERCHANT_'+kind,'2026-11-15T'+at+'Z','m5','MERCHANT',meta))
    if reject:
        s['app_users'].append(dict(user_id='6',login_normalized=v.REJECT,enabled=True,account_status='REJECTED',authorization_version=1,created_at=t,updated_at=t,password_hash='test'))
        s['user_roles'].append(dict(user_id='6',role_name='MERCHANT'))
        s['merchants'].append(dict(merchant_id='m6',verified=False,active=False,verified_by=None,verified_at=None))
        s['merchant_memberships'].append(dict(user_id='6',merchant_id='m6',active=False))
        s['merchant_registrations'].append(dict(user_id='6',merchant_id='m6',email=v.REJECT))
        s['lifecycle'].append(dict(merchant_id='m6',status='REJECTED',approved_at=None,approved_by=None,review_reference=None,reason='test rejection'))
        s['audit'].append(audit('MERCHANT_REJECT','2026-11-15T09:00:01Z','m6','MERCHANT',dict(reason='test rejection',**{'from':'PENDING_APPROVAL','to':'REJECTED'})))
    return s,base

def family(created='2026-11-15T05:00:00Z',version=2,revoked='2026-11-15T05:29:59Z',status='PENDING_APPROVAL'):
    return dict(user_id='5',created_at=created,authorization_version=version,revoked_at=revoked,account_status=status,roles_snapshot='MERCHANT',absolute_expires_at='2026-11-16T00:00:00Z',idle_expires_at='2026-11-16T00:00:00Z')

class CloseoutTests(unittest.TestCase):
    def test_counts_without_rejection(self):
        s,b=fixture();self.assertEqual([6,4,4,2,6,4],v.evaluate(s,b)['actualCounts'])
    def test_counts_with_rejection(self):
        s,b=fixture(True);self.assertEqual([7,5,5,3,6,4],v.evaluate(s,b)['actualCounts'])
    def test_unexpected_account_counts(self):
        s,b=fixture();s['payments'].append({})
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_invalid_lifecycle(self):
        for field in ('enabled','account_status'):
            s,b=fixture();s['app_users'][5][field]=False if field=='enabled' else 'SUSPENDED'
            with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_missing_each_required_audit(self):
        for kind in ('MERCHANT_APPROVE','MERCHANT_SUSPEND','MERCHANT_REACTIVATE','DISPOSABLE_MERCHANT_PASSWORD_RECOVERED','LOCAL_DEMO_PASSWORD_RESET'):
            s,b=fixture();s['audit']=[e for e in s['audit'] if e['event_type']!=kind]
            with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_wrong_actor_and_attestation(self):
        for mutate in (lambda e:e.update(actor_user_id=None),lambda e:e['metadata'].update(ownershipAttested=False),lambda e:e['metadata'].update(reviewReference='changed')):
            s,b=fixture();mutate(s['audit'][2])
            with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_otp_enabled_and_usable_grant_rejected(self):
        for key,row in [('eligibility',{'enabled':True}),('challenges',{'consumed_at':None,'expires_at':'2026-11-16T00:00:00Z'}),('grants',{'consumed_at':None,'expires_at':'2026-11-16T00:00:00Z'})]:
            s,b=fixture();s[key]=[row]
            with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_other_pending_registration_unchanged(self):
        s,b=fixture();s['app_users'][4]['account_status']='ACTIVE'
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_old_operational_password_change_not_silently_allowed(self):
        s,b=fixture();s['app_users'][0]['password_hash']='different'
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_missing_history_is_limitation(self):
        s,b=fixture();r=v.evaluate(s,b);self.assertIn('WITH_DOCUMENTED_EVIDENCE_LIMITATIONS',r['result']);self.assertTrue(all(x['historicalStatus']=='HISTORICAL_EVIDENCE_UNAVAILABLE' for x in r['sessionEvents']))
    def session(self,row,version=3):
        s,b=fixture();return v.event_sessions(s['app_users'][5],['MERCHANT'],[row],s['audit'][1],version,s['collectedAt'])
    def test_lower_version_post_event_not_pre(self):
        r=self.session(family(created='2026-11-15T05:31:00Z'));self.assertEqual(0,r['retainedPreEventFamilies']);self.assertEqual(1,r['postEventFamilies'])
    def test_valid_post_event_session_not_required_revoked(self):
        r=self.session(family(created='2026-11-15T09:00:00Z',version=6,revoked=None,status='ACTIVE'));self.assertEqual('HISTORICAL_EVIDENCE_UNAVAILABLE',r['historicalStatus'])
    def test_revoked_pre_event(self):self.assertEqual('VERIFIED_FROM_RETAINED_ROWS',self.session(family())['historicalStatus'])
    def test_unrevoked_and_late_revocation(self):
        for at in (None,'2026-11-15T05:30:01Z'):self.assertEqual('REVOCATION_INCONSISTENT',self.session(family(revoked=at))['historicalStatus'])
    def test_boundary_and_version_ambiguity(self):
        self.assertEqual('AMBIGUOUS_BOUNDARY',self.session(family(created='2026-11-15T05:30:00Z'))['historicalStatus'])
        self.assertEqual('AMBIGUOUS_BOUNDARY',self.session(family(version=6))['historicalStatus'])
    def test_current_usable_pre_event_detected(self):
        r=self.session(family(version=6,revoked=None,status='ACTIVE'),version=7);self.assertEqual('CURRENT_SECURITY_FAILURE',r['historicalStatus'])
    def test_additional_increment_reported_not_invented(self):
        s,b=fixture();s['app_users'][1]['authorization_version']+=1;
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_read_only_sql_wrapper_rejects_write(self):
        obj=object.__new__(v.FinalAudit)
        with self.assertRaises(v.Stop):obj.sql('SELECT 1',write=True)
    def test_financial_mismatch_fails_archive_comparison(self):
        obj=object.__new__(v.FinalAudit);obj.activation={'backup':{'path':'fixture','sha256':'invalid'}};obj.private=Path('/tmp');obj.command=Mock()
        from unittest.mock import patch
        with patch.object(v,'protected',return_value=Path(__file__)):
            with self.assertRaises(v.Stop):obj.archive({})
        obj.command.assert_not_called()
    def test_exact_financial_comparison_not_only_counts(self):
        cols=['amount','status'];types={'amount':'numeric','status':'text'}
        v.compare_financial([{'amount':'25.00','status':'SUCCESS'}],[{'amount':25,'status':'SUCCESS'}],cols,types)
        with self.assertRaises(v.Stop):v.compare_financial([{'amount':'25.00','status':'SUCCESS'}],[{'amount':26,'status':'SUCCESS'}],cols,types)
    def test_disposable_admin_authenticated_password_change(self):
        s,b=fixture();u=s['app_users'][1];u['authorization_version']+=1;u['password_hash']='different-new-hash'
        s['audit'].append(dict(event_type='ADMIN_PASSWORD_CHANGED',occurred_at='2026-11-15T09:00:00Z',resource_id='1',resource_type='ACCOUNT',outcome='SUCCESS',actor_user_id='1',actor_identifier=v.ADMIN,metadata={}))

        with self.assertRaises(v.Stop):v.evaluate(s,b) # No independent authorization for a disposable Admin change.
        s['audit'][-1]['actor_user_id']='0'
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_archive_returns_financial_and_account_baseline_without_restore(self):
        import tempfile,hashlib
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            obj=object.__new__(v.FinalAudit);obj.private=Path(tmp);(obj.private/'backups').mkdir();path=obj.private/'backups/test.dump';path.write_bytes(b'synthetic archive')
            obj.activation={'backup':{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}
            obj.command=Mock(return_value='synthetic COPY');obj.sql=Mock(return_value='[{"id":"1"}]')
            tables=v.FINANCIAL+v.ACCOUNTS+('security_audit_events',)
            snapshot={t:[{'id':'1'}] for t in v.FINANCIAL};snapshot['types']=[dict(table_name=t,column_name='id',data_type='text') for t in tables]
            with patch.object(v,'protected',side_effect=lambda p,*args:Path(p)),patch.object(v,'copy_rows',return_value=(['id'],[{'id':'1'}])):
                base=obj.archive(snapshot)
            self.assertEqual(set(tables),set(base));self.assertEqual(1,len(base['payments']))
            for call in obj.command.call_args_list:self.assertNotIn('--dbname',list(map(str,call.args[0])))
    def test_runtime_otp_enabled_stops_before_snapshot(self):
        import tempfile,json
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            obj=object.__new__(v.FinalAudit);obj.repo=Path(tmp);obj.private=Path(tmp);obj.evidence={}
            (obj.repo/'.git').mkdir();(obj.repo/'.git/index').write_bytes(b'fixture')
            record=dict(mode='activate-phase674',success=True,beforeIntegrity={},afterIntegrity={},afterCounts=[6,4,4,2,6,4],recoveryEnabled=False,backup={'listVerified':True,'extractionVerified':True},newJavaPid=1,newFrontendPid=1,beforeServices={'ai':{'pid':'1'},'llm':{'pid':'1'}})
            file=obj.private/'evidence.json';file.write_text(json.dumps(record))
            obj.service=Mock(return_value={'pid':'1'});obj.command=Mock(return_value='PostgreSQL 16.3')
            obj.launch=Mock(side_effect=lambda:setattr(obj,'flags',{'paymesh.demo.password-recovery.enabled':'false'}))
            obj.sql=Mock(side_effect=['paymesh_demo|paymesh_demo_user|127.0.0.1|5432|on','1,2,3,4,5,6,7,8,9,10,11|true'])
            obj.http_json=Mock(return_value=(200,{'localDemoEnabled':True}));obj.snapshot=Mock();obj.read_authorization=Mock(return_value=({},{}))
            with patch.object(v,'protected',return_value=file),patch.object(v,'hidden',return_value='synthetic-private-password'):
                with self.assertRaises(v.Stop):obj.run()
            obj.snapshot.assert_not_called()
    def test_rejected_account_requires_its_actual_registration(self):
        s,b=fixture(True);s['merchant_registrations'][-1].update(user_id='2',merchant_id='m2')
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_source_never_calls_mutation_or_old_v10_launch_guard(self):
        source=Path(v.__file__).read_text();self.assertIn('launch=Activation.launch',source)
        for forbidden in ('self.restart(', 'self.backup(', 'os.kill(', 'write=True)', 'http_json(\'proxy:/api/v1/auth/login'):
            self.assertNotIn(forbidden,source)

if __name__=='__main__':unittest.main()
