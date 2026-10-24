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
 test "$(cat /proc/sys/net/ipv6/conf/all/disable_ipv6)" = 0
 test "$(cat /proc/sys/net/ipv6/conf/lo/disable_ipv6)" = 0
 /usr/bin/python3 -B - <<'IPV6'
import socket
addresses=socket.getaddrinfo('localhost',0)
assert any(row[0]==socket.AF_INET6 and row[4][0]=='::1' for row in addresses)
assert any(row[0]==socket.AF_INET and row[4][0]=='127.0.0.1' for row in addresses)
with socket.socket(socket.AF_INET6) as server:
 server.bind(('::1',0));server.listen(1)
 with socket.socket(socket.AF_INET6) as client:
  client.connect(server.getsockname())
  peer,_=server.accept()
  with peer:
   client.sendall(b'loopback');assert peer.recv(32)==b'loopback'
print('ipv6-loopback-passed')
IPV6
 if /usr/sbin/ip -6 route get 2001:db8::1 >/work/no-ipv6-external-route 2>&1; then
  exit 72
 else
  test "$?" = 2
  grep -q 'Network is unreachable' /work/no-ipv6-external-route
 fi
 printf 'ipv6-external-route-absent\n'
 cat >/work/loopback-probe.rs <<'RUST'
use std::net::{TcpListener, TcpStream};
fn main() {
    for address in ["127.0.0.1", "::1"] {
        let server = TcpListener::bind((address, 0)).expect("literal loopback bind");
        let _client = TcpStream::connect(("localhost", server.local_addr().unwrap().port()))
            .expect("dual-stack localhost fixture lookup");
    }
}
RUST
 "$RUSTC" /work/loopback-probe.rs -o /work/loopback-probe
 /work/loopback-probe
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
