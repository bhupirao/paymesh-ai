"""Read-only operator audit. Imported operations are reused ONLY for identity/GET/evidence helpers.
No activation, restart, backup creation, mutation SQL or authentication POST is called.
Raw backup rows and password hashes are compared only in memory and never printed/persisted.
"""
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sys
import urllib.request

from phase673_otp_ops import Ops, Stop, protected, identifier, PG, ADMIN, MERCHANT, REVIEWER

DEPLOY = 'otp-step17-deploy-20261114T181004Z-5kbrnbq_'
ACTIVATE = 'otp-step17-activate-20261114T181150Z-exy1_tap'
DISABLE = 'otp-step17-disable-20261114T192418Z-f2y4hrzi'
COUNTS = [6, 4, 4, 2, 6, 4]
FINANCIAL = ('payments', 'refunds', 'payment_gateway_transactions', 'idempotency_keys',
             'simulated_gateway_outcomes', 'webhook_events', 'reconciliation_jobs', 'reconciliation_attempts')
ACCOUNTS = ('app_users', 'user_roles', 'merchants', 'merchant_memberships', 'merchant_registrations')


def require(condition, message):
    if not condition:
        raise Stop(message)


def instant(value):
    d = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(d.tzinfo is not None, 'Timestamp evidence is missing a timezone.')
    return d.astimezone(timezone.utc)


def uncopy(value):
    if value == r'\N':
        return None
    def escaped(match):
        token = match.group(1)
        if token[0] in '01234567':
            return chr(int(token, 8))
        if token.startswith('x'):
            return chr(int(token[1:], 16))
        return {'b':'\b','f':'\f','n':'\n','r':'\r','t':'\t','v':'\v','\\':'\\'}.get(token, token)
    return re.sub(r'\\([0-7]{1,3}|x[0-9a-fA-F]{1,2}|.)', escaped, value)


def copy_rows(text, table):
    # No SQL from the archive is executed. Only public, whitelisted COPY data is parsed.
    match = re.search(r'^COPY public\.' + re.escape(table) + r' \(([^\n]+)\) FROM stdin;\n', text, re.M)
    require(match is not None, 'Archive lacks an expected public COPY table; no row-integrity claim.')
    columns = [x.strip().strip('"') for x in match.group(1).split(',')]
    require(all(re.fullmatch(r'[a-z_][a-z0-9_]*', x) for x in columns), 'Unexpected archive column syntax.')
    end = text.find('\n\\.\n', match.end())
    # Empty COPY has terminator immediately following header.
    block = text[match.end():]
    if block.startswith('\\.\n'):
        return columns, []
    require(end >= 0, 'Archive COPY data is incomplete.')
    records = []
    for line in text[match.end():end].splitlines():
        fields = line.split('\t')
        require(len(fields) == len(columns), 'Archive COPY field count mismatch.')
        records.append(dict(zip(columns, map(uncopy, fields))))
    return columns, records


def canonical(value, kind):
    if value is None:
        return None
    if kind in ('timestamp with time zone',):
        return instant(str(value)).isoformat()
    if kind in ('numeric', 'decimal', 'bigint', 'integer', 'smallint', 'real', 'double precision'):
        return str(Decimal(str(value)).normalize())
    if kind == 'boolean':
        if value in (True, 't', 'true'): return 'true'
        if value in (False, 'f', 'false'): return 'false'
        raise Stop('Invalid boolean in row comparison.')
    if kind in ('json', 'jsonb'):
        obj = json.loads(value, parse_float=Decimal) if isinstance(value, str) else value
        return stable(obj)
    # Text and UUIDs retain exact spelling. No merchant-ID normalization.
    return str(value)


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, ensure_ascii=True)


def row_counts(rows, columns, types):
    return Counter(tuple(canonical(row[c], types[c]) for c in columns) for row in rows)


def fingerprint(rows, key):
    # HMAC covers password hash + all account fields without storing the hash itself.
    return hmac.new(key, stable(rows).encode(), hashlib.sha256).hexdigest()


def session_history(user, roles, sessions, reset_at, observed):
    """Audit timestamps are observation boundaries, not reset commit timestamps.
    Never use current-version difference as the historical cohort selector.
    """
    when, now = instant(reset_at), instant(observed)
    before = [s for s in sessions if instant(s['created_at']) < when]
    boundary = [s for s in sessions if instant(s['created_at']) == when]
    after = [s for s in sessions if instant(s['created_at']) > when]
    def usable(s):
        return (user['enabled'] and bool(roles) and s['revoked_at'] is None
                and instant(s['absolute_expires_at']) > now and instant(s['idle_expires_at']) > now
                and s['authorization_version'] == user['authorization_version']
                and s['account_status'] == user['account_status']
                and s['roles_snapshot'] == ','.join(sorted(roles)))
    eligible = sum(usable(s) for s in before)
    bad = [s for s in before if s['revoked_at'] is None or instant(s['revoked_at']) > when]
    # Current-version (or future-version) rows on/before an audit boundary need ordering review.
    version_boundary = any(s['authorization_version'] >= user['authorization_version'] for s in before)
    if eligible:
        status = 'CURRENT_SECURITY_FAILURE'
    elif bad:
        status = 'REVOCATION_INCONSISTENT'
    elif boundary or version_boundary:
        status = 'AMBIGUOUS_BOUNDARY'
    elif not before:
        status = 'HISTORICAL_EVIDENCE_UNAVAILABLE'
    else:
        status = 'VERIFIED_FROM_RETAINED_ROWS'
    return {'historicalStatus':status, 'retainedPreResetFamilies':len(before),
            'postResetFamilies':len(after), 'equalTimestampFamilies':len(boundary),
            'inconsistentPreResetFamilies':len(bad), 'currentEligiblePreResetFamilies':eligible,
            'currentEligibleBoundaryFamilies':sum(usable(s) for s in boundary),
            'currentSecurityStatus':'CURRENT_SECURITY_FAILURE' if eligible else 'NO_RETAINED_PRE_RESET_FAMILY_PASSES_CURRENT_CHECKS',
            'actualJwtAcceptanceTested':False, 'deletedHistoryReconstructed':False}


def audit_accounts(snapshot, targets, expected_enabled, allow_history_limitations=False):
    users = {u['login_normalized']: u for u in snapshot['app_users']}
    roles = snapshot['user_roles']
    checks = ((REVIEWER,'ADMIN','ACTIVE'), (ADMIN,'ADMIN','ACTIVE'), (MERCHANT,'MERCHANT','PENDING_APPROVAL'))
    for name, role, status in checks:
        user = users.get(name)
        require(user is not None and user['enabled'] and user['account_status'] == status,
                'Required account missing, disabled or status changed.')
        actual = sorted(r['role_name'] for r in roles if r['user_id'] == user['user_id'])
        require(actual == [role], 'Required single-role account invariant failed.')
    root, admin, merchant = (users[name] for name in (REVIEWER, ADMIN, MERCHANT))
    require(admin['user_id'] == targets['admin'] and merchant['user_id'] == targets['merchant']
            and root['user_id'] == targets['reviewer']['id'], 'Manifest/account UUID association mismatch.')
    require(root['authorization_version'] == targets['reviewer']['version'], 'Operational Admin authorization version changed.')
    registrations = [r for r in snapshot['merchant_registrations'] if r['user_id'] == merchant['user_id']]
    require(len(registrations) == 1 and registrations[0]['email'] == MERCHANT, 'Dedicated pending registration mismatch.')
    mid = registrations[0]['merchant_id']
    registry = [r for r in snapshot['merchants'] if r['merchant_id'] == mid]
    memberships = [r for r in snapshot['merchant_memberships'] if r['user_id'] == merchant['user_id']]
    require(len(registry) == 1 and not registry[0]['active'] and not registry[0]['verified']
            and registry[0]['verified_by'] is None and registry[0]['verified_at'] is None,
            'Pending Merchant registry is unexpectedly active/verified.')
    require(len(memberships) == 1 and memberships[0]['merchant_id'] == mid and not memberships[0]['active']
            and memberships[0]['granted_by'] is None, 'Pending Merchant membership changed.')
    eligibility = snapshot['eligibility']
    enabled = {(e['user_id'],e['portal']) for e in eligibility if e['enabled']}
    expected = {(admin['user_id'],'ADMIN'), (merchant['user_id'],'MERCHANT')} if expected_enabled else set()
    require(enabled == expected, 'Enabled eligibility differs from the required pre/post scope.')
    for user, portal in ((admin,'ADMIN'), (merchant,'MERCHANT')):
        matches = [e for e in eligibility if e['user_id'] == user['user_id']]
        require(len(matches) == 1 and matches[0]['portal'] == portal
                and matches[0]['designated_by'] == root['user_id']
                and matches[0]['review_reference'] == targets['reference'], 'Scoped designation metadata mismatch.')
    resets = [e for e in snapshot['audit'] if e['event_type'] == 'LOCAL_DEMO_PASSWORD_RESET' and e['outcome'] == 'SUCCESS']
    require(not any(e['resource_id'] not in (admin['user_id'],merchant['user_id']) for e in resets),
            'Unexpected successful reset for an operational/non-designated account.')
    creation = [e for e in snapshot['audit'] if e['event_type'] == 'ACCOUNT_CREATED'
                and e['outcome'] == 'SUCCESS' and e['resource_id'] == admin['user_id']]
    require(len(creation) == 1 and creation[0]['actor_user_id'] == root['user_id']
            and creation[0]['actor_identifier'] == REVIEWER and creation[0]['resource_type'] == 'ACCOUNT'
            and creation[0]['metadata'].get('role') == 'ADMIN', 'Additional Admin creation lacks the real expected actor audit.')
    require(instant(admin['created_at']) <= instant(creation[0]['occurred_at']) <= instant(snapshot['collectedAt']), 'Admin creation audit timestamp is inconsistent.')
    summary = {}
    for label, user in (('admin',admin), ('merchant',merchant)):
        events = [e for e in resets if e['resource_id'] == user['user_id']]
        require(len(events) == 1, 'Expected exactly one successful reset for each dedicated account; investigate actual counts.')
        event = events[0]
        require(event['actor_user_id'] is None and event['actor_identifier'] is None
                and event['resource_type'] == 'ACCOUNT'
                and event['metadata'] == {'source':'insecure_local_demo_on_screen_otp'}, 'Recovery audit source/actor metadata mismatch.')
        when = instant(event['occurred_at'])
        require(instant(user['created_at']) <= when <= instant(snapshot['collectedAt']), 'Recovery audit timestamp is inconsistent.')
        require(user['authorization_version'] >= 1, 'Successful reset requires a positive current authorization version.')
        assigned = [r['role_name'] for r in roles if r['user_id'] == user['user_id']]
        history = session_history(user, assigned,
                                  [r for r in snapshot['sessions'] if r['user_id'] == user['user_id']],
                                  event['occurred_at'], snapshot['collectedAt'])
        require(history['historicalStatus'] not in ('CURRENT_SECURITY_FAILURE','REVOCATION_INCONSISTENT'),
                'Retained pre-reset session revocation/current security failure.')
        if not allow_history_limitations:
            require(history['historicalStatus'] == 'VERIFIED_FROM_RETAINED_ROWS',
                    'Historical session evidence unavailable/ambiguous; strict certification cannot pass.')
        version_events = [e for e in snapshot['audit'] if e['resource_id']==user['user_id']
                          and e['outcome']=='SUCCESS' and e['event_type'] in
                          ('ACCOUNT_ENABLED','ACCOUNT_DISABLED','MEMBERSHIP_ASSIGNED','MEMBERSHIP_REVOKED','ADMIN_PASSWORD_RECOVERED')]
        version_status = 'SINGLE_RESET_VERSION' if user['authorization_version']==1 else 'ADDITIONAL_INCREMENT_UNEXPLAINED'
        # These events are possible contributors, not an exact change log: logout-all has no such audit.
        if not allow_history_limitations:
            require(version_status == 'SINGLE_RESET_VERSION', 'Additional authorization increment needs documented review.')
        challenges = {c['challenge_id']: c for c in snapshot['challenges'] if c['user_id'] == user['user_id']}
        old_grants = [g for g in snapshot['grants'] if g['challenge_id'] in challenges
                      and challenges[g['challenge_id']]['authorization_version'] < user['authorization_version']]
        require(all(g['consumed_at'] is not None for g in old_grants), 'Pre-reset grant remains unconsumed.')
        if not allow_history_limitations:
            require(old_grants, 'Retained grant history unavailable for strict certification.')
        summary[label] = {'successfulResets':len(events), 'resetAt':event['occurred_at'],
                          'authorizationVersion':user['authorization_version'], **history,
                          'priorFamiliesRevoked':history['retainedPreResetFamilies'],
                          'oldGrantsConsumed':len(old_grants),
                          'grantHistoryStatus':'RETAINED_CONSUMED_OLD_VERSION_GRANTS' if old_grants else 'HISTORICAL_EVIDENCE_UNAVAILABLE',
                          'versionHistoryStatus':version_status,
                          'possibleVersionAuditEvents':[{'type':e['event_type'],'at':e['occurred_at']} for e in version_events]}
    if not expected_enabled:
        # Strong postcondition: no outstanding unconsumed record, even expired, for any account.
        require(all(c['consumed_at'] is not None for c in snapshot['challenges'])
                and all(g['consumed_at'] is not None for g in snapshot['grants']),
                'Outstanding recovery challenges/grants remain; investigate without broad SQL changes.')
    return summary


class Closeout(Ops):
    def __init__(self, mode):
        super().__init__('verify-' + mode)
        self.phase = mode
        self.baseline_file = self.private / 'phase673-closeout-pre.json'

    def sql(self, sql, write=False):
        require(not write, 'Read-only verifier cannot perform a write.')
        wrapped = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL timezone='UTC'; SET LOCAL statement_timeout='20s'; " + sql + '; COMMIT;'
        return super().sql(wrapped, write=False)

    def read_evidence(self):
        self.deploy = json.loads(protected(self.private / DEPLOY / 'evidence.json').read_text())
        self.activation = json.loads(protected(self.private / ACTIVATE / 'evidence.json').read_text())
        for data, mode in ((self.deploy,'deploy'),(self.activation,'activate')):
            require(data.get('success') is True and data.get('mode') == mode, 'Expected successful protected deployment/activation evidence.')
        self.targets = json.loads(protected(self.manifest).read_text())
        require(self.activation.get('dedicatedTargets') == {k:self.targets[k] for k in ('admin','merchant')}, 'Activation/manifest target mismatch.')
        for key in ('admin','merchant'): identifier(self.targets[key])
        if self.phase == 'final':
            self.deactivation = json.loads(protected(self.private / DISABLE / 'evidence.json').read_text())
            require(self.deactivation.get('success') is True and self.deactivation.get('mode')=='disable'
                    and self.deactivation.get('recoveryEnabled') is False
                    and self.deactivation.get('afterCounts')==COUNTS
                    and self.deactivation.get('dedicatedTargets')=={k:self.targets[k] for k in ('admin','merchant')},
                    'Successful authentic disabled-state evidence is required for final mode.')

    def snapshot(self):
        # Whole comparisons need account password hashes in memory, not in output/evidence.
        parts = {t:'SELECT * FROM public.' + t for t in FINANCIAL + ACCOUNTS}
        parts.update({
            'eligibility':'SELECT user_id,portal,enabled,designated_by,review_reference FROM public.demo_recovery_eligibility',
            'sessions':'SELECT user_id,authorization_version,account_status,roles_snapshot,created_at,absolute_expires_at,idle_expires_at,revoked_at FROM public.auth_sessions',
            'challenges':'SELECT challenge_id,user_id,portal,authorization_version,created_at,expires_at,consumed_at FROM public.password_recovery_challenges',
            'grants':'SELECT challenge_id,expires_at,consumed_at FROM public.password_reset_authorizations',
            'audit':"SELECT actor_user_id,actor_identifier,event_type,resource_id,resource_type,outcome,metadata,occurred_at FROM public.security_audit_events WHERE event_type IN ('LOCAL_DEMO_PASSWORD_RESET','ACCOUNT_CREATED','ACCOUNT_ENABLED','ACCOUNT_DISABLED','MEMBERSHIP_ASSIGNED','MEMBERSHIP_REVOKED','ADMIN_PASSWORD_RECOVERED')",
            'types':"SELECT table_name,column_name,data_type FROM information_schema.columns WHERE table_schema='public'"})
        fields = ["'collectedAt',CURRENT_TIMESTAMP"]
        for name, query in parts.items():
            fields.append("'"+name+"',COALESCE((SELECT json_agg(row_to_json(t)) FROM ("+query+") t),'[]'::json)")
        return json.loads(self.sql('SELECT json_build_object(' + ','.join(fields) + ')'), parse_float=Decimal)

    def compare_backup(self, snapshot, backup=None, exact_accounts=False, label='preOtp'):
        self.stage = 'archive-row-comparison'
        backup = self.activation['backup'] if backup is None else backup
        directory = protected(self.private / 'backups', 0o700)
        path = protected(backup['path'])
        require(path.resolve().is_relative_to(directory.resolve()), 'Backup path outside protected demo backups.')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == backup['sha256'], 'Pre-OTP backup checksum mismatch.')
        self.command([PG/'pg_restore', '--list', path])
        for table in FINANCIAL + ACCOUNTS:
            archive = self.command([PG/'pg_restore', '--data-only', '--table='+table, '--file=-', path]) + '\n'
            columns, original = copy_rows(archive, table)
            types = {r['column_name']:r['data_type'] for r in snapshot['types'] if r['table_name']==table}
            require(set(columns) == set(types), 'Backup/live column set differs; cannot claim full row comparison.')
            old = row_counts(original, columns, types)
            current = row_counts(snapshot[table], columns, types)
            if table in FINANCIAL:
                require(old == current, 'Financial row-content mismatch against protected archive; investigate privately.')
            elif exact_accounts:
                require(old == current, 'Account row-content mismatch against pre-deactivation archive; investigate privately.')
            else:
                require(not (old - current), 'Existing account/registry/membership/registration row changed from pre-OTP archive.')
        self.evidence.setdefault('archiveComparisons',{})[label] = {'financialTables':list(FINANCIAL),'allAccountRowsExact':exact_accounts,'matched':True,'testRestorePerformed':False}
        self.evidence['financialRowComparison'] = {'tables':list(FINANCIAL), 'matched':True, 'testRestorePerformed':False}
        self.evidence['existingAccountRowsMatchedBackup'] = True

    def compare_pre_post(self, snapshot):
        # New passwords are preserved across deactivation by private keyed fingerprints,
        # not stored hashes, password re-entry or authentication probes.
        rows = {t: sorted(snapshot[t], key=stable) for t in ACCOUNTS + FINANCIAL}
        preserved_flags = {k:v for k,v in self.flags.items() if not k.startswith('paymesh.demo.password-recovery.') and k != 'spring.config.additional-location'}
        if self.baseline_file.exists():
            previous = json.loads(protected(self.baseline_file).read_text())
            key = bytes.fromhex(previous['comparisonKey'])
            require(previous['configurationFingerprint'] == fingerprint(preserved_flags,key), 'Persistent session/JWT/AI/scheduling launch settings changed.')
            expected = previous['fingerprints']
            require(expected == {t:fingerprint(r,key) for t,r in rows.items()},
                    'Pre/post account or financial row fingerprint mismatch; no secret details printed.')
            for kind in ('frontend','ai','llm'):
                require(self.services[kind] == previous['services'][kind], 'Preserved service identity differs from pre-audit.')
        else:
            require(self.phase == 'pre', 'Run and pass the pre-deactivation audit first; no baseline is available.')
            key = secrets.token_bytes(32)
            previous = {'comparisonKey':key.hex(), 'configurationFingerprint':fingerprint(preserved_flags,key), 'fingerprints':{t:fingerprint(r,key) for t,r in rows.items()},
                        'services':self.services, 'collectedAt':snapshot['collectedAt']}
            self.private_json(self.baseline_file, previous)
        self.evidence['prePostRowsMatched'] = self.phase in ('post','final')

    def final_comparisons(self, snapshot):
        comparisons = {}
        backup = self.deactivation.get('backup')
        if backup and Path(backup['path']).exists():
            self.compare_backup(snapshot, backup=backup, exact_accounts=True, label='preDeactivation')
            comparisons['preDeactivationArchive'] = 'VERIFIED_EXACT_ACCOUNT_PASSWORD_AND_FINANCIAL_ROWS'
        else:
            comparisons['preDeactivationArchive'] = 'UNAVAILABLE'
        comparisons['activationDeactivationFingerprints'] = 'UNAVAILABLE_NOT_RECORDED'
        if self.baseline_file.exists():
            # A baseline file alone does not prove a completed pre-audit.
            baseline = json.loads(protected(self.baseline_file).read_text())
            authentic = False
            for file in self.private.glob('otp-step17-verify-pre-*/evidence.json'):
                record = json.loads(protected(file).read_text())
                if (record.get('success') is True and record.get('mode')=='verify-pre'
                        and record.get('stage')=='read-only-pre-verified'
                        and record.get('preBaselineReference')==str(self.baseline_file)
                        and instant(record['startedAt']) <= instant(baseline['collectedAt'])
                        and instant(baseline['collectedAt']) < instant(self.deactivation['startedAt'])):
                    authentic = True
            require(authentic, 'Pre-audit fingerprint file lacks successful authentic pre-audit provenance.')
            self.compare_pre_post(snapshot)
            comparisons['preAuditFingerprints'] = 'VERIFIED_AUTHENTIC_BASELINE'
        else:
            comparisons['preAuditFingerprints'] = 'UNAVAILABLE_NO_SUCCESSFUL_PRE_AUDIT'
        self.evidence['comparisons'] = comparisons
        self.evidence['historicalLimitations'] = [
            'Deleted/never-created pre-reset families cannot be reconstructed.',
            'No live JWT acceptance/replay was tested; legacy no-sid tokens are not inventoried.',
            'Password matching and 30 browser checks remain operator-confirmed evidence.']
        for label,row in self.evidence['recoveryAudit'].items():
            if row['historicalStatus']!='VERIFIED_FROM_RETAINED_ROWS':
                self.evidence['historicalLimitations'].append(label+': '+row['historicalStatus'])
            if row['grantHistoryStatus']=='HISTORICAL_EVIDENCE_UNAVAILABLE':
                self.evidence['historicalLimitations'].append(label+': grant history unavailable')
            if row['versionHistoryStatus']!='SINGLE_RESET_VERSION':
                self.evidence['historicalLimitations'].append(label+': '+row['versionHistoryStatus'])
        for name,status in comparisons.items():
            if status.startswith('UNAVAILABLE'):
                self.evidence['historicalLimitations'].append(name+': '+status)

    def closeout(self, success):
        if self.phase != 'final':
            return super().closeout(success)
        self.evidence.update({'success':success,'stage':self.stage,'strictFullCertification':False})
        if hasattr(self,'index_before'):
            self.evidence['indexPreserved']=hashlib.sha256((self.repo/'.git/index').read_bytes()).hexdigest()==self.index_before
            self.evidence['stagedPreserved']=self.command(['/usr/bin/git','-C',self.repo,'diff','--cached','--binary'])==self.staged_before
        path=self.run_dir/'evidence.json'
        self.private_json(path,self.evidence)
        with self.report.open('a') as out:
            out.write('\n## Operator final read-only audit evidence\n\n')
            out.write(('Current checks verified with documented evidence limitations' if success else 'Stopped; final verification failed')+'. Strict full certification is not claimed. Protected evidence: `'+str(path)+'`. No reset/deactivation/restart/financial action performed.\n')
        self.db_password=None
        print(('VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS' if success else 'FINAL_VERIFICATION_FAILED')+'. Evidence: '+str(path))

    def run(self):
        self.read_evidence()
        self.preflight()  # All SQL goes through this class's read-only transaction override.
        expected = self.phase == 'pre'
        require(self.enabled_before is expected and self.flags.get('paymesh.demo.password-recovery.enabled') == str(expected).lower(),
                'Capabilities/launch flag differ from requested pre/post state.')
        require(self.before == COUNTS, 'Actual entity counts differ from 6/4/4/2/6/4.')
        for kind in ('frontend','ai','llm'):
            require(self.services[kind] == self.activation['beforeServices'][kind], 'Preserved service differs from successful activation evidence.')
        if expected:
            require(self.services['java']['pid'] == str(self.activation['newJavaPid']), 'Java process changed since activation; review before pre-audit.')
        if self.phase == 'final':
            require(self.services['java']['pid']==str(self.deactivation['newJavaPid']), 'Java identity differs from the successful disabled deployment.')
            require(self.jar_sha==self.deactivation['artifactSha256'], 'Artifact differs from the disabled deployment.')
        self.stage = 'read-only-snapshot'
        snapshot = self.snapshot()
        actual = [len(snapshot[t]) for t in ('app_users','merchants','merchant_memberships','merchant_registrations','payments','refunds')]
        self.evidence['actualCounts'] = actual
        require(actual == COUNTS, 'Snapshot entity counts changed during audit.')
        # Safe summary only; raw records never enter persistent evidence.
        self.evidence['authorizationVersions'] = {label:next((u['authorization_version'] for u in snapshot['app_users'] if u['login_normalized']==name),None) for label,name in (('operationalAdmin',REVIEWER),('dedicatedAdmin',ADMIN),('dedicatedMerchant',MERCHANT))}
        self.evidence['actualSuccessfulResetCounts'] = {
            label:sum(e['event_type']=='LOCAL_DEMO_PASSWORD_RESET' and e['outcome']=='SUCCESS' and e['resource_id']==self.targets[label] for e in snapshot['audit'])
            for label in ('admin','merchant')}
        print('Successful reset counts admin|merchant: ' + str(self.evidence['actualSuccessfulResetCounts']['admin']) + '|' + str(self.evidence['actualSuccessfulResetCounts']['merchant']))
        self.evidence['recoveryAudit'] = audit_accounts(snapshot, self.targets, expected, allow_history_limitations=self.phase=='final')
        self.compare_backup(snapshot)
        for prefix in ('','proxy:'):
            require(self.http_json(prefix+'/api/v1/payments/health')[0] == 200, 'Payment health failed.')
        require(self.http_json('/actuator/health/readiness')[1].get('status') == 'UP', 'Java readiness failed.')
        with self.http.open(urllib.request.Request('http://127.0.0.1:5500/', method='GET'), timeout=10) as response:
            require(response.status == 200, 'Frontend landing page unavailable.')
            response.read(1024)
        self.unchanged_other_services()
        require(self.service(18080,self.repo/'backend','java') == self.services['java'], 'Java identity changed during audit.')
        require(self.http_json('proxy:/api/v1/auth/password/capabilities')[1].get('localDemoEnabled') is expected,
                'Recovery capability changed during audit.')
        if self.phase == 'final':
            self.final_comparisons(snapshot)
        else:
            self.compare_pre_post(snapshot)
        self.stage = 'read-only-' + self.phase + '-verified'
        self.evidence['preBaselineReference'] = str(self.baseline_file) if self.phase!='final' or self.baseline_file.exists() else None
        self.evidence['result'] = 'VERIFIED_WITH_DOCUMENTED_EVIDENCE_LIMITATIONS' if self.phase=='final' else 'Verified read-only ' + self.phase + ' closeout audit'
        self.evidence['recoveryEnabled'] = expected
        print('Counts users|merchants|memberships|registrations|payments|refunds: 6|4|4|2|6|4')
        print('Current account/eligibility/reset-audit/grant checks: VERIFIED')
        for label, row in self.evidence['recoveryAudit'].items():
            print(label + ': ' + row['historicalStatus'] + '; ' + row['versionHistoryStatus'])
        print('Financial row contents: MATCH (8 pre-OTP archive tables; no restore)')
        print('Capabilities localDemoEnabled=' + str(expected).lower() + '; readiness/health/frontend: PASS')
        if self.phase == 'post': print('Pre/post account/password/financial fingerprints and preserved services: MATCH')
        if self.phase == 'final':
            for name,status in self.evidence['comparisons'].items(): print(name+': '+status)


def main():
    os.umask(0o077)
    if len(sys.argv)!=2 or sys.argv[1] not in ('pre','post','final') or not sys.stdin.isatty() or not sys.stdout.isatty():
        print('Operator-only: verify-phase673-closeout.sh pre|post|final in a private Terminal.', file=sys.stderr)
        return 1
    audit = None
    try:
        audit = Closeout(sys.argv[1]); audit.run(); audit.closeout(True); return 0
    except Stop as error:
        print(str(error), file=sys.stderr)
    except (Exception,KeyboardInterrupt):
        print('Read-only audit failed/interrupted; inspect protected evidence. No secrets or raw errors are displayed.', file=sys.stderr)
    if audit:
        try: audit.closeout(False)
        except Exception: print('Could not save private audit evidence.', file=sys.stderr)
    return 1

if __name__ == '__main__':
    sys.exit(main())
