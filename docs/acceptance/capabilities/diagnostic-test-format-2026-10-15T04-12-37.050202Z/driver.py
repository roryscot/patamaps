from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,runpy,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"scripts/parity"))
from storage_guard import ensure_guarded
from identity import identities
ensure_guarded()
sha=lambda p:"sha256:"+hashlib.sha256(p.read_bytes()).hexdigest()
out=ROOT/"docs/acceptance/capabilities"/datetime.now(timezone.utc).strftime("diagnostic-test-format-%Y-%m-%dT%H-%M-%S.%fZ");out.mkdir()
(out/"driver.py").write_bytes(Path(__file__).read_bytes())
before={p.relative_to(ROOT).as_posix():sha(p) for p in (ROOT/"crates").rglob("*.rs")}
engine_before=identities(ROOT)
argv=[str(Path.home()/".cargo/bin/cargo"),"fmt","--all"]
result=subprocess.run(argv,cwd=ROOT,capture_output=True)
for stream in ["stdout","stderr"]:(out/("format."+stream+".log")).write_bytes(getattr(result,stream))
assert result.returncode==0
changed=[{"path":name,"beforeDigest":digest,"afterDigest":sha(ROOT/name)} for name,digest in before.items() if sha(ROOT/name)!=digest]
allowed={"crates/patamaps-inspect/tests/inspection.rs","crates/patamaps-inspect/tests/source_inspection.rs","crates/patamaps-workspace/tests/source_evaluation.rs"}
assert {v["path"] for v in changed}<=allowed
assert identities(ROOT)==engine_before
(out/"receipt.json").write_text(json.dumps({"status":"passed","argv":argv,"exitCode":result.returncode,"formattedTestFiles":changed,"productionEnginesUnchanged":True,"engines":engine_before,"priorFailedCompiler":"docs/acceptance/capabilities/compiler-2026-10-15T04-09-36.057406Z/receipt.json","scope":"Format newly strengthened native test assertions before the fresh complete compiler milestone; prior formatting failure and all logs remain preserved.","deleted":[]},indent=2)+"\n")
runpy.run_path(str(ROOT/"scripts/capabilities/compiler.py"),run_name="__main__")
