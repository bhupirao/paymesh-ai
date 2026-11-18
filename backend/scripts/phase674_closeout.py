"""Operator-only read-only V11 audit. No login, mutation, restart, restore or OTP call.
Archive password hashes/PII exist in memory only; evidence contains sanitized summaries.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import urllib.request
from decimal import Decimal
from phase673_otp_ops import Ops, Stop, PG, ADMIN, MERCHANT, REVIEWER, protected, hidden
from phase673_closeout import Closeout, require, instant, copy_rows, row_counts, FINANCIAL, ACCOUNTS
from phase674_activation import Activation

ACTIVATION='otp-step17-activate-phase674-20261115T045625Z-yd6r_0kn'
REJECT='reject-demo@example.test'
EVENTS=('MERCHANT_APPROVE','MERCHANT_REJECT','MERCHANT_SUSPEND','MERCHANT_REACTIVATE',
        'DISPOSABLE_MERCHANT_PASSWORD_RECOVERED','ADMIN_PASSWORD_CHANGED','LOCAL_DEMO_PASSWORD_RESET','ADMIN_PASSWORD_RECOVERED')

AUTH_DIAGNOSTIC='otp-step17-diagnose-phase674-password-mismatch-20261115T055856Z-1mmdwii9'
AUTH_FILE='phase674-demo-admin-password-change-authorization.json'
AUTH_STATEMENT='Yes, I intentionally changed the demo-admin password during the Admin Profile browser test. I authorize this exact change.'
AUTH_TIME='2026-11-15T05:38:11.323483Z'

def authorization_record(a):
    require(isinstance(a,dict),'Missing or invalid exact operator authorization record.')
    fixed=dict(schemaVersion=1,scope='PHASE674_ONE_EXACT_DEMO_ADMIN_PASSWORD_CHANGE',operatorStatement=AUTH_STATEMENT,
               login=REVIEWER,eventType='ADMIN_PASSWORD_CHANGED',actorLogin=REVIEWER,outcome='SUCCESS',beforeAuthorizationVersion=3,afterAuthorizationVersion=4)
    require(all(a.get(k)==v for k,v in fixed.items()),'Operator authorization scope/identity/version mismatch.')
    require(a.get('userId')==a.get('actorUserId') and isinstance(a.get('userId'),str),'Authorization must name the exact authenticated self actor.')
    from phase673_otp_ops import identifier
    require(identifier(a['userId'])==a['userId'],'Invalid authorized account UUID.')
    require(instant(a.get('occurredAt',''))==instant(AUTH_TIME),'Authorized event timestamp mismatch.')
    require(a.get('eventIdEvidence')=='NOT_RETAINED_IN_DIAGNOSTIC' and a.get('eventId') is None,'Event ID was not retained; do not invent authorization identifiers.')
    require(all(isinstance(a.get(k),str) and re.fullmatch('[0-9a-f]{64}',a[k]) for k in ('activationSha256','diagnosticSha256','archiveSha256')),'Missing exact evidence bindings.')
    return a

def authorized_change(snapshot,base,a):
    a=authorization_record(a);uid=a['userId']
    current=[u for u in snapshot['app_users'] if u['user_id']==uid];original=[u for u in base['app_users'] if u['user_id']==uid]
    require(len(current)==len(original)==1,'Authorized account UUID missing from archive/current state.')
    u,b=current[0],original[0]
    for table,rows in ((snapshot,snapshot['user_roles']),(base,base['user_roles'])):
        require(sorted(r['role_name'] for r in rows if r['user_id']==uid)==['ADMIN'],'Authorized account must remain ADMIN-only.')
    require(all(x['login_normalized']==REVIEWER and x['enabled'] and x['account_status']=='ACTIVE' for x in (u,b)),'Authorized account identity/status changed.')
    require(b['authorization_version']==3 and u['authorization_version']==4,'Authorized account version must be exactly3 to4.')
    require(u['password_hash']!=b['password_hash'],'Authorized password hash must differ from original archive.')
    events=[e for e in snapshot['audit'] if e['event_type']=='ADMIN_PASSWORD_CHANGED' and e['resource_id']==uid and instant(e['occurred_at'])>=instant(snapshot['baselineAt'])]
    require(len(events)==1,'Missing or additional authorized-account password-change event.')
    e=events[0]
    require(e['resource_type']=='ACCOUNT' and e['outcome']=='SUCCESS' and e['actor_user_id']==uid and e['actor_identifier']==REVIEWER
            and instant(e['occurred_at'])==instant(AUTH_TIME),'Authorized password-change actor/target/time/outcome mismatch.')
    from phase673_otp_ops import identifier
    require(identifier(e['event_id'])==e['event_id'],'Current authorized event ID must be a valid UUID.')
    return uid,e

def event_sessions(user, roles, sessions, event, post_version, now, exact_version=True):
    """Audit Instant is after trigger CURRENT_TIMESTAMP (transaction start), not commit.
    Same timestamp or version incompatible with strict before-ordering is ambiguous.
    Current account version is never used as the historical cohort selector.
    """
    when=instant(event['occurred_at']);observed=instant(now)
    require(when<=observed,'Future audit timestamp; clock review required.')
    pre=[];after=[];boundary=[]
    for s in sessions:
        created=instant(s['created_at'])
        (pre if created<when else after if created>when else boundary).append(s)
    def usable(s):
        return (user['enabled'] and s['revoked_at'] is None and instant(s['absolute_expires_at'])>observed
                and instant(s['idle_expires_at'])>observed and s['authorization_version']==user['authorization_version']
                and s['account_status']==user['account_status'] and s['roles_snapshot']==','.join(sorted(roles)))
    known=[s for s in pre if post_version is not None and s['authorization_version']<post_version]
    ambiguous=len(boundary)+len(pre)-len(known)
    bad=[s for s in known if s['revoked_at'] is None or instant(s['revoked_at'])>when]
    eligible=sum(usable(s) for s in known)
    status=('CURRENT_SECURITY_FAILURE' if eligible else 'REVOCATION_INCONSISTENT' if bad else
            'AMBIGUOUS_BOUNDARY' if ambiguous else 'HISTORICAL_EVIDENCE_UNAVAILABLE' if not known else 'VERIFIED_FROM_RETAINED_ROWS')
    return dict(event=event['event_type'],occurredAt=event['occurred_at'],expectedPostVersion=post_version,exactEventVersionKnown=exact_version,
                historicalStatus=status,retainedPreEventFamilies=len(known),postEventFamilies=len(after),
                ambiguousFamilies=ambiguous,inconsistentFamilies=len(bad),currentUsablePreEventFamilies=eligible,
                actualJwtAcceptanceTested=False)

def compare_financial(original,current,columns,types):
    require(row_counts(original,columns,types)==row_counts(current,columns,types),'Financial row-content mismatch against pre-V11 archive.')

def check_counts(s,base):
    has_reject=any(u['login_normalized']==REJECT for u in s['app_users'])
    expected=[len(base[t])+(1 if has_reject and t in ('app_users','merchants','merchant_memberships','merchant_registrations') else 0)
              for t in ('app_users','merchants','merchant_memberships','merchant_registrations','payments','refunds')]
    actual=[len(s[t]) for t in ('app_users','merchants','merchant_memberships','merchant_registrations','payments','refunds')]
    require(actual==expected,'Unexpected account/financial counts; investigate without changing records.')
    return actual

def evaluate(s,base,authorization=None):
    authorized_uid=None
    if authorization is not None:authorized_uid,_=authorized_change(s,base,authorization)
    actual=check_counts(s,base);now=s['collectedAt'];users={u['user_id']:u for u in s['app_users']}
    names={u['login_normalized']:u for u in users.values()};old={u['user_id']:u for u in base['app_users']}
    roles=lambda uid:sorted(r['role_name'] for r in s['user_roles'] if r['user_id']==uid)
    require(all(u['login_normalized'] in {x['login_normalized'] for x in old.values()}|{REJECT} for u in users.values()),'Unexpected account identity.')
    require(all(uid in users for uid in old),'An existing account is missing.')
    require(not any(e['enabled'] for e in s['eligibility']),'Recovery eligibility unexpectedly enabled.')
    require(not any(c['consumed_at'] is None and instant(c['expires_at'])>instant(now) for c in s['challenges']),'Usable recovery challenge remains.')
    require(not any(g['consumed_at'] is None and instant(g['expires_at'])>instant(now) for g in s['grants']),'Usable recovery grant remains.')
    # All baseline roles, membership/registration identities and optional new rejection ownership are conserved.
    for uid,u in users.items():
        require(roles(uid) in (['ADMIN'],['MERCHANT']),'Unexpected account role set.')
        if uid in old:
            require(roles(uid)==sorted(r['role_name'] for r in base['user_roles'] if r['user_id']==uid),'Existing role assignment changed.')
            require(all(u[k]==old[uid][k] for k in ('user_id','login_normalized','created_at','enabled')),'Existing account identity/enabled state changed.')
        mm=[m for m in s['merchant_memberships'] if m['user_id']==uid]
        require(len(mm)==(1 if roles(uid)==['MERCHANT'] else 0),'Account membership cardinality differs from reviewed ownership model.')
    merchants={m['merchant_id']:m for m in s['merchants']};life={m['merchant_id']:m for m in s['lifecycle']}
    require(set(merchants)==set(life),'Lifecycle/registry identity mismatch.')
    require(len(s['merchant_memberships'])==len(merchants),'Unexpected unowned/shared registry.')
    for mm in s['merchant_memberships']:
        u=users[mm['user_id']];m=merchants[mm['merchant_id']];a=life[mm['merchant_id']]
        status=u['account_status']
        require(a['status']==status and m['active']==(status=='ACTIVE') and mm['active']==(status=='ACTIVE')
                and m['verified']==(status in ('ACTIVE','SUSPENDED')),'Account/registry/membership/lifecycle state inconsistent.')
    for r in s['merchant_registrations']:
        require(any(m['user_id']==r['user_id'] and m['merchant_id']==r['merchant_id'] for m in s['merchant_memberships']),'Registration ownership mismatch.')
    for table,keys in (('merchant_registrations',('user_id',)),('merchant_memberships',('user_id','merchant_id'))):
        for before in base[table]:
            matches=[r for r in s[table] if all(r[k]==before[k] for k in keys)]
            require(len(matches)==1,'Existing ownership or registration removed/duplicated.')
            if table=='merchant_registrations':require(matches[0]==before,'Existing registration profile changed.')
    audit=[e for e in s['audit'] if e['outcome']=='SUCCESS'];limits=['No live JWT acceptance/replay test; legacy no-sid tokens are not inventoried. Phase673 historical limitations remain.'];summaries={};hist=[]
    def actor(e):
        a=users.get(e['actor_user_id'])
        require(a is not None and roles(a['user_id'])==['ADMIN'] and a['enabled'] and a['account_status']=='ACTIVE'
                and e['actor_identifier']==a['login_normalized'],'Missing/inconsistent authenticated Admin audit actor.')
    dedicated=names.get(MERCHANT);require(dedicated is not None,'Dedicated Merchant missing.')
    member=next(m for m in s['merchant_memberships'] if m['user_id']==dedicated['user_id'])
    mid=member['merchant_id'];registry=merchants[mid];state=life[mid]
    require(dedicated['enabled'] and dedicated['account_status']=='ACTIVE' and roles(dedicated['user_id'])==['MERCHANT']
            and registry['verified'] and registry['active'] and member['active'] and state['status']=='ACTIVE','Dedicated Merchant lifecycle is not enabled approved ACTIVE.')
    events=[e for e in audit if (e['resource_type']=='MERCHANT' and e['resource_id']==mid) or
            (e['resource_type']=='ACCOUNT' and e['resource_id']==dedicated['user_id'])]
    recent=[e for e in events if instant(e['occurred_at'])>=instant(s['baselineAt']) and e['event_type'] in EVENTS]
    for kind in ('MERCHANT_APPROVE','MERCHANT_SUSPEND','MERCHANT_REACTIVATE','DISPOSABLE_MERCHANT_PASSWORD_RECOVERED'):
        require(sum(e['event_type']==kind for e in recent)==1,'Expected exactly one lifecycle/offline recovery success is missing or repeated; inspect actual audit counts.')
    order=[e['event_type'] for e in sorted(recent,key=lambda e:instant(e['occurred_at']))]
    require(order==['DISPOSABLE_MERCHANT_PASSWORD_RECOVERED','MERCHANT_APPROVE','MERCHANT_SUSPEND','MERCHANT_REACTIVATE'],'Unexpected recovery/lifecycle ordering or additional security mutation.')
    approval=next(e for e in recent if e['event_type']=='MERCHANT_APPROVE')
    for e in recent:
        if e['event_type'].startswith('MERCHANT_'):
            actor(e)
            expected={'MERCHANT_APPROVE':('PENDING_APPROVAL','ACTIVE'),'MERCHANT_SUSPEND':('ACTIVE','SUSPENDED'),'MERCHANT_REACTIVATE':('SUSPENDED','ACTIVE')}[e['event_type']]
            require((e['metadata'].get('from'),e['metadata'].get('to'))==expected,'Lifecycle audit transition metadata mismatch.')
            if e['event_type']!='MERCHANT_APPROVE':require(bool(e['metadata'].get('reason','').strip()),'Required lifecycle reason missing.')
        else:require(e['actor_user_id'] is None and e['actor_identifier'] is None and e['metadata'].get('source')=='offline_operator_recovery','Offline recovery audit actor/source mismatch.')
    require(approval['metadata'].get('ownershipAttested') is True and bool(approval['metadata'].get('reviewReference'))
            and state['review_reference']==approval['metadata']['reviewReference'] and state['approved_by']==approval['actor_user_id']
            and registry['verified_by']==state['approved_by'] and instant(registry['verified_at'])==instant(state['approved_at'])
            and instant(state['approved_at'])<=instant(approval['occurred_at']),'Original approval attestation/actor/time was not preserved.')
    require(any(e['event_type']=='LOCAL_DEMO_PASSWORD_RESET' for e in events),'Prior OTP reset audit missing.')
    expected_changes={dedicated['user_id']:recent}
    rejection=names.get(REJECT)
    if rejection:
        rm=next(m for m in s['merchant_memberships'] if m['user_id']==rejection['user_id']);rs=life[rm['merchant_id']];reg=merchants[rm['merchant_id']]
        require(rejection['enabled'] and rejection['account_status']=='REJECTED' and not rm['active'] and not reg['active'] and not reg['verified'] and rs['status']=='REJECTED' and bool(rs['reason']) and rs['approved_at'] is None,'Rejection account/lifecycle state invalid.')
        require(sum(r['user_id']==rejection['user_id'] and r['merchant_id']==rm['merchant_id'] and r['email']==REJECT for r in s['merchant_registrations'])==1,'Rejected account registration/ownership profile missing or mismatched.')
        ev=[e for e in audit if e['event_type']=='MERCHANT_REJECT' and e['resource_id']==rm['merchant_id'] and e['resource_type']=='MERCHANT']
        require(len(ev)==1,'Missing/repeated rejection success audit.');actor(ev[0])
        require(ev[0]['metadata'].get('reason')==rs['reason'] and ev[0]['metadata'].get('from')=='PENDING_APPROVAL' and ev[0]['metadata'].get('to')=='REJECTED','Rejection reason/transition audit mismatch.')
        expected_changes[rejection['user_id']]=ev
    allowed_mids={mid}|({next(m['merchant_id'] for m in s['merchant_memberships'] if m['user_id']==rejection['user_id'])} if rejection else set())
    require(not any(e['event_type'].startswith('MERCHANT_') and instant(e['occurred_at'])>=instant(s['baselineAt']) and e['resource_id'] not in allowed_mids for e in audit),'Unexpected operational Merchant administrative audit mutation.')
    for uid,u in users.items():
        changes=expected_changes.get(uid,[])
        pw=[e for e in audit if e['event_type']=='ADMIN_PASSWORD_CHANGED' and e['resource_type']=='ACCOUNT' and e['resource_id']==uid and instant(e['occurred_at'])>=instant(s['baselineAt'])]
        if pw:
            require(uid==authorized_uid,'Unexpected operational account password change; documented review required.')
            for e in pw:actor(e);require(e['actor_user_id']==uid,'Password-change actor must be the target Admin.')
            changes=changes+pw
        if uid in old:
            if uid!=dedicated['user_id']:
                require(u['account_status']==old[uid]['account_status'],'Unexpected operational/pending account status change.')
                if not pw:require(u['password_hash']==old[uid]['password_hash'],'Unexplained existing password change.')
            initial=int(old[uid]['authorization_version'])
        else:initial=0
        delta=int(u['authorization_version'])-initial
        require(delta>=len(changes),'Authorization version does not reflect recorded security changes.')
        if uid in old and uid not in (dedicated['user_id'],authorized_uid):require(u==old[uid],'Undocumented operational/disposable Admin account change; strict archive equality required.')
        if delta!=len(changes):limits.append('Additional authorization-version increment unexplained for '+('dedicatedMerchant' if uid==dedicated['user_id'] else 'dedicatedAdmin' if u['login_normalized']==ADMIN else 'otherAccount'))
        post_known=delta==len(changes)
        for i,e in enumerate(sorted(changes,key=lambda e:instant(e['occurred_at'])),1):
            result=event_sessions(u,roles(uid),[r for r in s['sessions'] if r['user_id']==uid],e,initial+i,now,exact_version=post_known)
            hist.append(result)
            require(result['historicalStatus'] not in ('CURRENT_SECURITY_FAILURE','REVOCATION_INCONSISTENT'),'Retained pre-event family is usable or revocation inconsistent; investigate privately.')
            if result['historicalStatus']!='VERIFIED_FROM_RETAINED_ROWS':limits.append(result['historicalStatus']+': '+e['event_type'])
        summaries['dedicatedMerchant' if uid==dedicated['user_id'] else 'dedicatedAdmin' if u['login_normalized']==ADMIN else 'operationalAdmin' if u['login_normalized']==REVIEWER else 'account-'+str(len(summaries)+1)]=dict(status=u['account_status'],authorizationVersion=u['authorization_version'],baselineVersion=initial,expectedVersionChanges=len(changes),passwordChangeAudits=len(pw))
    # Non-target registry/membership rows are exact; legitimate target lifecycle changes are isolated above.
    for table,key in (('merchants','merchant_id'),('merchant_memberships','merchant_id')):
        for before in base[table]:
            if before[key]!=mid:require(before==next(r for r in s[table] if r[key]==before[key]),'Operational registry/membership changed unexpectedly.')
    return dict(actualCounts=actual,rejectionRegistrationPresent=bool(rejection),accounts=summaries,sessionEvents=hist,limitations=limits,
                result='VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS' if limits else 'VERIFIED_FROM_AVAILABLE_DATABASE_EVIDENCE',actualJwtAcceptanceTested=False)

class FinalAudit(Closeout):
    def __init__(self):
        Ops.__init__(self,'verify-phase674-final');self.report=self.repo/'frontend/PHASE-6.7.4-ADMIN-DASHBOARD-MERCHANT-MANAGEMENT-REPORT.md'
    launch=Activation.launch
    def snapshot(self):
        # One snapshot query below includes every required table and all audits: overwrite old restricted collector.
        parts={t:'SELECT * FROM public.'+t for t in FINANCIAL+ACCOUNTS}
        parts.update(lifecycle='SELECT * FROM public.merchant_administration',eligibility='SELECT user_id,enabled FROM public.demo_recovery_eligibility',
            sessions='SELECT user_id,authorization_version,account_status,roles_snapshot,created_at,absolute_expires_at,idle_expires_at,revoked_at FROM public.auth_sessions',
            challenges='SELECT user_id,expires_at,consumed_at FROM public.password_recovery_challenges',grants='SELECT expires_at,consumed_at FROM public.password_reset_authorizations',
            audit="SELECT event_id,actor_user_id,actor_identifier,event_type,target_merchant_id,resource_id,resource_type,outcome,metadata,occurred_at FROM public.security_audit_events",
            types="SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public'")
        fields=["'collectedAt',clock_timestamp()"]+["'"+k+"',COALESCE((SELECT json_agg(row_to_json(x)) FROM ("+v+") x),'[]'::json)" for k,v in parts.items()]
        return json.loads(self.sql('SELECT json_build_object('+','.join(fields)+')'),parse_float=Decimal)
    def archive(self,s):
        backup=self.activation['backup'];path=protected(backup['path']);directory=protected(self.private/'backups',0o700)
        require(path.resolve().is_relative_to(directory.resolve()),'Archive path outside protected backups.')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==backup['sha256'],'Activation archive checksum mismatch.')
        self.command([PG/'pg_restore','--list',path]);base={}
        for table in FINANCIAL+ACCOUNTS+('security_audit_events',):
            text=self.command([PG/'pg_restore','--data-only','--table='+table,'--file=-',path])+'\n'
            cols,rows=copy_rows(text,table);types={r['column_name']:r['data_type'] for r in s['types'] if r['table_name']==table}
            require(set(cols)==set(types),'Archive/current columns differ.')
            if table in FINANCIAL:
                compare_financial(rows,s[table],cols,types)
                base[table]=rows
            else:
                # Canonicalize archive values to actual JSON shapes before account comparisons.
                def convert(r):
                    return {k:(None if v is None else v=='t' if types[k]=='boolean' else int(v) if types[k] in ('bigint','integer','smallint') else instant(v).isoformat() if types[k]=='timestamp with time zone' else json.loads(v) if types[k] in ('json','jsonb') else v) for k,v in r.items()}
                base[table]=[convert(r) for r in rows]
        # Every pre-existing audit row must remain unchanged (including old OTP reset evidence).
        cols=list(base['security_audit_events'][0]) if base['security_audit_events'] else []
        types={r['column_name']:r['data_type'] for r in s['types'] if r['table_name']=='security_audit_events'}
        current=self.sql("SELECT COALESCE(json_agg(row_to_json(e)),'[]'::json) FROM public.security_audit_events e")
        require(not(row_counts(base['security_audit_events'],cols,types)-row_counts(json.loads(current),cols,types)),'Historical audit row changed or disappeared.')
        return base
    def read_authorization(self):
        authorization=authorization_record(json.loads(protected(self.private/AUTH_FILE).read_text()))
        diagnostic_file=protected(self.private/AUTH_DIAGNOSTIC/'evidence.json')
        require(hashlib.sha256(diagnostic_file.read_bytes()).hexdigest()==authorization['diagnosticSha256']
                and hashlib.sha256((self.private/ACTIVATION/'evidence.json').read_bytes()).hexdigest()==authorization['activationSha256']
                and self.activation['backup']['sha256']==authorization['archiveSha256'],'Operator authorization evidence fingerprints differ.')
        diagnostic=json.loads(diagnostic_file.read_text())
        require(diagnostic.get('success') is True and diagnostic.get('mode')=='diagnose-phase674-password-mismatch','Successful original diagnostic required.')
        diag_admin=next((u for u in diagnostic['diagnosis']['accounts'] if u['login']==REVIEWER),None)
        require(diag_admin is not None and diag_admin['previousAuthorizationVersion']==3 and diag_admin['currentAuthorizationVersion']==4
                and diag_admin['passwordHashChanged']=='YES','Diagnostic does not support exact operator authorization.')
        events=[e for e in diag_admin['passwordAuditEvents'] if e['eventType']=='ADMIN_PASSWORD_CHANGED' and e['afterActivation']]
        require(diag_admin['enabled'] and diag_admin['status']=='ACTIVE' and diag_admin['roles']==['ADMIN'] and len(events)==1
                and events[0]['actorLogin']==REVIEWER and events[0]['actorClassification']=='AUTHENTICATED_ADMIN_SELF_RECORD'
                and instant(events[0]['occurredAt'])==instant(AUTH_TIME),'Diagnostic actor/event does not support this exact authorization.')
        return authorization,diag_admin
    def run(self):
        self.activation=json.loads(protected(self.private/ACTIVATION/'evidence.json').read_text())
        require(self.activation.get('mode')=='activate-phase674' and self.activation.get('success') is True and self.activation.get('beforeIntegrity')==self.activation.get('afterIntegrity') and all(self.activation['backup'].get(k) is True for k in ('listVerified','extractionVerified')) and self.activation.get('afterCounts')==[6,4,4,2,6,4] and self.activation.get('recoveryEnabled') is False,'Successful authentic V11 activation evidence required.')
        authorization,diag_admin=self.read_authorization()
        self.index_before=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest();self.staged_before=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])
        self.services={}
        for k,p,c,t in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:self.services[k]=self.service(p,c,t)
        self.launch()
        require(self.services['java']['pid']==str(self.activation['newJavaPid']) and self.services['frontend']['pid']==str(self.activation['newFrontendPid']),'Java/frontend PID differs from successful activation; review legitimate restart evidence before proceeding.')
        require(self.flags.get('paymesh.demo.password-recovery.enabled')=='false','OTP launch configuration must remain disabled.')
        for k in ('ai','llm'):require(self.services[k]==self.activation['beforeServices'][k],'Python/LLM identity differs from authentic activation evidence.')
        for n in ('psql','pg_restore'):require(' 16.' in self.command([PG/n,'--version']),'PostgreSQL16 tools required.')
        self.db_password=hidden('Existing paymesh_demo_user database password (hidden): ');require(bool(self.db_password),'Empty database credential.')
        self.stage='read-only-identity'
        require(self.sql("SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port(),current_setting('transaction_read_only')")=='paymesh_demo|paymesh_demo_user|127.0.0.1|5432|on','Read-only demo identity mismatch.')
        require(self.sql("SELECT string_agg(version,',' ORDER BY installed_rank)||'|'||bool_and(success)::text FROM public.flyway_schema_history WHERE version IS NOT NULL")=='1,2,3,4,5,6,7,8,9,10,11|true','Require successful V1–V11 only.')
        require(self.http_json('proxy:/api/v1/auth/password/capabilities')==(200,{'localDemoEnabled':False}),'OTP runtime must remain disabled.')
        self.stage='read-only-snapshot';s=self.snapshot();base=self.archive(s)
        trigger=json.loads(self.sql("SELECT COALESCE(json_agg(row_to_json(t)),'[]'::json) FROM (SELECT g.tgenabled AS enabled,p.prosrc AS body FROM pg_trigger g JOIN pg_proc p ON p.oid=g.tgfoid WHERE g.tgrelid='public.app_users'::regclass AND g.tgname='auth_account_security_change' AND p.proname='revoke_auth_state_for_account_change') t"))
        migration=(self.repo/'backend/src/main/resources/db/migration/V10__persistent_sessions_and_local_demo_recovery.sql').read_text()
        body=re.search(r'CREATE FUNCTION revoke_auth_state_for_account_change\(\).*?AS \$\$(.*?)\$\$;',migration,re.S).group(1)
        require(len(trigger)==1 and trigger[0]['enabled'] in ('O','A') and trigger[0]['body']==body,'V10 account security trigger missing, disabled or changed.')
        self.evidence['accountRevocationTriggerMatchesV10']=True
        # Normalize timestamp representations in both structures for exact metadata equality.
        for table in ACCOUNTS:
            for r in s[table]:
                for field,value in r.items():
                    if value is not None and any(t['table_name']==table and t['column_name']==field and t['data_type']=='timestamp with time zone' for t in s['types']):r[field]=instant(value).isoformat()
        s['baselineAt']=self.activation['startedAt']
        self.evidence['actualCounts']=[len(s[t]) for t in ('app_users','merchants','merchant_memberships','merchant_registrations','payments','refunds')]
        self.evidence['observedSuccessfulAuditCounts']={kind:sum(e['event_type']==kind and e['outcome']=='SUCCESS' for e in s['audit']) for kind in EVENTS}
        require(any(u['user_id']==authorization['userId'] and instant(u['updated_at'])==instant(diag_admin['currentUpdatedAt']) for u in s['app_users']),'Authorized account update timestamp differs from diagnostic evidence.')
        summary=evaluate(s,base,authorization)
        _,authorized_event=authorized_change(s,base,authorization)
        self.evidence['authorizedAdminPasswordChange']={'authorizationFile':str(self.private/AUTH_FILE),'matchedEventId':authorized_event['event_id'],'occurredAt':authorized_event['occurred_at'],'beforeVersion':3,'afterVersion':4}
        self.evidence['sessionEvidenceLimits']='Audit timestamps are not commit timestamps; legacy no-sid JWTs are not inventoried; no token replay performed. Missing/deleted families cannot certify historical revocation. Phase673 limitations remain unchanged.'
        self.evidence.update(summary,financialRowComparison=dict(tables=list(FINANCIAL),matched=True,testRestorePerformed=False),activationEvidence=str(self.private/ACTIVATION/'evidence.json'),recoveryEnabled=False)
        require(self.http_json('/actuator/health/readiness')[1].get('status')=='UP','Java readiness failed.')
        for prefix in ('','proxy:'):require(self.http_json(prefix+'/api/v1/payments/health')[0]==200,'Payment health failed.')
        for route in ('/','/admin/dashboard','/admin/merchants','/admin/merchant','/admin/pending','/admin/payments','/admin/refunds','/admin/audit','/admin/accounts','/admin/profile','/merchant/dashboard'):
            with self.http.open(urllib.request.Request('http://127.0.0.1:5500'+route),timeout=10) as r:require(r.status==200,'Frontend route unavailable.');r.read(1024)
        for k,p,c,t in [('java',18080,self.repo/'backend','java'),('frontend',5500,self.repo,'python'),('ai',8000,self.repo/'ai-service','python'),('llm',8082,Path.home()/'Developer/paymesh-tools/llama.cpp','llm')]:require(self.service(p,c,t)==self.services[k],'Service identity changed during audit.')
        require(self.counts()==summary['actualCounts'],'Counts changed during audit; rerun only after reviewing concurrent activity.')
        require(self.http_json('proxy:/api/v1/auth/password/capabilities')==(200,{'localDemoEnabled':False}),'OTP state changed during audit.')
        self.stage='read-only-final-verified'
        print('Counts users|merchants|memberships|registrations|payments|refunds: '+'|'.join(map(str,summary['actualCounts'])))
        print('V11/account/lifecycle/actor/audit/eligibility/grant checks: VERIFIED')
        print('Actual successful audit counts: '+json.dumps(self.evidence['observedSuccessfulAuditCounts'],sort_keys=True))
        print('Financial row contents: MATCH (8 pre-V11 archive tables; no restore)')
        for r in summary['sessionEvents']:print(r['event']+': '+r['historicalStatus'])
        print('OTP=false; persistent-session configuration/readiness/payment health/frontend: PASS')
        for limitation in summary['limitations']:print('Evidence limitation: '+limitation)
        print(summary['result'])
    def closeout(self,success):
        self.evidence.update(success=success,stage=self.stage)
        if hasattr(self,'index_before'):
            self.evidence['indexPreserved']=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()==self.index_before
            self.evidence['stagedPreserved']=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])==self.staged_before
        self.private_json(self.run_dir/'evidence.json',self.evidence);self.db_password=None
        with self.report.open('a') as f:f.write('\n## Operator Phase674 final read-only verification\n\nOutcome: '+(self.evidence.get('result','verified') if success else 'STOPPED; inspect private evidence, no automatic retry')+'. Evidence: `'+str(self.run_dir/'evidence.json')+'`. No mutation/restore/token test performed.\n')
        print(('Verified read-only audit.' if success else 'Stopped safely; review private evidence.')+' Evidence: '+str(self.run_dir/'evidence.json'))

def main():
    os.umask(0o077);op=None
    if len(sys.argv)!=1 or not sys.stdin.isatty() or not sys.stdout.isatty():print('Use the interactive wrapper without arguments.',file=sys.stderr);return 1
    try:op=FinalAudit();op.run();op.closeout(True);return 0
    except Stop as e:print(str(e),file=sys.stderr)
    except (Exception,KeyboardInterrupt):print('Read-only verification failed; inspect protected evidence, not raw credentials.',file=sys.stderr)
    if op:
        try:op.closeout(False)
        except Exception:print('Could not complete private evidence; no automatic retry.',file=sys.stderr)
    return 1
if __name__=='__main__':sys.exit(main())
