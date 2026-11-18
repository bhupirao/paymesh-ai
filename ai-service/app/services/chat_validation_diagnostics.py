"""Opt-in local, bounded reason-only evidence. Never a public response or ordinary logger."""
import fcntl
import json
import os
from pathlib import Path
import stat
from uuid import UUID

REASONS = frozenset({
    'INVALID_JSON', 'DUPLICATE_JSON_KEY', 'SCHEMA_MISMATCH', 'INVALID_VARIANT',
    'INTENT_MISMATCH', 'KNOWLEDGE_ALIAS_MISMATCH', 'EVIDENCE_ALIAS_MISMATCH',
    'OTHER_VALIDATION_FAILURE',
})
SCHEMA_REASONS = frozenset({'SCHEMA_MISMATCH', 'INVALID_VARIANT'})
SCHEMA_FAILURE_CODES = frozenset({
    'REQUIRED_FIELD_MISSING', 'FIELD_TYPE_MISMATCH', 'EXTRA_FIELD_FORBIDDEN',
    'ENUM_VALUE_INVALID', 'NESTED_STRUCTURE_INVALID', 'ROOT_STRUCTURE_INVALID',
    'MULTIPLE_SCHEMA_FAILURES', 'UNKNOWN_SCHEMA_FAILURE',
})
MAX_BYTES = 65536
FILENAME = 'chat-validation-diagnostics.jsonl'


def _owned(info, mode, directory=False):
    correct_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not correct_type or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != mode:
        raise ValueError('Protected diagnostic sink required')
    if not directory and info.st_nlink != 1:
        raise ValueError('Protected diagnostic sink required')


def _open_sink(value):
    root = Path.home() / '.config/paymesh-demo'
    path = Path(value)
    if not path.is_absolute() or path.name != FILENAME:
        raise ValueError('Protected diagnostic sink required')
    parts = path.relative_to(root).parts
    if not parts or any(p in ('.', '..') for p in parts):
        raise ValueError('Protected diagnostic sink required')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    fd = None
    try:
        _owned(os.fstat(directory), 0o700, directory=True)
        for name in parts[:-1]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
            _owned(os.fstat(directory), 0o700, directory=True)
        fd = os.open(parts[-1], os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW, dir_fd=directory)
        _owned(os.fstat(fd), 0o600)
        result, fd = fd, None
        return result
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        os.close(directory)


def validate_sink(value):
    """Startup validation opens an existing dedicated file, without writing/creating it."""
    if value is None:
        return None
    try:
        fd = _open_sink(value)
        os.close(fd)
    except (OSError, ValueError, TypeError):
        raise ValueError('Existing owner-only local diagnostic file required') from None
    return value


def valid_correlation(value):
    """Canonical UUIDv4 only; no arbitrary diagnostic text or identifiers."""
    try:
        parsed = UUID(value) if isinstance(value, str) and len(value) == 36 else None
        return parsed is not None and parsed.version == 4 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


def schema_failure_code(issues):
    """Map structured labels only. Never emit locations, names, messages or input.

    Same-category errors collapse to one code; mixed known categories have a
    fixed MULTIPLE code. Unknown/malformed/oversized error sets remain UNKNOWN.
    """
    unknown = 'UNKNOWN_SCHEMA_FAILURE'
    if not isinstance(issues, list) or not 1 <= len(issues) <= 32:
        return unknown
    categories = set()
    for issue in issues:
        if not isinstance(issue, dict):
            return unknown
        kind, loc = issue.get('type'), issue.get('loc')
        if not isinstance(loc, tuple) or not isinstance(kind, str):
            return unknown
        known_field = len(loc) == 1 and loc[0] in ('intent', 'variant', 'evidence', 'knowledge')
        if loc == () and kind in ('model_type', 'model_attributes_type'):
            code = 'ROOT_STRUCTURE_INVALID'
        elif kind == 'extra_forbidden' and len(loc) == 1:
            code = 'EXTRA_FIELD_FORBIDDEN'
        elif known_field and kind == 'missing':
            code = 'REQUIRED_FIELD_MISSING'
        elif loc == ('variant',) and kind == 'literal_error':
            code = 'ENUM_VALUE_INVALID'
        elif known_field and kind in ('string_type', 'list_type'):
            code = 'FIELD_TYPE_MISMATCH'
        elif len(loc) == 2 and loc[0] in ('evidence', 'knowledge') and type(loc[1]) is int and loc[1] >= 0 and kind == 'string_type':
            code = 'NESTED_STRUCTURE_INVALID'
        else:
            return unknown
        categories.add(code)
    return next(iter(categories)) if len(categories) == 1 else 'MULTIPLE_SCHEMA_FAILURES'


def record(config, reason, correlation_id=None, schema_failure_code=None):
    """Best effort, fixed code only; sink failure must never change the public fallback."""
    if reason not in REASONS or not valid_correlation(correlation_id):
        return False
    payload = {'correlationId': correlation_id, 'reasonCode': reason}
    if reason in SCHEMA_REASONS:
        code = 'UNKNOWN_SCHEMA_FAILURE' if schema_failure_code is None else schema_failure_code
        if not isinstance(code, str) or code not in SCHEMA_FAILURE_CODES:
            return False
        payload['schemaFailureCode'] = code
    elif schema_failure_code is not None:
        return False
    fd = None
    try:
        value = config.chat_validation_diagnostics_file
        if not value:
            return False
        fd = _open_sink(value)  # Recheck ownership/type/permissions for every append.
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        row = (json.dumps(payload, separators=(',', ':')) + '\n').encode('ascii')
        if os.fstat(fd).st_size + len(row) > MAX_BYTES:
            return False
        return os.write(fd, row) == len(row)
    except Exception:
        # No exception text, paths, model content or fallback-to-console logging.
        return False
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
