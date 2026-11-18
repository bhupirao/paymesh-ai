#!/bin/bash
# Operator-only, interactive Mac Terminal activation. Never run this through Codex stdin/TTY.
set +x
set -euo pipefail
umask 077
set -o noclobber
[[ $# == 0 && -t 0 && -t 1 && -r /dev/tty ]] || { echo 'Run this file without arguments in a real interactive Mac Terminal.' >&2; exit 1; }
repo=$(cd -- "$(dirname -- "$0")/../.." && pwd -P)
private="$HOME/.config/paymesh-demo"
report="$repo/frontend/PHASE-6.7.3-SESSIONS-PASSWORD-RECOVERY-REPORT.md"
pgbin=/Library/PostgreSQL/16/bin
stage=preflight
java_stopped=false; java_started=false; frontend_stopped=false; frontend_started=false; migration_verified=false
java_new=none; frontend_new=none; backup_verified=false; backup=none; backup_sha=none; run=none
fail() { printf 'STOP: %s\n' "$1" >&2; exit 1; }
[[ $repo == "$HOME/Developer/paymesh-ai" ]] || fail 'Unexpected project checkout'
finish() {
  local result=$?
  trap - EXIT
  unset activation_db_password PGPASSWORD PAYMESH_DB_PASSWORD
  if [[ $result != 0 ]]; then
    printf 'Activation stopped at stage %s. No automatic retry, restore, downgrade or repair. Private evidence directory: %s\n' "$stage" "$run" >&2
    printf '\n## Operator activation stopped\n\nStage: %s. Backup verified: %s. Java old stopped/new started: %s/%s (new PID %s). Frontend old stopped/new started: %s/%s (new PID %s). V10 verified: %s. No automatic rollback/restart was attempted. Private evidence: `%s`. Inspect it privately before another attempt; database state may have changed if startup began.\n' "$stage" "$backup_verified" "$java_stopped" "$java_started" "$java_new" "$frontend_stopped" "$frontend_started" "$frontend_new" "$migration_verified" "$run" >> "$report"
  fi
  exit "$result"
}
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
owned_mode() { [[ ! -L "$1" && $(/usr/bin/stat -f '%u' "$1") == "$(id -u)" && $(/usr/bin/stat -f '%Lp' "$1") == "$2" ]] || fail 'Protected file/directory ownership or mode mismatch'; }
owned_mode "$private" 700
for file in demo.env secrets.env jwt-private.pem; do owned_mode "$private/$file" 600; done
[[ -r "$private/jwt-public.pem" && ! -L "$private/jwt-public.pem" ]] || fail 'Missing public JWT key'
for tool in psql pg_dump pg_restore; do [[ -x "$pgbin/$tool" ]] || fail 'PostgreSQL 16 tools missing'; "$pgbin/$tool" --version | /usr/bin/grep -Eq ' 16\.' || fail 'PostgreSQL tool version mismatch'; done
python_bin=$(command -v python3); mvn_bin=$(command -v mvn); java_home=$(/usr/libexec/java_home -v 21)
[[ -x "$python_bin" && -x "$mvn_bin" && -x "$java_home/bin/java" ]] || fail 'Required local build/runtime tools unavailable'
# Never dump process environments or full command lines.
listener() { local p; p=$(/usr/sbin/lsof -t -nP -iTCP:"$1" -sTCP:LISTEN | /usr/bin/sort -u); [[ $p =~ ^[0-9]+$ ]] || fail 'Expected exactly one listener'; printf '%s' "$p"; }
identity() {
  local pid=$1 port=$2 cwd=$3 kind=$4 comm names args
  [[ $(listener "$port") == "$pid" ]] || fail 'Listener identity changed'
  comm=$(/bin/ps -p "$pid" -o comm=)
  case "$kind:$comm" in java:java|java:*/java|python:*/Python|python:Python|python:*/python3|python:*/python3.*|llm:*/llama-server|llm:llama-server) ;; *) fail 'Unexpected process executable';; esac
  /usr/sbin/lsof -a -p "$pid" -d cwd -Fn | /usr/bin/grep -Fx "n$cwd" >/dev/null || fail 'Unexpected process working directory'
  names=$(/usr/sbin/lsof -nP -a -p "$pid" -iTCP:"$port" -sTCP:LISTEN -Fn | /usr/bin/grep '^n')
  [[ $names == "n127.0.0.1:$port" ]] || fail 'Listener is not bound exclusively to the expected literal loopback address'
  args=$(/bin/ps -p "$pid" -o args=)
  case "$kind" in
    java) [[ $args == *' -jar target/paymesh-backend-0.0.1-SNAPSHOT.jar'* || $args == *" -jar $repo/backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar"* ]] || fail 'Unexpected Java main artifact';;
    python) if [[ $port == 5500 ]]; then [[ $args == *'frontend/dev_server.py'* ]] || fail 'Unexpected frontend command'; fi;;
  esac
}
java_old=$(listener 18080); frontend_old=$(listener 5500); ai_pid=$(listener 8000); llm_pid=$(listener 8082)
identity "$java_old" 18080 "$repo/backend" java
identity "$frontend_old" 5500 "$repo" python
identity "$ai_pid" 8000 "$repo/ai-service" python
identity "$llm_pid" 8082 "$HOME/Developer/paymesh-tools/llama.cpp" llm
java_stamp=$(/bin/ps -p "$java_old" -o lstart=); frontend_stamp=$(/bin/ps -p "$frontend_old" -o lstart=)
ai_stamp=$(/bin/ps -p "$ai_pid" -o lstart=); llm_stamp=$(/bin/ps -p "$llm_pid" -o lstart=)
untouched() {
  identity "$ai_pid" 8000 "$repo/ai-service" python
  identity "$llm_pid" 8082 "$HOME/Developer/paymesh-tools/llama.cpp" llm
  [[ $(/bin/ps -p "$ai_pid" -o lstart=) == "$ai_stamp" && $(/bin/ps -p "$llm_pid" -o lstart=) == "$llm_stamp" ]] || fail 'AI/LLM identity changed externally'
}
# Source only operator-owned protected files; never display their contents or errors.
set -a
source "$private/demo.env" >/dev/null 2>&1 || fail 'Cannot load private demo configuration'
source "$private/secrets.env" >/dev/null 2>&1 || fail 'Cannot load private secrets'
set +a
set +x
set -euo pipefail
for name in JAVA_TOOL_OPTIONS JDK_JAVA_OPTIONS _JAVA_OPTIONS BASH_ENV SPRING_APPLICATION_JSON SPRING_CONFIG_LOCATION SPRING_CONFIG_ADDITIONAL_LOCATION SPRING_CONFIG_IMPORT; do [[ -z ${!name:-} ]] || fail 'Unreviewed JVM/Spring override'; done
for name in $(compgen -e); do
  case "$name" in SPRING_DATASOURCE_*|SPRING_FLYWAY_*|SPRING_JPA_*|SPRING_MAIN_*) [[ -z ${!name:-} ]] || fail 'Unreviewed datasource/migration/startup override';; esac
 done
[[ -z ${SPRING_PROFILES_ACTIVE:-} || $SPRING_PROFILES_ACTIVE == demo ]] || fail 'Conflicting profile'
target=jdbc:postgresql://127.0.0.1:5432/paymesh_demo
[[ -z ${PAYMESH_DB_URL:-} || $PAYMESH_DB_URL == "$target" ]] || fail 'Conflicting protected database URL'
[[ -z ${PAYMESH_DEMO_DB_URL:-} || $PAYMESH_DEMO_DB_URL == "$target" ]] || fail 'Conflicting protected demo URL'
[[ -z ${PAYMESH_DB_USER:-} || $PAYMESH_DB_USER == paymesh_demo_user ]] || fail 'Conflicting protected database user'
for name in PAYMESH_JWT_ISSUER PAYMESH_JWT_AUDIENCE PAYMESH_RAZORPAY_WEBHOOK_SECRET PAYMESH_STRIPE_WEBHOOK_SECRET PAYMESH_SETTLEMENT_ADMIN_TOKEN; do [[ -n ${!name:-} ]] || fail 'Required existing private configuration is missing'; done
[[ -z ${PAYMESH_JWT_PRIVATE_KEY_FILE:-} || $PAYMESH_JWT_PRIVATE_KEY_FILE == "$private/jwt-private.pem" ]] || fail 'Unexpected private JWT key location'
[[ -z ${PAYMESH_JWT_PUBLIC_KEY_FILE:-} || $PAYMESH_JWT_PUBLIC_KEY_FILE == "$private/jwt-public.pem" ]] || fail 'Unexpected public JWT key location'
export PAYMESH_DB_URL="$target" PAYMESH_DEMO_DB_URL="$target" PAYMESH_DB_USER=paymesh_demo_user
export PAYMESH_JWT_PRIVATE_KEY_FILE="$private/jwt-private.pem" PAYMESH_JWT_PUBLIC_KEY_FILE="$private/jwt-public.pem"
# Compare only reviewed non-secret settings in the running command; never print argv.
"$python_bin" -c 'import os,shlex,subprocess,sys
args=shlex.split(subprocess.check_output(["/bin/ps","-p",sys.argv[1],"-o","args="],text=True)); flags={}; index=0
while index<len(args):
 item=args[index]
 if item.startswith("--"):
  key,sep,value=item[2:].partition("=")
  if not sep and index+1<len(args) and not args[index+1].startswith("--"): index+=1;value=args[index]
  flags[key]=value
 index+=1
expected={"spring.config.location":"classpath:/application.properties","spring.profiles.active":"demo","spring.datasource.url":"jdbc:postgresql://127.0.0.1:5432/paymesh_demo","spring.datasource.username":"paymesh_demo_user","spring.flyway.enabled":"true","spring.jpa.hibernate.ddl-auto":"validate","server.address":"127.0.0.1","server.port":"18080","paymesh.settlement.scheduling-enabled":"false","paymesh.ai.enabled":"true","paymesh.ai.base-url":"http://127.0.0.1:8000","paymesh.ai.connect-timeout-ms":"2000","paymesh.ai.response-timeout-ms":"45000","paymesh.ai.max-response-bytes":"262144","paymesh.jwt.issuer":os.environ["PAYMESH_JWT_ISSUER"],"paymesh.jwt.audience":os.environ["PAYMESH_JWT_AUDIENCE"],"paymesh.demo.gateway-timeout.enabled":os.getenv("PAYMESH_DEMO_GATEWAY_TIMEOUT_ENABLED","false")}
if any(key in flags and flags[key]!=value for key,value in expected.items()) or flags.get("spring.config.additional-location") or "spring.datasource.password" in flags:sys.exit("STOP: running launch settings require private review before replacement")
' "$java_old"
run=$(/usr/bin/mktemp -d "$private/activation-673-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
owned_mode "$run" 700
/usr/bin/git -C "$repo" diff --cached --binary > "$run/staged-before.bin"
index_before=$(/usr/bin/shasum -a 256 "$repo/.git/index" | /usr/bin/awk '{print $1}')
staged_before=$(/usr/bin/shasum -a 256 "$run/staged-before.bin" | /usr/bin/awk '{print $1}')
printf 'Verified listener identities. Activation will target paymesh_demo only; stop browser activity until verification completes.\n'
stage=credential
unset activation_db_password PAYMESH_DB_PASSWORD PGPASSWORD
IFS= read -r -s -p 'Existing paymesh_demo_user database password (hidden): ' activation_db_password </dev/tty
printf '\n' >/dev/tty
[[ -n "$activation_db_password" ]] || fail 'Empty database credential'
ro() { PGPASSWORD="$activation_db_password" PGOPTIONS='-c default_transaction_read_only=on' "$pgbin/psql" -X -w -h 127.0.0.1 -p 5432 -U paymesh_demo_user -d paymesh_demo -Atq -v ON_ERROR_STOP=1 -c "$1" 2>>"$run/sql-errors.log"; }
counts() { ro 'SELECT (SELECT count(*) FROM public.app_users),(SELECT count(*) FROM public.merchants),(SELECT count(*) FROM public.merchant_memberships),(SELECT count(*) FROM public.merchant_registrations),(SELECT count(*) FROM public.payments),(SELECT count(*) FROM public.refunds)'; }
admin_ok() { [[ $(ro "SELECT count(*) FROM public.app_users u WHERE login_normalized='demo-admin' AND enabled AND account_status='ACTIVE' AND authorization_version=1 AND EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=u.user_id AND role_name='ADMIN') AND NOT EXISTS(SELECT 1 FROM public.user_roles r WHERE r.user_id=u.user_id AND role_name<>'ADMIN')") == 1 ]] || fail 'Existing administrator state mismatch'; }
history() { ro "SELECT string_agg(version,',' ORDER BY installed_rank) FILTER(WHERE version IS NOT NULL)||'|'||CASE WHEN bool_and(success) THEN 'ok' ELSE 'failed' END FROM public.flyway_schema_history"; }
stage=database-preflight
[[ $(ro 'SELECT current_database(),current_user,host(inet_server_addr()),inet_server_port()') == 'paymesh_demo|paymesh_demo_user|127.0.0.1|5432' ]] || fail 'Actual database identity mismatch'
server_version=$(ro 'SHOW server_version_num'); [[ $server_version =~ ^[0-9]+$ && $server_version -lt 170000 ]] || fail 'Server is not compatible with PostgreSQL 16 dump tools'
[[ $(history) == '1,2,3,4,5,6,7,8,9|ok' ]] || fail 'Expected successful V1-V9 with no V10; refuse partial/repeated migration'
[[ $(ro "SELECT count(*) FROM unnest(ARRAY['auth_sessions','auth_refresh_tokens','demo_recovery_eligibility','password_recovery_challenges','password_reset_authorizations']) AS wanted(name) WHERE to_regclass('public.'||name) IS NULL") == 5 ]] || fail 'Unexpected partial V10 schema'
before=$(counts); [[ $before == '4|3|3|1|6|4' ]] || fail 'Existing entity counts differ from approved baseline'
admin_ok
printf 'Before users|merchants|memberships|registrations|payments|refunds: %s\n' "$before" | tee "$run/counts-before.txt"
database_bytes=$(ro 'SELECT pg_database_size(current_database())')
free_kb=$(/bin/df -Pk "$private" | /usr/bin/awk 'NR==2 {print $4}')
[[ $database_bytes =~ ^[0-9]+$ && $free_kb =~ ^[0-9]+$ ]] || fail 'Cannot verify available storage'
(( free_kb*1024 > database_bytes*3+1073741824 )) || fail 'Insufficient free space for backup/build/startup reserve'
stage=backup
if [[ ! -e "$private/backups" ]]; then /bin/mkdir -m 700 "$private/backups"; fi
owned_mode "$private/backups" 700
backup=$(/usr/bin/mktemp "$private/backups/paymesh_demo-pre-v10-$(date -u +%Y%m%dT%H%M%SZ).XXXXXX")
PGPASSWORD="$activation_db_password" PGOPTIONS='-c default_transaction_read_only=on' "$pgbin/pg_dump" -w -h 127.0.0.1 -p 5432 -U paymesh_demo_user -d paymesh_demo -Fc -f "$backup" 2>"$run/dump-errors.log"
[[ -s "$backup" ]] || fail 'Empty backup'
owned_mode "$backup" 600
"$pgbin/pg_restore" --list "$backup" > "$run/archive-list.txt" 2>"$run/archive-list-errors.log"
"$pgbin/pg_restore" --file=/dev/null "$backup" 2>"$run/archive-extraction-errors.log"
/usr/bin/shasum -a 256 "$backup" > "$backup.sha256"
owned_mode "$backup.sha256" 600
backup_sha=$(/usr/bin/awk '{print $1}' "$backup.sha256"); backup_verified=true
printf 'Protected custom backup verified (list and extraction, NOT a test restore). SHA-256: %s\n' "$backup_sha"
[[ $(counts) == "$before" && $(history) == '1,2,3,4,5,6,7,8,9|ok' ]] || fail 'Database changed during backup'
admin_ok
stage=build
(cd "$repo/backend" && "$mvn_bin" package -DskipTests > "$run/maven-package.log" 2>&1)
jar="$repo/backend/target/paymesh-backend-0.0.1-SNAPSHOT.jar"
"$python_bin" -c 'import pathlib,sys,zipfile; p=pathlib.Path(sys.argv[1]); migration=pathlib.Path(sys.argv[2]); z=zipfile.ZipFile(p); names=z.namelist(); required=["BOOT-INF/classes/db/migration/"+migration.name,"BOOT-INF/classes/com/paymesh/backend/security/auth/SessionController.class","BOOT-INF/classes/com/paymesh/backend/security/auth/PasswordRecoveryController.class"]; assert all(n in names for n in required),"Missing activation artifact"; assert z.read(required[0])==migration.read_bytes(),"Packaged migration differs from reviewed source"' "$jar" "$repo/backend/src/main/resources/db/migration/V10__persistent_sessions_and_local_demo_recovery.sql" > "$run/artifact-check.txt" 2>&1
stage=private-session-configuration
session_config="$run/sessions.properties"
printf '%s\n' 'paymesh.sessions.origin=http://127.0.0.1:5500' 'paymesh.sessions.local-http=true' 'paymesh.demo.password-recovery.enabled=false' 'server.address=127.0.0.1' 'server.port=18080' > "$session_config"
owned_mode "$session_config" 600
untouched
identity "$java_old" 18080 "$repo/backend" java
identity "$frontend_old" 5500 "$repo" python
[[ $(/bin/ps -p "$java_old" -o lstart=) == "$java_stamp" && $(/bin/ps -p "$frontend_old" -o lstart=) == "$frontend_stamp" ]] || fail 'Process identity changed since preflight'
[[ $(counts) == "$before" ]] || fail 'Counts changed before activation'
admin_ok
stop_exact() {
  case "$2" in
    18080) identity "$1" 18080 "$repo/backend" java; [[ $(/bin/ps -p "$1" -o lstart=) == "$java_stamp" ]] || fail 'Java changed immediately before stop';;
    5500) identity "$1" 5500 "$repo" python; [[ $(/bin/ps -p "$1" -o lstart=) == "$frontend_stamp" ]] || fail 'Frontend changed immediately before stop';;
    *) fail 'Unexpected stop port';;
  esac
  local all_listeners
  all_listeners=$(/usr/sbin/lsof -nP -a -p "$1" -iTCP -sTCP:LISTEN -Fn | /usr/bin/grep '^n')
  [[ $all_listeners == "n127.0.0.1:$2" ]] || fail 'Unexpected additional listener on process selected for stop'
  /bin/kill -TERM "$1"
  for attempt in {1..30}; do if ! /bin/kill -0 "$1" 2>/dev/null; then break; fi; /bin/sleep 1; done
  ! /bin/kill -0 "$1" 2>/dev/null || fail 'Old process did not exit; refusing force-kill or duplicate startup'
  if [[ $2 == 18080 ]]; then java_stopped=true; else frontend_stopped=true; fi
  if /usr/sbin/lsof -t -nP -iTCP:"$2" -sTCP:LISTEN >/dev/null; then fail 'Port still occupied'; fi
}
stage=java-restart
stop_exact "$java_old" 18080; java_stopped=true
cd "$repo/backend"
# Inline assignment puts the password in the child environment, never argv or a file.
PAYMESH_DB_PASSWORD="$activation_db_password" /usr/bin/nohup "$java_home/bin/java" -jar "$jar" \
 --spring.config.location=classpath:/application.properties "--spring.config.additional-location=file:$session_config" \
 --spring.profiles.active=demo --spring.profiles.include= \
 --spring.datasource.url=jdbc:postgresql://127.0.0.1:5432/paymesh_demo --spring.datasource.username=paymesh_demo_user \
 --spring.flyway.enabled=true --spring.flyway.validate-on-migrate=true --spring.flyway.default-schema=public --spring.flyway.schemas=public \
 --spring.jpa.hibernate.ddl-auto=validate --spring.jpa.properties.hibernate.default_schema=public --spring.sql.init.mode=never \
 --server.address=127.0.0.1 --server.port=18080 --server.forward-headers-strategy=none \
 --paymesh.sessions.origin=http://127.0.0.1:5500 --paymesh.sessions.local-http=true --paymesh.demo.password-recovery.enabled=false \
 --paymesh.settlement.scheduling-enabled=false --paymesh.ai.enabled=true --paymesh.ai.base-url=http://127.0.0.1:8000 \
 --paymesh.ai.connect-timeout-ms=2000 --paymesh.ai.response-timeout-ms=45000 --paymesh.ai.max-response-bytes=262144 \
 > "$run/java.log" 2>&1 < /dev/null &
java_new=$!; java_started=true
printf '%s\n' "$java_new" > "$run/java.pid"
ready=false
for attempt in {1..120}; do
  /bin/kill -0 "$java_new" 2>/dev/null || fail 'Java exited; inspect private startup log without publishing secrets'
  if /usr/bin/curl --noproxy '*' --silent --fail --connect-timeout 1 --max-time 2 http://127.0.0.1:18080/actuator/health/readiness -o "$run/readiness.json"; then
    if "$python_bin" -c 'import json,sys;assert json.load(open(sys.argv[1])).get("status")=="UP"' "$run/readiness.json" 2>/dev/null; then ready=true; break; fi
  fi
  /bin/sleep 1
done
[[ $ready == true ]] || fail 'Java readiness timeout; no automatic retry/restore/downgrade'
identity "$java_new" 18080 "$repo/backend" java
stage=migration-verification
[[ $(history) == '1,2,3,4,5,6,7,8,9,10|ok' ]] || fail 'V10 was not applied successfully'
[[ $(ro "SELECT count(*) FROM public.flyway_schema_history WHERE version='10' AND success AND script='V10__persistent_sessions_and_local_demo_recovery.sql'") == 1 ]] || fail 'Unexpected V10 migration identity'
[[ $(ro "SELECT count(*) FROM unnest(ARRAY['auth_sessions','auth_refresh_tokens','demo_recovery_eligibility','password_recovery_challenges','password_reset_authorizations']) AS wanted(name) WHERE to_regclass('public.'||name) IS NOT NULL") == 5 ]] || fail 'Required authentication tables missing'
[[ $(ro "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND NOT t.tgisinternal AND t.tgenabled IN ('O','A') AND (c.relname,t.tgname) IN (('app_users','auth_account_security_change'),('user_roles','auth_role_security_change'))") == 2 ]] || fail 'Required security triggers missing or disabled'
[[ $(ro 'SELECT count(*) FROM public.demo_recovery_eligibility') == 0 ]] || fail 'Recovery eligibility is not empty'
after=$(counts); [[ $after == "$before" ]] || fail 'Entity counts changed after migration'
admin_ok; migration_verified=true
/usr/bin/curl --noproxy '*' --silent --show-error --fail --max-time 5 http://127.0.0.1:18080/api/v1/payments/health -o "$run/java-payment-health.json"
/usr/bin/curl --noproxy '*' --silent --show-error --fail --max-time 5 http://127.0.0.1:18080/api/v1/auth/password/capabilities -o "$run/java-capabilities.json"
"$python_bin" -c 'import json,sys;assert json.load(open(sys.argv[1])).get("localDemoEnabled") is False' "$run/java-capabilities.json"
untouched
stage=frontend-restart
identity "$frontend_old" 5500 "$repo" python
[[ $(/bin/ps -p "$frontend_old" -o lstart=) == "$frontend_stamp" ]] || fail 'Frontend identity changed'
stop_exact "$frontend_old" 5500; frontend_stopped=true
cd "$repo"
/usr/bin/nohup /usr/bin/env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/sbin:/sbin "$python_bin" frontend/dev_server.py > "$run/frontend.log" 2>&1 < /dev/null &
frontend_new=$!; frontend_started=true
printf '%s\n' "$frontend_new" > "$run/frontend.pid"
front_ready=false
for attempt in {1..30}; do
 /bin/kill -0 "$frontend_new" 2>/dev/null || fail 'Frontend exited; inspect private log'
 if /usr/bin/curl --noproxy '*' --silent --fail --max-time 2 http://127.0.0.1:5500/ -o /dev/null; then front_ready=true;break;fi
 /bin/sleep 1
done
[[ $front_ready == true ]] || fail 'Frontend readiness timeout'
identity "$frontend_new" 5500 "$repo" python
stage=read-only-http-verification
for path in / /merchant/signup /merchant/login /merchant/dashboard /merchant/forgot-password /admin/login /admin/dashboard /admin/forgot-password /assets/js/session-recovery-tests.html; do
 /usr/bin/curl --noproxy '*' --silent --show-error --fail --max-time 5 "http://127.0.0.1:5500$path" -o /dev/null
done
/usr/bin/curl --noproxy '*' --silent --show-error --fail --max-time 5 http://127.0.0.1:5500/api/v1/payments/health -o "$run/proxy-payment-health.json"
/usr/bin/curl --noproxy '*' --silent --show-error --fail --max-time 5 http://127.0.0.1:5500/api/v1/auth/password/capabilities -o "$run/proxy-capabilities.json"
"$python_bin" -c 'import json,sys;assert json.load(open(sys.argv[1])).get("localDemoEnabled") is False' "$run/proxy-capabilities.json"
# Empty-cookie probes only: no login, no password/recovery POST, no session credential or financial request.
code=$(/usr/bin/curl --noproxy '*' --silent --max-time 5 -o "$run/origin-denial.json" -w '%{http_code}' -X POST http://127.0.0.1:5500/api/v1/auth/refresh)
[[ $code == 403 ]] || fail 'Proxy Origin/CSRF denial mismatch'
code=$(/usr/bin/curl --noproxy '*' --silent --max-time 5 -D "$run/missing-cookie.headers" -o "$run/missing-cookie.json" -w '%{http_code}' -X POST -H 'Origin: http://127.0.0.1:5500' -H 'X-PayMesh-CSRF: 1' http://127.0.0.1:5500/api/v1/auth/refresh)
[[ $code == 401 ]] || fail 'Java session route/Origin/cookie behavior mismatch'
"$python_bin" -c 'import pathlib,sys;from http.cookies import SimpleCookie
headers=pathlib.Path(sys.argv[1]).read_text().splitlines(); values=[line.split(":",1)[1].strip() for line in headers if line.lower().startswith("set-cookie:")]; assert len(values)==1; c=SimpleCookie();c.load(values[0]); item=c.get("pm_refresh");assert item is not None and item.value=="" and item["path"]=="/api/v1/auth" and item["httponly"] and item["samesite"]=="Strict" and not item["secure"] and not item["domain"],"Unexpected local cookie attributes"' "$run/missing-cookie.headers"
"$python_bin" -c 'import importlib.util,sys;spec=importlib.util.spec_from_file_location("phase673_proxy",sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert all(m.allowed("POST","/api/v1/auth/"+p) for p in ["login","refresh","logout","logout-all","password/forgot","password/verify-otp","password/reset"]);assert not m.allowed("POST","/api/v1/auth/password/approve");assert not m.allowed("GET","/actuator/env")' "$repo/frontend/dev_server.py"
untouched
final_counts=$(counts); [[ $final_counts == "$before" ]] || fail 'Final entity counts differ'
admin_ok
[[ $(ro 'SELECT count(*) FROM public.demo_recovery_eligibility') == 0 ]] || fail 'Eligibility changed externally'
/usr/bin/git -C "$repo" diff --check
/usr/bin/git -C "$repo" diff --cached --binary > "$run/staged-after.bin"
index_after=$(/usr/bin/shasum -a 256 "$repo/.git/index" | /usr/bin/awk '{print $1}')
staged_after=$(/usr/bin/shasum -a 256 "$run/staged-after.bin" | /usr/bin/awk '{print $1}')
staging_note='Initial/final staged snapshots and index match.'
if [[ $index_before != "$index_after" || $staged_before != "$staged_after" ]]; then staging_note='Concurrent external staging observed and left untouched; no index mutations issued by this script.';fi
printf '\n## Successful operator-run sessions-only activation\n\nBackup: `%s`, custom format, mode600, nonempty; PostgreSQL16 pg_restore list and full archive extraction to /dev/null passed. SHA-256 `%s`. No actual test restore performed.\n\nMaven package succeeded; packaged V10 matched source and both controllers were present. Protected non-secret session configuration: `%s`. OTP explicitly disabled; no recovery key or eligibility was created.\n\nV1-V10 history successful; five auth/recovery tables and both enabled security triggers verified. Before/after counts users|merchants|memberships|registrations|payments|refunds: `%s` / `%s`. Existing admin remains enabled ACTIVE ADMIN-only at authorization_version1.\n\nJava old/new PID: %s/%s. Frontend old/new PID: %s/%s. Python PID %s and llama.cpp PID %s plus start identities remain unchanged. Readiness UP, direct/proxy health, all eight SPA routes, test page and disabled recovery capabilities verified. Empty-cookie refresh returned401; missing Origin/CSRF returned403. No login, recovery POST, password reset, financial mutation or original paymesh_db/8080 operation was performed.\n\nGit index initial/final: `%s` / `%s`; staged diff initial/final: `%s` / `%s`. %s git diff --check passed. Private evidence: `%s`. Native browser/cookie/Web-Locks verification remains pending. OTP activation and Phase6.7.4 are not authorized by this run.\n' "$backup" "$backup_sha" "$session_config" "$before" "$final_counts" "$java_old" "$java_new" "$frontend_old" "$frontend_new" "$ai_pid" "$llm_pid" "$index_before" "$index_after" "$staged_before" "$staged_after" "$staging_note" "$run" >> "$report"
stage=complete
printf 'Activation verified. Java PID %s; frontend PID %s. Counts %s. OTP DISABLED.\nPrivate evidence: %s\nBackup: %s\n' "$java_new" "$frontend_new" "$final_counts" "$run" "$backup"
