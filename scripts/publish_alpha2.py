"""Publish the exact CI-verified alpha.2 archives; defaults to a read-only preflight."""
import argparse,hashlib,io,json,struct,tarfile,time,tomllib,urllib.error,urllib.request,zipfile
from pathlib import Path
NAMES=["patamaps-workspace","patamaps-inspect","patamaps-cli"]
VERSION="0.1.0-alpha.2"
ZIP_SHA="b50730c61fa9873bb5a38fb76ee1693041492f237ee4e9768cf78ea24e745086"
def request(url,data=None,token=None):
    headers={"User-Agent":"patamaps-alpha2-release (github.com/roryscot/patamaps)","Accept":"application/json"}
    if token:headers["Authorization"]=token
    if data is not None:headers["Content-Type"]="application/octet-stream"
    req=urllib.request.Request(url,data=data,headers=headers,method="PUT" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req,timeout=45) as response:return response.read()
    except urllib.error.HTTPError as e:
        if e.code==404 and data is None:return None
        raise RuntimeError("Registry request failed HTTP "+str(e.code)) from None
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence",required=True,type=Path)
    parser.add_argument("--execute",action="store_true")
    args=parser.parse_args()
    raw=(args.evidence/"evidence.zip").read_bytes()
    assert hashlib.sha256(raw).hexdigest()==ZIP_SHA
    ci=json.loads((args.evidence/"ci.json").read_text())
    assert ci["run"]["id"]==40117789049 and ci["run"]["conclusion"]=="success"
    assert ci["run"]["head_sha"]=="f160d0dcb5ff15ef3f13f5316495bd0e0aa902de"
    archive=zipfile.ZipFile(io.BytesIO(raw))
    proof=json.loads(archive.read("clean-install/receipt.json"))
    assert proof["exitCode"]==0 and proof["freshCargoHome"] and proof["generatedRustConsumer"]=="passed"
    assert [p["name"] for p in proof["archives"]]==NAMES
    candidates=[]
    for record in proof["archives"]:
        name=record["name"]
        data=archive.read("target/package/"+name+"-"+VERSION+".crate")
        assert hashlib.sha256(data).hexdigest()==record["sha256"]
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
            manifest=tomllib.loads(tar.extractfile(name+"-"+VERSION+"/Cargo.toml").read().decode())
        pkg=manifest["package"]
        assert pkg["name"]==name and pkg["version"]==VERSION
        deps=[]
        for target,group in [(None,manifest),*manifest.get("target",{}).items()]:
            for table,kind in [("dependencies","normal"),("build-dependencies","build"),("dev-dependencies","dev")]:
                for alias,dep in group.get(table,{}).items():
                    if isinstance(dep,str):dep={"version":dep}
                    assert not any(k in dep for k in ["path","git","workspace"])
                    deps.append({"name":dep.get("package",alias),"version_req":dep["version"],"features":dep.get("features",[]),"optional":dep.get("optional",False),"default_features":dep.get("default-features",True),"target":target,"kind":kind,"registry":None,"explicit_name_in_toml":alias if "package" in dep else None})
        metadata={"name":name,"vers":VERSION,"deps":deps,"features":manifest.get("features",{}),"authors":pkg.get("authors",[]),"description":pkg.get("description"),"documentation":pkg.get("documentation"),"homepage":pkg.get("homepage"),"readme":None,"readme_file":None,"keywords":pkg.get("keywords",[]),"categories":pkg.get("categories",[]),"license":pkg.get("license"),"license_file":pkg.get("license-file"),"repository":pkg.get("repository"),"badges":{},"links":pkg.get("links"),"rust_version":pkg.get("rust-version")}
        owners=json.loads(request("https://crates.io/api/v1/crates/"+name+"/owners"))["users"]
        assert "roryscot" in [x["login"] for x in owners]
        candidates.append((record,data,metadata))
    if not args.execute:
        print(json.dumps({"status":"preflight-passed","archives":proof["archives"],"publication":False},indent=2));return
    credentials=tomllib.loads((Path.home()/".cargo/credentials.toml").read_text())
    token=credentials["registry"]["token"]
    results=[]
    for record,data,meta in candidates:
        name=record["name"]
        url="https://crates.io/api/v1/crates/"+name+"/"+VERSION
        existing=request(url+"?check="+str(time.time()))
        if existing is None:
            encoded=json.dumps(meta,separators=(",",":")).encode()
            response=json.loads(request("https://crates.io/api/v1/crates/new",struct.pack("<I",len(encoded))+encoded+struct.pack("<I",len(data))+data,token))
            assert not response.get("errors"),"Registry rejected upload"
        for attempt in range(30):
            raw=request(url+"?check="+str(time.time()))
            if raw:
                public=json.loads(raw)["version"]
                if public["checksum"]==record["sha256"]:break
            time.sleep(2)
        else:raise RuntimeError("Public version not confirmed; inspect registry before retry")
        assert not public["yanked"] and public["published_by"]["login"]=="roryscot"
        downloaded=request("https://static.crates.io/crates/"+name+"/"+name+"-"+VERSION+".crate")
        assert hashlib.sha256(downloaded).hexdigest()==record["sha256"]
        results.append({**record,"version":VERSION,"publishedBy":"roryscot","createdAt":public["created_at"],"publicDownloadVerified":True})
        (args.evidence/"publication.json").write_text(json.dumps({"packages":results,"status":"passed" if len(results)==len(NAMES) else "partial"},indent=2)+"\n")
        print(name,VERSION,"public checksum and publisher verified",flush=True)
if __name__=="__main__":main()
