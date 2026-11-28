#!/bin/sh
set -eu
process_uid="$(id -u)"
process_gid="$(id -g)"
data_owner="$(stat -c '%u:%g' "$PGDATA")"
data_mode="$(stat -c '%a' "$PGDATA")"
printf 'PATAMAPS_DATA_OWNER process=%s:%s data=%s mode=%s\n' "$process_uid" "$process_gid" "$data_owner" "$data_mode"
[ "$process_uid:$process_gid" = '501:20' ] || exit 64
[ "$data_owner" = '501:20' ] || exit 64
[ "$data_mode" = '700' ] || exit 64
exec /usr/local/bin/docker-entrypoint.sh postgres
