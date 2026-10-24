"""Clean-install exact alpha.2 archives from a checksum-verified local candidate registry."""
import argparse,hashlib,json,os,shutil,subprocess,tarfile,tomllib,urllib.request
from pathlib import Path,PurePosixPath
FORK="patamaps-icu-collator"
USER_AGENT="patamaps-alpha2-preflight (github.com/roryscot/patamaps)"
def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def slug(name):
    name = name.lower()
    if len(name) <= 2:
        return f'{len(name)}/{name}'
    if len(name) == 3:
        return f'3/{name[0]}/{name}'
    return f'{name[:2]}/{name[2:4]}/{name}'

def download(url, destination, expected=None):
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response, destination.open('xb') as stream:
        shutil.copyfileobj(response, stream)
    if expected:
        assert digest(destination) == expected, f'upstream checksum mismatch: {destination.name}'

def metadata_from_cache(home, package, destination):
    path = slug(package['name'])
    for index in (home / 'registry/index').glob('*'):
        candidate = index / '.cache' / path
        if not candidate.is_file():
            continue
        for part in candidate.read_bytes().split(b'\0'):
            if not part.startswith(b'{'):
                continue
            value = json.loads(part)
            if value.get('vers') == package['version']:
                assert value['cksum'] == package['checksum']
                return value
    temporary = destination / f"{package['name']}-{package['version']}.index-response"
    download('https://index.crates.io/' + path, temporary)
    for line in temporary.read_text().splitlines():
        value = json.loads(line)
        if value['vers'] == package['version']:
            assert value['cksum'] == package['checksum']
            return value
    raise AssertionError(f"locked upstream version absent: {package['name']} {package['version']}")

def index_write(registry, entry):
    path = registry / 'index' / slug(entry['name'])
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        records = [json.loads(line) for line in path.read_text().splitlines()]
        same = [value for value in records if value['vers'] == entry['vers']]
        if same:
            assert same == [entry], f'changed registry entry: {entry["name"]}'
            return
    with path.open('a') as stream:
        stream.write(json.dumps(entry, separators=(',', ':')) + '\n')

def index_entry(manifest, checksum):
    dependencies = []
    groups = [(None, manifest)] + list(manifest.get('target', {}).items())
    for target, group in groups:
        for table, kind in [('dependencies', 'normal'), ('dev-dependencies', 'dev'), ('build-dependencies', 'build')]:
            for alias, value in group.get(table, {}).items():
                value = {'version': value} if isinstance(value, str) else value
                assert 'workspace' not in value and 'path' not in value and 'git' not in value, (alias, value)
                assert value.get('registry') in {None, 'crates-io'}
                dependencies.append({'name': alias, 'req': value['version'],
                                     'features': value.get('features', []),
                                     'optional': value.get('optional', False),
                                     'default_features': value.get('default-features', True),
                                     'target': target, 'kind': kind, 'registry': None,
                                     'package': value.get('package')})
    package = manifest['package']
    return {'name': package['name'], 'vers': package['version'], 'deps': dependencies,
            'cksum': checksum, 'features': {}, 'features2': manifest.get('features', {}),
            'v': 2, 'yanked': False, 'links': package.get('links'),
            'rust_version': package.get('rust-version')}

def inspect_archive(path, name, version, extraction=None):
    assert path.stat().st_size < 10_000_000, f'crate exceeds alpha registry size limit: {name}'
    prefix = f'{name}-{version}'
    members = []
    manifests = {}
    seen = set()
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            assert relative.parts and relative.parts[0] == prefix
            assert not relative.is_absolute() and '..' not in relative.parts
            assert member.name not in seen
            seen.add(member.name)
            assert member.isfile() or member.isdir(), f'nonordinary archive member: {member.name}'
            if member.isdir():
                continue
            tail = PurePosixPath(*relative.parts[1:])
            assert tail.parts
            raw = archive.extractfile(member).read()
            members.append({'path': tail.as_posix(), 'bytes': len(raw),
                            'sha256': hashlib.sha256(raw).hexdigest()})
            if tail.as_posix() == 'Cargo.toml':
                manifests = tomllib.loads(raw.decode())
            if extraction:
                target = extraction.joinpath(*tail.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(raw)
    assert manifests['package']['name'] == name and manifests['package']['version'] == version
    assert set(manifests.get('workspace', {})) <= {'resolver'}
    assert manifests['package']['license'] == ('Unicode-3.0' if name == FORK else 'Apache-2.0')
    assert any(value['path'] == 'LICENSE' for value in members)
    if name != FORK:
        assert any(value['path'] == 'NOTICE' for value in members)
    index_entry(manifests, digest(path))
    return manifests, members

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage",type=Path,required=True)
    args=parser.parse_args()
    stage=args.stage.resolve()
    output=stage/"clean-install"
    output.mkdir(exist_ok=False)
    registry=output/"registry"
    (registry/"index").mkdir(parents=True)
    (registry/"index/config.json").write_text(json.dumps({"dl":registry.as_uri()+"/{crate}-{version}.crate"}))
    original=Path.home()/".cargo"
    for package in tomllib.loads((stage/"Cargo.lock").read_text())["package"]:
        if "source" not in package:continue
        assert package["source"]=="registry+https://github.com/rust-lang/crates.io-index"
        filename=package["name"]+"-"+package["version"]+".crate"
        cached=list((original/"registry/cache").glob("*/"+filename))
        dest=registry/filename
        if cached:
            assert digest(cached[0])==package["checksum"]
            shutil.copyfile(cached[0],dest)
        else:download("https://static.crates.io/crates/"+package["name"]+"/"+filename,dest,package["checksum"])
        index_write(registry,metadata_from_cache(original,package,output))
    archives=[]
    for name in ["patamaps-workspace","patamaps-cli"]:
        archive=stage/"target/package"/(name+"-0.1.0-alpha.2.crate")
        manifest,members=inspect_archive(archive,name,"0.1.0-alpha.2")
        shutil.copyfile(archive,registry/archive.name)
        index_write(registry,index_entry(manifest,digest(archive)))
        archives.append({"name":name,"sha256":digest(archive),"bytes":archive.stat().st_size})
    home=output/"cargo-home"
    home.mkdir()
    (home/"config.toml").write_text('[source.crates-io]\nreplace-with="candidate"\n[source.candidate]\nlocal-registry='+json.dumps(str(registry))+'\n[net]\noffline=true\n')
    env=dict(os.environ,CARGO_HOME=str(home),CARGO_TARGET_DIR=str(output/"target"),CARGO_INCREMENTAL="0",CARGO_PROFILE_DEV_DEBUG="0",PATH=os.environ["PATH"])
    for k in ["CARGO_REGISTRY_TOKEN","CARGO_REGISTRIES_CRATES_IO_TOKEN"]:env.pop(k,None)
    sdk="/Library/Developer/CommandLineTools/SDKs/MacOSX26.5.sdk"
    if Path(sdk).exists():env["SDKROOT"]=sdk
    cmd=["cargo","install","--locked","--offline","--debug","--version","=0.1.0-alpha.2","--root",str(output/"installation"),"patamaps-cli"]
    with (output/"install.log").open("x") as log:
        result=subprocess.run(cmd,cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT)
    receipt={"archives":archives,"command":cmd,"exitCode":result.returncode,"freshCargoHome":True,"registry":"local exact-candidate rehearsal","publicPublication":False}
    if result.returncode==0:
        binary=output/"installation/bin/patamaps"
        receipt["version"]=subprocess.check_output([str(binary),"--version"],env=env,text=True).strip()
        root=Path(__file__).resolve().parents[1]
        subprocess.run([str(binary),"validate",str(root/"fixtures/routing/graph.json"),"--relation-pack",str(root/"relation-packs/routing.json")],env=env,check=True)
        generated=output/"generated.rs"
        subprocess.run([str(binary),"link",str(root/"fixtures/routing/graph.json"),str(root/"fixtures/routing/policy.json"),str(root/"fixtures/routing/projection-spec.json"),"--relation-pack",str(root/"relation-packs/routing.json"),"--as-of","2026-10-24T12:00:00Z","--format","rust","--output",str(generated)],env=env,check=True)
        subprocess.run(["rustc","--edition=2024","--crate-type=lib",str(generated),"-o",str(output/"libconsumer.rlib")],env=env,check=True)
        receipt["generatedRustConsumer"]="passed"
    (output/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    raise SystemExit(result.returncode)
if __name__=="__main__":main()
