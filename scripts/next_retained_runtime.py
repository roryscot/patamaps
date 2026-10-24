"""CI-only retained Next runtime: private image/output data and an isolated bounded cache."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

from deployment_miniserve_image import stop_owned
from qualify_next_standalone import inventory, summary, changed_summary

ROOT = Path(__file__).resolve().parent.parent
BASE = "node@sha256:bbf39cb344bb33c1f2eedb3b45b4a890eecfbac91a4f7bac020a95d4e4ea147e"
BASE_CONFIG = "sha256:ecf6aca355bb97426fb9e9b3616c9d92dbae14b96f4851d1b47d2d6fe51c1a0d"
TEST_DIGEST = "sha256:d4a2ea78a5e1019aedef533e8b778f4345a5efe1d2c8fbd0ddb42cbbda19bc66"
CACHE_BYTES = 67108864
MEMORY_BYTES = 3221225472
DRIVERS = [
    "qualify_chatbot_runtime.py", "qualify_chatbot_auth.mjs", "chatbot_rewrite_profile.py",
    "qualify_chatbot_next.py", "qualify_next_standalone.py", "project_watch.py",
    "deployment_miniserve_image.py", "next_retained_runtime.py",
]
ENVIRONMENT = [
    "PATH", "HOME", "TMPDIR", "LANG", "TZ", "CI", "CI_PLAYWRIGHT", "NODE_OPTIONS",
    "NEXT_TELEMETRY_DISABLED", "PLAYWRIGHT_BROWSERS_PATH", "PLAYWRIGHT_SKIP_BROWSER_GC",
    "npm_config_userconfig", "npm_config_globalconfig",
]

PROBE_NODE = r"""
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
function hash(p){const h=crypto.createHash('sha256'),fd=fs.openSync(p,'r'),b=Buffer.alloc(65536);
try{let n;while((n=fs.readSync(fd,b,0,b.length,null)))h.update(b.subarray(0,n));}finally{fs.closeSync(fd);}return 'sha256:'+h.digest('hex');}
const rows=Object.create(null);function walk(p,name){const s=fs.lstatSync(p),mode=s.mode&0o7777;
if(s.isSymbolicLink()){rows[name]={kind:'symlink',mode,target:fs.readlinkSync(p),targetFollowed:false};return;}
if(s.isDirectory()){rows[name]={kind:'directory',mode};for(const n of fs.readdirSync(p).sort())walk(path.join(p,n),name==='.'?n:name+'/'+n);}
else{if(!s.isFile())throw Error('SPECIAL');rows[name]={kind:'file',mode,bytes:s.size,digest:hash(p)};}}
walk('/bundle','.');
const limits={};for(const [k,n] of Object.entries({cpu:'cpu.max',memory:'memory.max',swap:'memory.swap.max',pids:'pids.max'}))limits[k]=fs.readFileSync('/sys/fs/cgroup/'+n,'utf8').trim();
let readonly=false;try{const fd=fs.openSync('/bundle/server.js','r+');fs.closeSync(fd);}catch(e){readonly=e.code==='EROFS';}
const cache='/bundle/.next/cache',stats=fs.statfsSync(cache);
fs.writeFileSync(cache+'/controlled-write',Buffer.from('x'));
let quota=false,written=0;const fd=fs.openSync(cache+'/controlled-quota','w'),buf=Buffer.alloc(65536);
try{while(written<100663296){written+=fs.writeSync(fd,buf);}}catch(e){quota=e.code==='ENOSPC';}finally{fs.closeSync(fd);}
console.log(JSON.stringify({inventory:rows,limits,nodeVersion:process.version,uid:process.getuid(),readonly,cacheWritable:true,cacheQuotaBytes:stats.bsize*stats.blocks,quotaRefused:quota,quotaBytesWritten:written}));
"""
CACHE_NODE = r"""
const fs=require('node:fs'),path=require('node:path');let files=0,dirs=0,links=0,bytes=0;
function walk(p){const s=fs.lstatSync(p);if(s.isSymbolicLink()){links++;return;}if(s.isDirectory()){dirs++;for(const n of fs.readdirSync(p))walk(path.join(p,n));}else{if(!s.isFile())throw Error('SPECIAL');files++;bytes+=s.size;}}
walk('/bundle/.next/cache');const limits={};for(const [k,n] of Object.entries({cpu:'cpu.max',memory:'memory.max',swap:'memory.swap.max',pids:'pids.max'}))limits[k]=fs.readFileSync('/sys/fs/cgroup/'+n,'utf8').trim();
console.log(JSON.stringify({files,directories:dirs,symlinks:links,bytes,limits,nodeVersion:process.version}));
"""

def environment_references(configuration):
    references={key.upper():key for key in configuration}
    assert len(references)==len(configuration), "RETAINED_ENVIRONMENT_COLLISION"
    assert all(re.fullmatch("[A-Z_][A-Z_0-9]*",key) for key in references), "RETAINED_ENVIRONMENT_NAME"
    return references

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+"\n")

def digest(path):
    with Path(path).open("rb") as source:
        return "sha256:"+hashlib.file_digest(source,"sha256").hexdigest()

def present(path):
    return path.exists() or path.is_symlink()

class ProducerMoves:
    """Rename only declared owned paths; never overwrite a conflicting original."""
    def __init__(self, private):
        self.private=private
        self.items=[]
    def take(self, original, relocated=None):
        original=Path(original)
        relocated=Path(relocated) if relocated else self.private/("producer-unavailable-"+str(len(self.items)))
        assert present(original) and not present(relocated), "RETAINED_MOVE_PRECONDITION"
        self.items.append((original,relocated))
        write(self.private/"producer-moves.json",[dict(original=str(a),retained=str(b)) for a,b in self.items])
        original.rename(relocated)
        assert not present(original) and present(relocated), "RETAINED_MOVE_UNAVAILABLE"
    def restore(self):
        conflicts=[]
        for original,relocated in reversed(self.items):
            if present(relocated):
                if present(original):
                    conflicts.append(str(original));continue
                relocated.rename(original)
            elif not present(original):
                conflicts.append(str(original))
        assert not conflicts,"RETAINED_MOVE_RESTORATION_REQUIRES_REVIEW"

def check_limits(value):
    assert value==dict(cpu="100000 100000",memory=str(MEMORY_BYTES),swap="0",pids="128"),"RETAINED_KERNEL_LIMITS"

def check_container(info, image, role):
    host=info["HostConfig"]
    assert info["Image"]==image and info["Config"]["User"]=="1000:1000" and info["Config"]["WorkingDir"]=="/bundle","RETAINED_CONTAINER_IDENTITY"
    assert host["ReadonlyRootfs"] and host["NetworkMode"]=="host" and not host.get("Binds"),"RETAINED_CONTAINER_MOUNTS"
    assert host["NanoCpus"]==1000000000 and host["Memory"]==MEMORY_BYTES and host["MemorySwap"]==MEMORY_BYTES and host["PidsLimit"]==128,"RETAINED_CONTAINER_LIMITS"
    assert host["CapDrop"]==["ALL"] and "no-new-privileges" in host["SecurityOpt"],"RETAINED_CONTAINER_PRIVILEGES"
    assert not host.get("Privileged") and not host.get("Devices") and not host.get("DeviceRequests"),"RETAINED_CONTAINER_PRIVILEGES"
    assert not host.get("Mounts") and all(m.get("Type")=="tmpfs" and m.get("Destination")=="/bundle/.next/cache" for m in info.get("Mounts",[])),"RETAINED_CONTAINER_MOUNTS"
    assert set(host["Tmpfs"])=={"/bundle/.next/cache"} and "size=67108864" in host["Tmpfs"]["/bundle/.next/cache"],"RETAINED_CACHE_MOUNT"
    expected=["/usr/local/bin/node"] if role=="probe" else ["/usr/local/bin/node","/bundle/server.js"]
    assert info["Config"]["Entrypoint"]==expected,"RETAINED_ENTRYPOINT"
    if role=="probe":
        assert info["Config"].get("Cmd")==["-e",PROBE_NODE],"RETAINED_ENTRYPOINT"
    else:
        assert info["Config"].get("Cmd") in [None,[]],"RETAINED_ENTRYPOINT"

class RetainedNextRuntime:
    def __init__(self, config, owner, work, private, evidence, environment, execute, monitor):
        self.config=config;self.owner=owner;self.work=work;self.private=private;self.evidence=evidence
        self.environment=environment;self.execute=execute;self.monitor=monitor
        self.moves=ProducerMoves(private);self.harness=private/"unchanged-test-harness"
        self.owned_path=evidence/"retained-owned.json"
        self.owned=dict(token=uuid.uuid4().hex,images=[],containers=[],filesDeleted=0)
        write(self.owned_path,self.owned)
        self.report=dict(status="preparing",base=BASE,cacheQuotaBytes=CACHE_BYTES,
            hostNetwork=True,networkIsolationClaimed=False,rawInspectAndRuntimeLogsPublished=False,
            productionActivation=False,registryPublication=False,completeDependencyClosure=False)
    def call(self,label,argv,timeout=120):
        self.execute(label,argv,self.environment,timeout=timeout,cwd=self.work)
        path=self.private/(label+".stdout")
        assert path.stat().st_size<33554432
        return path.read_text()
    def inspect(self,cid,label):
        return json.loads(self.call(label,["docker","inspect",cid]))[0]
    def create(self,role,secret_env=None):
        argv=["docker","create","--label","org.patamaps.qualification-owner="+self.owned["token"],
            "--network","host","--platform","linux/amd64","--user","1000:1000",
            "--cpus","1","--memory",str(MEMORY_BYTES),"--memory-swap",str(MEMORY_BYTES),
            "--pids-limit","128","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges",
            "--shm-size","1048576","--tmpfs","/bundle/.next/cache:rw,noexec,nosuid,nodev,size=67108864,mode=0700,uid=1000,gid=1000"]
        if secret_env is not None:
            envfile=self.private/"container-environment"
            allowed=["NODE_ENV","AUTH_SECRET","POSTGRES_URL","AUTH_URL","AUTH_TRUST_HOST","CI_PLAYWRIGHT","NEXT_TELEMETRY_DISABLED","NODE_OPTIONS","HOSTNAME","PORT"]
            values={k:secret_env[k] for k in allowed if k in secret_env}
            assert all("\n" not in v and "\r" not in v for v in values.values())
            envfile.write_text("".join(k+"="+v+"\n" for k,v in values.items()));envfile.chmod(0o600)
            argv+=["--env-file",str(envfile)]
        if role=="probe":argv+=["--entrypoint","/usr/local/bin/node"]
        argv+=[self.image]
        if role=="probe":argv+=["-e",PROBE_NODE]
        cid=self.call("retained-"+role+"-create",argv).strip()
        assert re.fullmatch("[0-9a-f]{64}",cid) and cid not in {x["id"] for x in self.owned["containers"]},"RETAINED_CONTAINER_ID"
        self.owned["containers"].append(dict(id=cid,role=role,confirmedStopped=False));write(self.owned_path,self.owned)
        info=self.inspect(cid,"retained-"+role+"-inspect")
        check_container(info,self.image,role)
        return cid
    def prepare(self):
        self.report["phase"]="docker-filesystem"
        docker_root=Path(self.call("retained-docker-data-root",["docker","info","--format","{{.DockerRootDir}}"]).strip())
        assert docker_root.is_absolute() and docker_root.stat().st_dev==self.work.stat().st_dev,"RETAINED_DOCKER_FILESYSTEM_MONITOR"
        self.report["dockerDataSharesMonitoredFilesystem"]=True
        self.bundle=Path(self.config["state"])/self.config["attempt"]/"candidate/bundle"
        self.expected=inventory(self.bundle)
        assert (self.bundle/".next/cache").is_dir() and not list((self.bundle/".next/cache").iterdir()),"RETAINED_CACHE_PREIMAGE"
        context=self.bundle.parent
        dockerfile=self.private/"retained-runtime.Dockerfile"
        self.report["imageContext"]="native-selected-candidate"
        root_mode=self.expected["."]["mode"]
        assert type(root_mode) is int and 0<=root_mode<=0o7777
        dockerfile.write_text("FROM "+BASE+"\nWORKDIR /bundle\nCOPY --chown=1000:1000 bundle/ /bundle/\nRUN chown 1000:1000 /bundle && chmod "+format(root_mode,"04o")+" /bundle\nUSER 1000:1000\nENTRYPOINT [\"/usr/local/bin/node\",\"/bundle/server.js\"]\nCMD []\n")
        self.report["phase"]="pinned-image-build"
        self.call("retained-pull-node",["docker","pull","--platform","linux/amd64",BASE],timeout=180)
        base=json.loads(self.call("retained-node-inspect",["docker","image","inspect",BASE]))[0]
        assert base["Id"]==BASE_CONFIG and (base["Os"],base["Architecture"])==("linux","amd64"),"RETAINED_NODE_BASE"
        iid=self.private/"image.iid"
        self.call("retained-build-image",["docker","buildx","build","--load","--platform","linux/amd64","--network","none","--provenance=false","--progress","plain","--iidfile",str(iid),"--file",str(dockerfile),str(context)],timeout=300)
        self.image=iid.read_text().strip();assert re.fullmatch("sha256:[0-9a-f]{64}",self.image)
        image=json.loads(self.call("retained-image-inspect",["docker","image","inspect",self.image]))[0]
        assert image["Size"]<536870912 and (image["Os"],image["Architecture"])==("linux","amd64"),"RETAINED_IMAGE_PLATFORM"
        self.owned["images"].append(self.image);write(self.owned_path,self.owned)
        self.report["phase"]="kernel-and-image-proof"
        probe=self.create("probe")
        proof=json.loads(self.call("retained-kernel-quota-proof",["docker","start","--attach",probe],timeout=120))
        assert int(self.call("retained-proof-wait",["docker","wait",probe]).strip())==0
        self.report["imageDifference"]=changed_summary(self.expected,proof["inventory"])
        self.report["enforcementObservation"]={key:proof[key] for key in ["limits","nodeVersion","uid","readonly","cacheWritable","cacheQuotaBytes","quotaRefused","quotaBytesWritten"]}
        assert proof["inventory"]==self.expected,"RETAINED_IMAGE_BYTES_MODES_LINKS"
        check_limits(proof["limits"])
        assert proof["nodeVersion"]=="v22.23.3" and proof["uid"]==1000 and proof["readonly"] and proof["cacheWritable"] and proof["quotaRefused"] and proof["cacheQuotaBytes"]==CACHE_BYTES,"RETAINED_REAL_ENFORCEMENT"
        self.report.update(imageId=self.image,nodeVersion=proof["nodeVersion"],imageBundle=summary(self.expected),
            imageBytesModesAndLinkTargetsVerified=True,kernelLimits=proof["limits"],
            readonlyWriteRefused=True,cacheWritePassed=True,cacheQuotaFailurePassed=True,
            probeCacheSeparateFromApp=True,hostSourceOrCompilerMount=False)
    def hide_producer(self):
        self.harness.mkdir();(self.harness/"tests/e2e").mkdir(parents=True)
        source_test=self.owner/"tests/e2e/auth.test.ts"
        assert digest(source_test)==TEST_DIGEST,"RETAINED_UPSTREAM_TEST_IDENTITY"
        shutil.copy2(source_test,self.harness/"tests/e2e/auth.test.ts")
        shutil.copy2(self.owner/"package.json",self.harness/"package.json")
        self.moves.take(self.owner/"node_modules",self.harness/"node_modules")
        for value in self.config["unavailablePaths"]:
            self.moves.take(Path(value))
        assert all(not present(Path(p)) for p in self.config["unavailablePaths"]),"RETAINED_SOURCE_TOOL_UNAVAILABLE"
        assert not (self.owner/"node_modules").exists()
        self.report.update(producerSourceAndToolsUnavailable=True,
            unavailableProducerPaths=len(self.config["unavailablePaths"]),
            separateUnchangedTestDigest=TEST_DIGEST,testHarnessApplicationSourceCopied=False)
    def release_port(self,port):
        request=Path(self.config["handoffRequest"]);ack=Path(self.config["handoffAck"])
        assert not request.exists() and not ack.exists(),"RETAINED_PORT_HANDOFF"
        write(request,dict(port=port,profileDigest=self.config["rewrite"]["profileDigest"]))
        started=time.monotonic()
        while not ack.exists():
            self.monitor();assert time.monotonic()-started<15,"RETAINED_PORT_HANDOFF"
            time.sleep(.1)
        assert json.loads(ack.read_bytes())==dict(port=port,profileDigest=self.config["rewrite"]["profileDigest"]),"RETAINED_PORT_HANDOFF"
    def server(self,trusted,port):
        self.report["phase"]="source-tool-unavailable-start"
        self.hide_producer()
        self.app=self.create("app",trusted)
        self.release_port(port)
        return ["docker","start","--attach",self.app]
    def after_browser(self):
        self.report["phase"]="post-browser-cache-and-generation"
        value=json.loads(self.call("retained-app-cache-summary",["docker","exec",self.app,"/usr/local/bin/node","-e",CACHE_NODE]))
        check_limits(value["limits"])
        assert value["nodeVersion"]=="v22.23.3" and value["files"]>0 and 0<value["bytes"]<CACHE_BYTES and value["symlinks"]==0,"RETAINED_APP_CACHE"
        assert inventory(self.bundle)==self.expected,"RETAINED_GENERATION_CHANGED"
        assert all(not present(Path(p)) for p in self.config["unavailablePaths"]),"RETAINED_SOURCE_TOOL_REAPPEARED"
        self.report.update(status="passed-private-retained-next-runtime",applicationCache=value,selectedGenerationUnchanged=True,
            producerUnavailableThroughoutBrowser=True,fullSourceOrOsClosure=False)
    def finish(self):
        try:
            stop_owned(self.owned_path)
            owned=json.loads(self.owned_path.read_bytes())
            assert all(x["confirmedStopped"] for x in owned["containers"]),"RETAINED_CONTAINER_STOP"
            self.report["allOwnedContainersStopped"]=True
        finally:
            self.moves.restore()
            self.report["renamedProducerPathsRestored"]=True

def main():
    assert sys.platform=="linux" and os.environ.get("GITHUB_ACTIONS")=="true"
    config=json.loads(Path(sys.argv[1]).read_bytes())
    assert config["profile"]=="patamaps-retained-next-runtime-1"
    state=Path(config["state"])
    pointer=json.loads((state/"selected.json").read_bytes())
    config["attempt"]=pointer["attempt"]
    assert ROOT.resolve()==(state/config["attempt"]/"candidate").resolve(),"RETAINED_SELECTED_COORDINATOR"
    work=Path(config["runtimeWork"]);work.mkdir(mode=0o700)
    evidence=Path(config["evidence"])
    def capacity():
        disk=shutil.disk_usage(work)
        assert disk.free>=500000000,"RETAINED_RUNTIME_RESERVE"
    from qualify_chatbot_runtime import qualify
    result=qualify(Path(config["owner"]),work,evidence,Path(config["pnpm"]),dict(os.environ),capacity,
        rewrite_profile=config["rewrite"],standalone_root=Path(config["standalone"]),retained=config)
    assert result["status"]=="passed" and result["retainedRuntime"]["allOwnedContainersStopped"]
    print("retained-next-private-runtime-passed")

if __name__=="__main__":
    main()
