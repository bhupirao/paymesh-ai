#!/bin/bash
# Operator approval required. Python only; no inference or database activity.
set +x
set -euo pipefail
umask 077
[[ $# == 0 && -t 0 && -t 1 && -r /dev/tty ]] || {
  echo 'Interactive terminal, no arguments required.' >&2
  exit 1
}
exec python3 -B "$(cd -- "$(dirname -- "$0")" && pwd -P)/phase697a_python_reload.py"
