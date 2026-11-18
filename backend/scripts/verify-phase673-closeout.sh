#!/bin/bash
# Read-only audit; never calls activation, password recovery or service-control operations.
set +x
set -euo pipefail
umask 077
[[ $# == 1 && ( "$1" == pre || "$1" == post || "$1" == final ) && -t 0 && -t 1 && -r /dev/tty ]] || { echo 'Usage in a private Mac Terminal: /bin/bash backend/scripts/verify-phase673-closeout.sh pre|post|final' >&2; exit 1; }
private="$HOME/.config/paymesh-demo"
[[ ! -L "$private" && $(stat -f '%u:%Lp' "$private") == "$(id -u):700" ]] || exit 1
for file in demo.env secrets.env; do [[ ! -L "$private/$file" && $(stat -f '%u:%Lp' "$private/$file") == "$(id -u):600" ]] || exit 1; done
set -a
source "$private/demo.env" >/dev/null 2>&1
source "$private/secrets.env" >/dev/null 2>&1
set +a
set +x
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd -P)/phase673_closeout.py" "$1"
