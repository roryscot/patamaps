#!/bin/bash
set -euo pipefail
mode=$1
logs=$2
mkdir -p "$logs"
cd bundle
server=''
cleanup() { if [ -n "$server" ] && kill -0 "$server" 2>/dev/null; then kill -TERM "$server"; wait "$server" || :; fi; }
trap cleanup EXIT
check() { printf '%s\n' "$1" >> $logs/passed-controls.txt; }
request() {
 local port=$1 path=$2 method=$3 label=$4
 printf '%s\t%s\t%s\t%s\n' "$label" "$port" "$method" "$path" >> $logs/request-attempts.tsv
 timeout 4 /bin/bash -c 'set -e; exec 3<>/dev/tcp/127.0.0.1/"$1"; printf "%s %s HTTP/1.0\r\nHost: localhost\r\nConnection: close\r\n\r\n" "$3" "$2" >&3; /bin/cat <&3' bash "$port" "$path" "$method" > "$logs/$label.http" 2> "$logs/$label.stderr"
}
ready() {
 local port=$1 prefix=$2
 for i in $(seq 1 60); do
  if request "$port" /qualified/status.txt GET "$prefix-$i" && grep -Eq '^HTTP/1\.[01] 200' "$logs/$prefix-$i.http"; then return 0; fi
  kill -0 "$server"
  sleep .1
 done
 return 1
}
if [ "$mode" = wrong-listener ]; then
 env -i PATH=/usr/bin:/bin LANG=C ./miniserve public --interfaces 127.0.0.1 --port 9101 --workers 1 --route-prefix /qualified --no-symlinks --quiet > "$logs/fault.stdout" 2> "$logs/fault.stderr" &
 server=$!
 ready 9101 fault-ready
 if request 9100 /qualified/status.txt GET fault-expected-listener; then exit 94; fi
 kill -0 "$server"
 printf 'CONFIRMED_WRONG_LISTENER_REFUSED\n' >&2
 exit 1
fi
test "$mode" = positive
test "$(env -i PATH=/usr/bin:/bin ./miniserve --version)" = 'miniserve 0.35.0'
check pinned-version-startup
./launch.sh > $logs/service.stdout 2> $logs/service.stderr &
server=$!
ready 9100 readiness
request 9100 /qualified/status.txt GET get-document
grep -Eq '^HTTP/1\.[01] 200' $logs/get-document.http
sed '1,/^\r$/d' $logs/get-document.http > $logs/get-document.body
cmp public/status.txt $logs/get-document.body
check exact-get-body
request 9100 /qualified/status.txt HEAD head-document
grep -Eq '^HTTP/1\.[01] 200' $logs/head-document.http
tr -d '\r' < $logs/head-document.http > $logs/head-document.normalized
grep -Eiq "^content-length: $(wc -c < public/status.txt | tr -d ' ')$" $logs/head-document.normalized
sed '1,/^\r$/d' $logs/head-document.http > $logs/head-document.body
test ! -s $logs/head-document.body
check head-length-and-empty-body
request 9100 /qualified/ GET listing
grep -Eq '^HTTP/1\.[01] 200' $logs/listing.http
grep -q status.txt $logs/listing.http
check directory-listing
request 9100 /qualified/not-present.txt GET missing
grep -Eq '^HTTP/1\.[01] 404' $logs/missing.http
check missing-document-refused
request 9100 /status.txt GET outside-prefix
grep -Eq '^HTTP/1\.[01] 404' $logs/outside-prefix.http
check out-of-prefix-refused
set +e
timeout 5 env -i PATH=/usr/bin:/bin ./miniserve public --port 65536 > $logs/invalid-port.stdout 2> $logs/invalid-port.stderr
code=$?
set -e
test "$code" = 2
check invalid-port-refused
kill -TERM "$server"; wait "$server" || :
server=''
env -i PATH=/usr/bin:/bin LANG=C ./miniserve public --interfaces 127.0.0.1 --port 9101 --workers 1 --route-prefix /qualified --no-symlinks --quiet > $logs/wrong-listener.stdout 2> $logs/wrong-listener.stderr &
server=$!
ready 9101 wrong-listener-ready
if request 9100 /qualified/status.txt GET wrong-expected-listener; then exit 93; fi
kill -0 "$server"
check wrong-listener-readiness-refused
cleanup
server=''
printf '{"status":"passed-miniserve-linux-http","network":"loopback","productionActivation":false}\n' > "$logs/runtime-receipt.json"
printf 'passed-miniserve-linux-http\n'
