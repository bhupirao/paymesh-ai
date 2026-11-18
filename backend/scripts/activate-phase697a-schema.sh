#!/bin/bash
# Inert until explicitly invoked/approved by the operator. Migration only; chat stays disabled.
set +x
set -euo pipefail
umask 077
[[ $# == 0 && -t 0 && -t 1 && -r /dev/tty ]] || { echo 'Use an interactive Mac Terminal without arguments.' >&2; exit 1; }
private="$HOME/.config/paymesh-demo"
[[ ! -L "$private" && $(stat -f '%u:%Lp' "$private") == "$(id -u):700" ]] || exit 1
for file in demo.env secrets.env; do
  [[ ! -L "$private/$file" && $(stat -f '%u:%Lp' "$private/$file") == "$(id -u):600" ]] || exit 1
done
set -a
source "$private/demo.env" >/dev/null 2>&1
source "$private/secrets.env" >/dev/null 2>&1
set +a
set +x
exec python3 "$(cd -- "$(dirname -- "$0")" && pwd -P)/phase697a_schema.py"
