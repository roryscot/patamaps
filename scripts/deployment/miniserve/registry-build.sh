#!/bin/bash
set -euo pipefail
trap 'printf "REGISTRY_STARTUP_FAILED_LINE=%s\n" "$LINENO" >&2' ERR
trap 'exit 130' TERM INT HUP
mkdir -p /work/{home,tmp,logs,export,cargo-home/registry}
ln -s /registry/cache /work/cargo-home/registry/cache
ln -s /registry/index /work/cargo-home/registry/index
{
 cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/pids.max
 test "$(cat /sys/fs/cgroup/cpu.max)" = '200000 100000'
 test "$(cat /sys/fs/cgroup/memory.max)" = 6442450944
 test "$(cat /sys/fs/cgroup/memory.swap.max)" = 0
 test "$(cat /sys/fs/cgroup/pids.max)" = 512
 test "$(df -B1 /work | tail -1 | awk '{print $2}')" = 3221225472
 df -B1 /work | tail -1 | awk '{print $2}'
 df -k /dev /dev/shm | tail -2 | awk '{print $2}'
 test "$(df -k /dev | tail -1 | awk '{print $2}')" = 65536
 test "$(df -k /dev/shm | tail -1 | awk '{print $2}')" = 1024
 test "$(ls /sys/class/net)" = lo
 printf 'lo\n'
 test -x /usr/sbin/ip
 if /usr/sbin/ip route get 192.0.2.1 >/work/no-external-route 2>&1; then
  route_status=0
 else
  route_status=$?
 fi
 test "$route_status" = 2
 grep -q 'Network is unreachable' /work/no-external-route
 printf 'external-route-absent\n'
} >/work/logs/limits.txt
finish() {
 printf '%s\n' "$1" >/work/exit
 printf 'done\n' >/work/done
 while :; do sleep 1; done
}
: >/work/logs/build.stdout
: >/work/logs/build.stderr
: >/work/logs/test.stdout
: >/work/logs/test.stderr
if "$CARGO" build --release --locked --offline --target x86_64-unknown-linux-gnu --bin miniserve >/work/logs/build.stdout 2>/work/logs/build.stderr; then
 cp /work/target/x86_64-unknown-linux-gnu/release/miniserve /work/export/miniserve
 printf 'ready\n' >/work/build.ready
else
 finish "$?"
fi
while [ ! -f /work/build.accepted ]; do sleep .1; done
cd /test-source
if "$CARGO" test --release --locked --offline --target x86_64-unknown-linux-gnu >/work/logs/test.stdout 2>/work/logs/test.stderr; then
 finish 0
else
 finish "$?"
fi
