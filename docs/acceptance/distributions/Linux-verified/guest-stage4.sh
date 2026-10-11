#!/bin/bash
set -euo pipefail
export RUSTUP_HOME=/usr/local/rustup CARGO_HOME=/usr/local/cargo
export RUSTUP_TOOLCHAIN=1.99.0-aarch64-unknown-linux-gnu
export PATH=/opt/bindloom-python/bin:/usr/local/cargo/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export CARGO_INCREMENTAL=0 CARGO_PROFILE_DEV_DEBUG=0 CARGO_PROFILE_TEST_DEBUG=0 CARGO_TERM_COLOR=never
unset HOME SDKROOT
mkdir -p /output
mount -t virtiofs bindloom-results /output
trap 'status=$?; test ! -d /results/Linux-verified || cp -R /results/Linux-verified /output/; exit "$status"' EXIT
python3 - <<'PY'
import pathlib,json,hashlib,tarfile
archive=pathlib.Path('/share/final-source.tar.gz')
receipt=json.loads(pathlib.Path('/share/final-inputs.json').read_text())
assert 'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sourceArchive']['digest']
target=pathlib.Path('/final-input-verified');target.mkdir()
with tarfile.open(archive) as tar: tar.extractall(target,filter='data')
source=next(target.glob('bindloom-draft-*'))
assert 'sha256:'+hashlib.sha256((source/'source-inventory.json').read_bytes()).hexdigest()==receipt['sourceInventoryDigest']
for entry in json.loads((source/'source-inventory.json').read_text()):
 raw=(source/entry['path']).read_bytes()
 assert len(raw)==entry['bytes'] and 'sha256:'+hashlib.sha256(raw).hexdigest()==entry['digest'],entry['path']
print('BINDLOOM_FINAL_SOURCE_INPUT_VERIFIED',receipt['sourceInventoryDigest'])
PY
cd /final-input-verified/bindloom-draft-07f74356f72d
python3 scripts/package.py --binary /source/target/release/bindloom --activator-binary /source/target/release/bindloom-activator --build-profile release --output /results/Linux-verified
python3 scripts/test_distribution.py /results/Linux-verified --node /usr/local/node/bin/node --tsc /reference/node_modules/typescript/lib/tsc.js --reference /reference --output /results/Linux-verified/installation.json
cp /share/guest-stage4.sh /results/Linux-verified/guest-stage4.sh
printf 'BINDLOOM_LINUX_STAGE4_PASS\n'
