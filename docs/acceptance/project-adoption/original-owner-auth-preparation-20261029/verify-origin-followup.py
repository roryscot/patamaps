from pathlib import Path
import json,hashlib
R=Path("/Volumes/dev_src_case_sensitive/projects/patamaps");O=Path("/Volumes/dev_src_case_sensitive/projects/seeder")
B=R/"docs/acceptance/project-adoption/original-owner-auth-preparation-20261029"
v=json.loads((B/"compiled-origin-followup.json").read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for row in v["sourceInputs"]:assert sha(O/row["path"])==row["sha256"]
app=Path(json.loads((R/".tools/original-owner-five-project-browser-20261027/browser-config.json").read_text())["http"]["app"])
p=app/v["compiledClientChunk"];assert sha(p)==v["compiledClientChunkSha256"]
s=p.read_text()
assert 'constructor(e){const t="http://127.0.0.1:1",i=e||'in s
sources={row["path"]:(O/row["path"]).read_text()for row in v["sourceInputs"]}
assert '@/services/authService'in sources["packages/web/src/app/login/page.tsx"]
assert'apiClient.post<Token>'in sources["packages/web/src/services/authService.ts"]
assert'from "../lib/api/client-app"'in sources["packages/web/src/services/authService.ts"]
assert'new AppApiClient()'in sources["packages/web/src/lib/api/client-app.ts"]
assert not v["browserNetworkObserved"]and not v["completeBundlerCallGraphProven"]
print("Compiled default origin/source bindings verified; actual browser network and whole bundle call graph remain unrun.")
