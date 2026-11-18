#!/bin/bash
set +x
set -euo pipefail
if [[ $# != 0 || ! -t 0 || ! -t 1 ]]; then
  printf '%s\n' 'Use a private interactive terminal with no arguments, pipes or output redirection.' >&2
  exit 1
fi
recovery_backend=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
recovery_jar="$recovery_backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar"
if [[ ! -f "$recovery_jar" ]] || ! /usr/bin/unzip -Z1 "$recovery_jar" | /usr/bin/grep -Fx 'BOOT-INF/classes/com/paymesh/backend/security/accounts/DisposableMerchantPasswordRecovery.class' >/dev/null; then
  printf '%s\n' 'Build the reviewed recovery JAR with mvn package -DskipTests before running this utility.' >&2
  exit 1
fi
recovery_java_home=$(/usr/libexec/java_home -v 21)
cd -- "$recovery_backend"
exec /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin \
  PAYMESH_OFFLINE_MERCHANT_RECOVERY=RESET_DISPOSABLE_PENDING_MERCHANT \
  PAYMESH_DEMO_DB_URL=jdbc:postgresql://127.0.0.1:5432/paymesh_demo \
  PAYMESH_DB_USER=paymesh_demo_user \
  "$recovery_java_home/bin/java" \
  -Dloader.main=com.paymesh.backend.security.accounts.DisposableMerchantPasswordRecovery \
  -cp "$recovery_jar" org.springframework.boot.loader.launch.PropertiesLauncher
