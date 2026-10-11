"""Compare finite numeric JCS ingress/encoding with independent ECMAScript."""
import argparse
import json
import math
import random
import struct
import subprocess
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument("--cli",type=Path,default=ROOT / "target/debug/patamaps")
parser.add_argument("--node",type=Path,required=True)
args=parser.parse_args()
rng=random.Random(8785)
values=[-0.0,5e-324,-5e-324,1e-7,1e-6,1e20,1e21,9007199254740991,9007199254740993,18446744073709551615]
for _ in range(4096):
    value=struct.unpack('>d',rng.getrandbits(64).to_bytes(8,'big'))[0]
    if math.isfinite(value): values.append(value)
with tempfile.TemporaryDirectory(prefix="patamaps-canonical-") as directory:
    path=Path(directory)/"numbers.json"
    path.write_text(json.dumps(values,allow_nan=False))
    rust=subprocess.check_output([str(args.cli.resolve()),"canonical",str(path)]).strip()
    javascript=subprocess.check_output([str(args.node),"--input-type=module","-e","import{readFileSync}from'node:fs';process.stdout.write(JSON.stringify(JSON.parse(readFileSync(process.argv[1],'utf8'))));",str(path)]).strip()
    assert rust==javascript,"Finite numeric JCS bytes disagree with ECMAScript"
    print(f"PASS: {len(values)} deterministic binary64 and integer boundary inputs match independent ECMAScript JSON bytes (seed 8785).")
