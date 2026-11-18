"""One authorized historical operational Admin change; no database/network/private files."""
import copy
import unittest
from unittest.mock import Mock
import phase674_closeout as v
from test_phase674_closeout import fixture

UID='45420a63-8575-42d5-b757-58e53634b0e3'
EID='8b8ed48c-451b-4b72-9443-31dfd873cc3a'

def sample():
    s,b=fixture()
    def replace(x):
        if isinstance(x,list):return [replace(y) for y in x]
        if isinstance(x,dict):return {k:replace(y) for k,y in x.items()}
        return UID if x=='0' else x
    s,b=replace(s),replace(b)
    b['app_users'][0]['authorization_version']=3;s['app_users'][0]['authorization_version']=4;s['app_users'][0]['password_hash']='new-admin-hash'
    e=dict(event_id=EID,event_type='ADMIN_PASSWORD_CHANGED',resource_type='ACCOUNT',resource_id=UID,actor_user_id=UID,actor_identifier=v.REVIEWER,outcome='SUCCESS',occurred_at=v.AUTH_TIME,metadata={})
    s['audit'].append(e)
    auth=dict(schemaVersion=1,scope='PHASE674_ONE_EXACT_DEMO_ADMIN_PASSWORD_CHANGE',operatorStatement=v.AUTH_STATEMENT,login=v.REVIEWER,userId=UID,
              actorUserId=UID,actorLogin=v.REVIEWER,eventType='ADMIN_PASSWORD_CHANGED',eventId=None,eventIdEvidence='NOT_RETAINED_IN_DIAGNOSTIC',occurredAt=v.AUTH_TIME,outcome='SUCCESS',beforeAuthorizationVersion=3,afterAuthorizationVersion=4,activationSha256='a'*64,diagnosticSha256='b'*64,archiveSha256='c'*64)
    return s,b,auth

class AuthorizationTests(unittest.TestCase):
    def test_exact_authorized_event_accepted(self):
        s,b,a=sample();r=v.evaluate(s,b,a);self.assertEqual(1,r['accounts']['operationalAdmin']['passwordChangeAudits']);self.assertTrue(any(e['event']=='ADMIN_PASSWORD_CHANGED' for e in r['sessionEvents']))
    def test_missing_authorization_rejected(self):
        s,b,a=sample()
        with self.assertRaises(v.Stop):v.evaluate(s,b)
    def test_wrong_record_identity_scope_or_statement(self):
        for key,value in [('login',v.ADMIN),('scope','ALL_ADMINS'),('operatorStatement','approved'),('beforeAuthorizationVersion',2),('afterAuthorizationVersion',5),('diagnosticSha256','missing')]:
            s,b,a=sample();a[key]=value
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_other_uuid_rejected(self):
        s,b,a=sample();a['userId']=a['actorUserId']='778b0df0-c804-41fd-ac65-606a6b208c27'
        with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_wrong_event_actor_target_timestamp_outcome_or_type(self):
        for key,value in [('actor_user_id','1'),('actor_identifier',v.ADMIN),('resource_id','1'),('occurred_at','2026-11-15T05:38:12Z'),('outcome','FAILED'),('resource_type','MERCHANT')]:
            s,b,a=sample();s['audit'][-1][key]=value
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_event_id_not_fabricated_and_live_id_validated(self):
        s,b,a=sample();a['eventId']=EID
        with self.assertRaises(v.Stop):v.evaluate(s,b,a) # Original diagnostic did not retain it.
        s,b,a=sample();s['audit'][-1]['event_id']='not-a-uuid'
        with self.assertRaises((ValueError,v.Stop)):v.evaluate(s,b,a)
    def test_version_extra_increment_or_wrong_baseline(self):
        for previous,current in ((3,5),(2,4),(3,3)):
            s,b,a=sample();b['app_users'][0]['authorization_version']=previous;s['app_users'][0]['authorization_version']=current
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_missing_or_additional_event(self):
        for extra in (False,True):
            s,b,a=sample()
            if extra:s['audit'].append(copy.deepcopy(s['audit'][-1]))
            else:s['audit'].pop()
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_unchanged_hash_is_not_the_authorized_change(self):
        s,b,a=sample();s['app_users'][0]['password_hash']=b['app_users'][0]['password_hash']
        with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_disabled_suspended_or_wrong_roles(self):
        for change in ('disabled','status','role'):
            s,b,a=sample()
            if change=='disabled':s['app_users'][0]['enabled']=False
            elif change=='status':s['app_users'][0]['account_status']='SUSPENDED'
            else:s['user_roles'][0]['role_name']='MERCHANT'
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_other_operational_hash_change_still_rejected(self):
        s,b,a=sample();s['app_users'][2]['password_hash']='unexpected'
        with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_disposable_admin_must_remain_unchanged(self):
        for field,value in [('password_hash','unexpected'),('authorization_version',2),('updated_at','2026-11-15T09:30:00Z')]:
            s,b,a=sample();s['app_users'][1][field]=value
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def test_lifecycle_and_otp_checks_preserved(self):
        for change in ('lifecycle','otp'):
            s,b,a=sample()
            if change=='lifecycle':s['lifecycle'][3]['status']='SUSPENDED'
            else:s['eligibility']=[{'enabled':True}]
            with self.assertRaises(v.Stop):v.evaluate(s,b,a)
    def loader_fixture(self,tmp):
        import json,hashlib
        from pathlib import Path
        obj=object.__new__(v.FinalAudit);obj.private=Path(tmp)
        act=obj.private/v.ACTIVATION/'evidence.json';act.parent.mkdir();obj.activation={'backup':{'sha256':'c'*64}};act.write_text(json.dumps(obj.activation));act.chmod(0o600)
        diag=obj.private/v.AUTH_DIAGNOSTIC/'evidence.json';diag.parent.mkdir();diag.write_text(json.dumps({'mode':'diagnose-phase674-password-mismatch','success':True,'diagnosis':{'accounts':[{'login':v.REVIEWER,'enabled':True,'status':'ACTIVE','roles':['ADMIN'],'previousAuthorizationVersion':3,'currentAuthorizationVersion':4,'passwordHashChanged':'YES','passwordAuditEvents':[{'eventType':'ADMIN_PASSWORD_CHANGED','afterActivation':True,'actorLogin':v.REVIEWER,'actorClassification':'AUTHENTICATED_ADMIN_SELF_RECORD','occurredAt':v.AUTH_TIME}]}]}}));diag.chmod(0o600)
        _,_,a=sample();a['activationSha256']=hashlib.sha256(act.read_bytes()).hexdigest();a['diagnosticSha256']=hashlib.sha256(diag.read_bytes()).hexdigest()
        record=obj.private/v.AUTH_FILE;record.write_text(json.dumps(a));record.chmod(0o600)
        return obj,record,diag
    def test_protected_authorization_and_source_bindings_loaded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            obj,record,diag=self.loader_fixture(tmp);a,u=obj.read_authorization();self.assertEqual(UID,a['userId']);self.assertEqual(4,u['currentAuthorizationVersion'])
            diag.write_text(diag.read_text()+' ')
            with self.assertRaises(v.Stop):obj.read_authorization()
    def test_missing_or_invalid_protected_record_fails(self):
        import tempfile,json
        with tempfile.TemporaryDirectory() as tmp:
            obj,record,diag=self.loader_fixture(tmp);record.chmod(0o644)
            with self.assertRaises(v.Stop):obj.read_authorization()
            record.chmod(0o600);record.write_text('{}')
            with self.assertRaises(v.Stop):obj.read_authorization()
    def test_authorized_admin_retained_unrevoked_session_still_fails(self):
        s,b,a=sample();s['sessions'].append(dict(user_id=UID,created_at='2026-11-15T05:00:00Z',authorization_version=3,account_status='ACTIVE',roles_snapshot='ADMIN',revoked_at=None,absolute_expires_at='2026-11-16T00:00:00Z',idle_expires_at='2026-11-16T00:00:00Z'))
        with self.assertRaises(v.Stop):v.evaluate(s,b,a)

if __name__=='__main__':unittest.main()
