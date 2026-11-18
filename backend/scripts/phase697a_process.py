"""macOS-only, read-only launch snapshot. No textual environment parsing or secret output.

KERN_PROCARGS2 is a native-int argc, executable NUL/padding, argc NUL-delimited
arguments, then NUL-delimited environment entries and alignment/Apple auxiliary
strings (some values are erased by libpthread). Only reviewed auxiliary forms are
accepted; unsupported/malformed/ambiguous layouts fail closed. This inventories kernel-exposed launch state, not later application getenv edits.
"""
import ctypes
import os
import re
import struct
import sys
from dataclasses import dataclass, field
from phase673_otp_ops import Stop

MAX_BYTES = 1024 * 1024

# Local SDK sys/sysctl.h defines KERN_PROCARGS2=49; the complete layout is in
# Apple XNU bsd/kern/kern_sysctl.c:sysctl_procargsx and kern_exec.c:
# exec_extract_strings / exec_add_apple_strings. The stack string area includes
# argv, env, alignment and apple[]; it is not an env-only buffer.
# https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_exec.c
# https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_sysctl.c
# libpthread src/pthread.c:parse_{main_stack,ptr_munge}_params and
# parse_main_thread_port zero VALUE bytes in place, leaving keys/NUL runs.
# https://github.com/apple-oss-distributions/libpthread/blob/main/src/pthread.c
_HEX = rb'0x[0-9a-fA-F]{1,16}'
_AUXILIARY = {
    b'ptr_munge': rb'(?:' + _HEX + rb')?',
    b'main_stack': rb'(?:' + _HEX + (rb',' + _HEX) * 3 + rb')?',
    b'executable_file': _HEX + rb',' + _HEX,
    b'dyld_file': _HEX + rb',' + _HEX,
    b'executable_cdhash': rb'[0-9a-fA-F]{40}',
    b'executable_boothash': rb'[0-9a-fA-F]{40}',
    b'th_port': rb'(?:0x[0-9a-fA-F]{1,8})?',
}


def _validate_auxiliary(raw):
    """Validate, never expose/import, the reviewed Apple tail after env boundary.

    NUL runs are alignment or erased startup values. Every non-NUL segment must
    be a unique reviewed key with its documented shape. Future keys fail closed.
    """
    if not raw or raw[0] != 0 or raw[-1] != 0:
        raise ValueError()
    seen = set()
    for entry in raw.split(b'\0'):
        if not entry:
            continue
        key, sep, value = entry.partition(b'=')
        pattern = _AUXILIARY.get(key)
        if not sep or pattern is None or key in seen or re.fullmatch(pattern, value) is None:
            raise ValueError()
        seen.add(key)


def parse_arguments(raw):
    try:
        if not isinstance(raw, bytes) or not 5 <= len(raw) <= MAX_BYTES:
            raise ValueError()
        argc = struct.unpack_from('=i', raw)[0]
        if not 1 <= argc <= 4096:
            raise ValueError()
        pos = 4
        def string():
            nonlocal pos
            end = raw.index(b'\0', pos)
            value = raw[pos:end].decode('utf-8', errors='strict')
            pos = end + 1
            return value
        executable = string()
        # exec_save_path preserves execve's path, including reviewed ./ launches.
        # This is metadata, never an executable to run. The service verifier checks
        # cwd independently; unresolved bare paths and traversal stay unsupported.
        if not executable.startswith('/') and not (executable.startswith('./') and all(part not in ('', '.', '..') for part in executable.split('/')[1:])):
            raise ValueError()
        while pos < len(raw) and raw[pos] == 0:
            pos += 1
        argv = tuple(string() for _ in range(argc))
        if not argv[0]:
            raise ValueError()
        env = {}
        while pos < len(raw):
            if raw[pos] == 0:
                _validate_auxiliary(raw[pos:])
                break
            entry = string()
            key, sep, value = entry.partition('=')
            if not sep or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) or key in env or key.encode('utf-8') in _AUXILIARY:
                raise ValueError()
            env[key] = value
        else:
            # No extra NUL after the last entry: boundary/truncation is ambiguous.
            raise ValueError()
        return executable, argv, env
    except Exception:
        raise Stop('Native process snapshot is malformed or unsupported.') from None


class BSDInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
        'rgid', 'svuid', 'svgid', 'rfu')]+[
        ('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]+[
        (name, ctypes.c_uint32) for name in ('nfiles', 'pgid', 'pjobc', 'e_tdev', 'e_tpgid')]+[
        ('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


class MacOS:
    def __init__(self):
        if sys.platform != 'darwin' or ctypes.sizeof(BSDInfo) != 136:
            raise Stop('Reviewed macOS process interfaces unavailable.')
        try:
            self.libproc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
            self.libc = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
            self.libproc.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
            self.libproc.proc_pidinfo.restype = ctypes.c_int
            self.libc.sysctl.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t), ctypes.c_void_p, ctypes.c_size_t]
            self.libc.sysctl.restype = ctypes.c_int
        except Exception:
            raise Stop('Native process verification unavailable.') from None

    def identity(self, pid):
        if type(pid) is not int or not 0 < pid < 2**31:
            raise Stop('Invalid process identity.')
        info = BSDInfo()
        count = self.libproc.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))  # PROC_PIDTBSDINFO
        if count != ctypes.sizeof(info) or info.pid != pid or info.uid != os.getuid() or not info.start_sec or info.start_usec >= 1000000:
            raise Stop('Process identity unavailable or not owned by operator.')
        return (pid, info.start_sec, info.start_usec, info.uid)

    def arguments(self, pid):
        mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2
        size = ctypes.c_size_t()
        if self.libc.sysctl(mib, 3, None, ctypes.byref(size), None, 0) or not 5 <= size.value <= MAX_BYTES:
            raise Stop('Native process environment unavailable.')
        buf = ctypes.create_string_buffer(size.value)
        if self.libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0) or size.value > len(buf):
            raise Stop('Native process environment unavailable.')
        return bytes(buf.raw[:size.value])


@dataclass(repr=False)
class Snapshot:
    identity: tuple
    executable: str = field(repr=False)
    argv: tuple = field(repr=False)
    environment: dict = field(repr=False)


def snapshot(pid, native=None):
    native = native if native is not None else MacOS()
    before = native.identity(pid)
    executable, argv, env = parse_arguments(native.arguments(pid))
    if native.identity(pid) != before:
        raise Stop('Process identity changed during snapshot.')
    return Snapshot(before, executable, argv, env)


def assert_same(saved, native):
    if native.identity(saved.identity[0]) != saved.identity:
        raise Stop('Process identity changed before inference.')
