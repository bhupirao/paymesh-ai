"""One operator-approved synthetic inference; protected correlation, no DB or retries.

Only sanitized status/code reaches the terminal. Existing public correlation fields
remain unchanged; diagnostic correlation and reasons are protected operational data.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import uuid
from phase673_otp_ops import Stop, protected
from phase697a_process import MacOS, snapshot, assert_same

REASONS = frozenset({'INVALID_JSON', 'DUPLICATE_JSON_KEY', 'SCHEMA_MISMATCH', 'INVALID_VARIANT',
    'INTENT_MISMATCH', 'KNOWLEDGE_ALIAS_MISMATCH', 'EVIDENCE_ALIAS_MISMATCH', 'OTHER_VALIDATION_FAILURE'})
SCHEMA_REASONS = frozenset({'SCHEMA_MISMATCH', 'INVALID_VARIANT'})
SCHEMA_FAILURE_CODES = frozenset({
    'REQUIRED_FIELD_MISSING', 'FIELD_TYPE_MISMATCH', 'EXTRA_FIELD_FORBIDDEN',
    'ENUM_VALUE_INVALID', 'NESTED_STRUCTURE_INVALID', 'ROOT_STRUCTURE_INVALID',
    'MULTIPLE_SCHEMA_FAILURES', 'UNKNOWN_SCHEMA_FAILURE',
})
MAX_BYTES = 65536
SOURCE_FILES = frozenset({'app/config.py', 'app/services/chat_service.py', 'app/services/chat_validation_diagnostics.py'})


def correlation(value):
    try:
        p = uuid.UUID(value) if isinstance(value, str) and len(value) == 36 else None
        return p is not None and p.version == 4 and str(p) == value
    except (ValueError, TypeError):
        return False


def unique_pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Stop('Duplicate protected JSON key.')
        result[key] = value
    return result


def matching_record(raw, request_id, require_schema_code=False):
    """Validate all rows; unrelated valid records are never attributed to this request."""
    if not correlation(request_id) or len(raw) > MAX_BYTES:
        raise Stop('Invalid diagnostic evidence size or identity.')
    found = {}; seen = set()
    try:
        for line in raw.splitlines():
            row = json.loads(line, object_pairs_hook=unique_pairs)
            if not isinstance(row, dict) or set(row) not in ({'correlationId', 'reasonCode'}, {'correlationId', 'reasonCode', 'schemaFailureCode'}) or not correlation(row['correlationId']) or not isinstance(row['reasonCode'], str) or row['reasonCode'] not in REASONS:
                raise Stop('Missing or invalid diagnostic correlation/reason.')
            if 'schemaFailureCode' in row and (row['reasonCode'] not in SCHEMA_REASONS or not isinstance(row['schemaFailureCode'], str) or row['schemaFailureCode'] not in SCHEMA_FAILURE_CODES):
                raise Stop('Invalid fixed schema failure code.')
            cid = row['correlationId']
            if cid in seen:
                raise Stop('Duplicate diagnostic correlation; attribution rejected.')
            seen.add(cid)
            if cid == request_id:
                found = row
    except Stop:
        raise
    except Exception:
        raise Stop('Malformed protected diagnostic evidence.') from None
    if require_schema_code and found.get('reasonCode') in SCHEMA_REASONS and 'schemaFailureCode' not in found:
        raise Stop('Matching schema diagnostic lacks a fixed category.')
    return found


def matching_reason(raw, request_id):
    return matching_record(raw, request_id).get('reasonCode')


def read_sink(path, private):
    """Read using owner-only directory descriptors; never follow links or print content."""
    try:
        if not path.is_absolute() or path.name != 'chat-validation-diagnostics.jsonl':
            raise Stop('Unexpected diagnostic path.')
        parts = path.relative_to(private).parts
        if any(p in ('.', '..') for p in parts):
            raise Stop('Unexpected diagnostic path.')
        directory = os.open(private, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = None
        try:
            def owned(info, mode, folder=False):
                kind = stat.S_ISDIR(info.st_mode) if folder else stat.S_ISREG(info.st_mode)
                if not kind or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode or (not folder and info.st_nlink != 1):
                    raise Stop('Protected diagnostic ownership/mode differs.')
            owned(os.fstat(directory), 0o700, True)
            for part in parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory); directory = child
                owned(os.fstat(directory), 0o700, True)
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            info = os.fstat(fd); owned(info, 0o600)
            with os.fdopen(fd, 'rb') as stream:
                fd = None; raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise Stop('Diagnostic evidence exceeds limit.')
            return (info.st_dev, info.st_ino), raw
        finally:
            if fd is not None:os.close(fd)
            os.close(directory)
    except Stop:raise
    except Exception:raise Stop('Protected diagnostic evidence unavailable.') from None


def properties(path, private):
    if not path.is_absolute() or not path.resolve().is_relative_to(private.resolve()):
        raise Stop('Unreviewed configuration location.')
    info = protected(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1048576:
        raise Stop('Unreviewed protected configuration.')
    result = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith('#'):continue
        key, sep, value = line.partition('=')
        if not sep or key != key.strip() or key in result or '\\' in line:
            raise Stop('Unsupported protected property encoding.')
        result[key] = value
    return result


def credentials(python, java, private, diagnostic):
    """Binary environment values retain whitespace and equals signs exactly."""
    if python.argv[1:] != ('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'):
        raise Stop('Unreviewed Python launch arguments.')
    env = python.environment
    expected = {'PAYMESH_AI_ANALYSIS_MODE':'RAG_LLM', 'PAYMESH_AI_CHAT_API_ENABLED':'true',
        'PAYMESH_AI_GENERATION_ENABLED':'true', 'PAYMESH_AI_INFERENCE_URL':'http://127.0.0.1:8082/v1/chat/completions',
        'PAYMESH_AI_MODEL_NAME':'paymesh-qwen', 'PAYMESH_AI_GENERATION_TIMEOUT':'30',
        'PAYMESH_AI_CHAT_VALIDATION_DIAGNOSTICS_FILE':str(diagnostic)}
    if any(env.get(k) != v for k,v in expected.items()):
        raise Stop('Running Python diagnostic/generation configuration differs.')
    if java.argv[1:2] != ('-jar',):raise Stop('Unreviewed Java launch layout.')
    flags = {}
    for item in java.argv[3:]:
        key, sep, value = item.removeprefix('--').partition('=')
        if not item.startswith('--') or not sep or key in flags:
            raise Stop('Unreviewed Java launch flags.')
        flags[key] = value
    # Avoid unreviewed environment precedence or injected JVM options.
    if any(k in java.environment for k in ('SPRING_APPLICATION_JSON','JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','SPRING_CONFIG_LOCATION','SPRING_CONFIG_ADDITIONAL_LOCATION')):
        raise Stop('Unreviewed Java environment override.')
    props = {}
    for name in ('spring.config.location','spring.config.additional-location'):
        for location in flags.get(name,'').split(','):
            if location == 'classpath:/application.properties':continue
            if not location.startswith('file:'):raise Stop('Unreviewed configuration location.')
            props.update(properties(Path(location[5:]),private))
    props.update(flags)
    if any(props.get(k) != v for k,v in {'paymesh.ai.chat.enabled':'true','paymesh.demo.password-recovery.enabled':'false','paymesh.demo.checkout-controls.enabled':'false'}.items()):
        raise Stop('Java safety configuration differs.')
    key = env.get('PAYMESH_AI_CHAT_SERVICE_TOKEN','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{64,128}',key) or not hmac.compare_digest(key,props.get('paymesh.ai.chat.service-token','')):
        raise Stop('Private service credentials missing or inconsistent.')
    override = java.environment.get('PAYMESH_AI_CHAT_SERVICE_TOKEN',key)
    if not hmac.compare_digest(key,override):raise Stop('Private service credential override differs.')
    return key


def run(op):
    # Normal verifier run() has already checked loopback listeners/cwd and confirmation.
    path = Path(input('Protected diagnostic activation evidence path: ').strip()).expanduser()
    if not path.is_absolute() or not path.resolve().is_relative_to(op.private.resolve()):
        raise Stop('Activation evidence must remain protected.')
    evidence = json.loads(protected(path).read_text(), object_pairs_hook=unique_pairs)
    expected = dict(evidence.get('beforeServices',{})); expected['ai'] = evidence.get('newPythonIdentity')
    if evidence.get('success') is not True or evidence.get('diagnosticsEnabled') is not True or op.services != expected:
        raise Stop('Successful diagnostic activation/service identity does not match.')
    hashes = evidence.get('sourceHashes',{})
    if set(hashes) != SOURCE_FILES or any(hashlib.sha256((op.repo/'ai-service'/name).read_bytes()).hexdigest()!=digest for name,digest in hashes.items()):
        raise Stop('Diagnostic patch/reload evidence differs; a reviewed Python reload is required.')
    native = MacOS()
    snapshots = {name:snapshot(int(op.services[name]['pid']),native) for name in ('ai','java','llm')}
    native_expected = evidence.get('nativeProcessIdentities',{})
    if set(native_expected) != set(snapshots) or any(list(saved.identity) != native_expected[name] for name,saved in snapshots.items()):
        raise Stop('Microsecond process identity baseline missing or changed; reviewed activation evidence required.')
    # Bind kernel microsecond identities to the listener/working-directory identities.
    op.services_checked()
    if op.services != expected:raise Stop('Service identity changed during snapshot.')
    for saved in snapshots.values():assert_same(saved,native)
    diagnostic = Path(evidence['diagnosticFile'])
    if diagnostic.parent != path.parent:raise Stop('Unexpected diagnostic evidence directory.')
    key = credentials(snapshots['ai'],snapshots['java'],op.private,diagnostic)
    if (op.repo/'ai-service/.env').exists():raise Stop('Unexpected Python dotenv configuration.')
    request_id = str(uuid.uuid4())
    inode,before = read_sink(diagnostic,op.private)
    if matching_reason(before,request_id) is not None:raise Stop('Diagnostic request identity already exists.')
    op.evidence['diagnosticCorrelationId'] = request_id
    # No locks or process changes; unrelated requests are separated by correlation.
    for saved in snapshots.values():assert_same(saved,native)
    try:
        op.internal(correlation_id=request_id,key_override=key)
    finally:
        key = ''
        after_inode,after = read_sink(diagnostic,op.private)
        if after_inode != inode or not after.startswith(before):
            raise Stop('Diagnostic evidence replaced or truncated; attribution rejected.')
        record = matching_record(after,request_id,require_schema_code=True)
        reason = record.get('reasonCode')
        schema_code = record.get('schemaFailureCode')
        if reason is not None and op.evidence.get('generation',{}).get('actualInferenceProven') is True:
            raise Stop('Successful generation conflicts with a validation diagnostic; attribution rejected.')
        op.evidence['diagnosticSchemaFailureCode'] = schema_code
        op.evidence['diagnosticReasonCode'] = reason
        op.evidence['diagnosticAttribution'] = 'MATCHED_REQUEST' if reason else 'NO_MATCHING_RECORD'
        # Correlation IDs stay in protected evidence; only a fixed code reaches terminal.
        print('DIAGNOSTIC_REASON='+ (reason if reason else 'NO_MATCHING_RECORD'))
        if reason in SCHEMA_REASONS:
            print('SCHEMA_FAILURE_CODE='+ (schema_code if schema_code else 'NOT_RECORDED'))
        for saved in snapshots.values():assert_same(saved,native)
