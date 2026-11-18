#!/bin/bash
# Requires deploy-phase673-admin-api.sh first. Operator-run only; authenticated Admin API.
set +x
set -euo pipefail
umask 077
[[ $# == 0 && -t 0 && -t 1 && -r /dev/tty ]] || { echo 'Run without arguments in an interactive Mac Terminal.' >&2; exit 1; }
private="$HOME/.config/paymesh-demo"
[[ ! -L "$private" && $(stat -f '%u:%Lp' "$private") == "$(id -u):700" ]] || exit 1
for file in demo.env secrets.env; do [[ ! -L "$private/$file" && $(stat -f '%u:%Lp' "$private/$file") == "$(id -u):600" ]] || exit 1; done
set -a
source "$private/demo.env" >/dev/null 2>&1
source "$private/secrets.env" >/dev/null 2>&1
set +a
set +x
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd -P)/phase673_otp_ops.py" activate
