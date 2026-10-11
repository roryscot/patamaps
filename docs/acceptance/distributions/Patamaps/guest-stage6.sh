#!/bin/bash
set -euo pipefail
unset HOME SDKROOT
export RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
export RUSTUP_TOOLCHAIN=1.99.0-aarch64-unknown-linux-gnu
export PATH=/opt/bindloom-python/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_TERM_COLOR=never
mkdir -p /output /results/Patamaps-final
mount -t virtiofs bindloom-results /output
trap 'status=$?; cp -R /results/Patamaps-final /output/; exit "$status"' EXIT
cp /share/guest-stage6.sh /results/Patamaps-final/guest-stage6.sh
python3 - <<'PY'
import hashlib,json,pathlib,tarfile
p=pathlib.Path('/share/patamaps-final-source.tar.gz');j=json.loads(pathlib.Path('/share/patamaps-final-source.json').read_text());assert 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()==j['sourceArchive']['digest']
r=pathlib.Path('/patamaps-final-source');r.mkdir()
with tarfile.open(p) as t:t.extractall(r,filter='data')
s=next(r.glob('patamaps-draft-*'))
assert 'sha256:'+hashlib.sha256((s/'source-inventory.json').read_bytes()).hexdigest()==j['sourceInventoryDigest']
for e in json.loads((s/'source-inventory.json').read_text()):
 b=(s/e['path']).read_bytes();assert len(b)==e['bytes'] and 'sha256:'+hashlib.sha256(b).hexdigest()==e['digest']
print('PATAMAPS_FINAL_SOURCE_VERIFIED',j['sourceInventoryDigest'])
PY
cd /patamaps-final-source/patamaps-draft-f5e64903ab9a
python3 scripts/package.py --binary /source/target/release/patamaps --activator-binary /source/target/release/patamaps-activator --build-profile release --output /results/Patamaps-final/Linux
python3 scripts/test_distribution.py /results/Patamaps-final/Linux --node /usr/local/node/bin/node --tsc /reference/node_modules/typescript/lib/tsc.js --reference /reference --output /results/Patamaps-final/Linux/installation.json
printf 'PATAMAPS_LINUX_STAGE6_PASS\n'
