#!/bin/bash
# Prepared operator-only helper. No invocation during Phase697A preparation.
set +x
set -euo pipefail
umask 077
[[ $# == 1 && -t 0 && -t 1 && -r /dev/tty ]] || { echo 'Interactive terminal and one documented mode required.' >&2; exit 1; }
case "$1" in health|internal|internal-diagnostic|merchant|admin|stage-enable|stage-disable) ;; *) echo 'Unsupported mode.' >&2; exit 1;; esac
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd -P)/phase697a_ai_verify.py" "$1"
