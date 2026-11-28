import hashlib,json,re,shlex,shutil,sys
from pathlib import Path
def pairs(values):
 d={}
 for k,v in values:
  if k in d:raise ValueError('DUPLICATE_CONFIG_KEY')
  d[k]=v
 return d
cfg=json.loads(Path('service.json').read_text(),object_pairs_hook=pairs)
if set(cfg)!=set(['schemaVersion','nonsecret','target','bind','port','routePrefix','documentRoot']):raise ValueError('SERVICE_CONFIG_KEYS')
if cfg['schemaVersion']!='miniserve-qualified-1' or cfg['nonsecret'] is not True or cfg['target']!='linux/amd64':raise ValueError('SERVICE_CONFIG_PROFILE')
if cfg['bind']!='127.0.0.1' or type(cfg['port'])!=int or not 1024<=cfg['port']<=65535:raise ValueError('SERVICE_CONFIG_LISTENER')
if cfg['routePrefix']!='/qualified' or cfg['documentRoot']!='public':raise ValueError('SERVICE_CONFIG_PATH')
argv=['env','-i','PATH=/usr/bin:/bin','LANG=C','./miniserve','public','--interfaces',cfg['bind'],'--port',str(cfg['port']),'--workers','1','--route-prefix',cfg['routePrefix'],'--no-symlinks','--quiet']
launch='#!/bin/bash\nset -euo pipefail\ncd "$(dirname "$0")"\nexec '+shlex.join(argv)+'\n'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
proof=dict(profile='miniserve-config-projection-1',configuration=cfg,configurationDigest=sha(Path('service.json')),runtimeDigest=sha(Path('runtime')),documentDigest=sha(Path('public/status.txt')),probeDigest=sha(Path('probe.sh')))
bundle=Path('bundle')
if '--verify' in sys.argv:
 assert (bundle/'launch.sh').read_text()==launch
 assert json.loads((bundle/'configuration.json').read_text())==proof
 assert sha(bundle/'miniserve')==sha(Path('runtime'))
 assert sha(bundle/'public/status.txt')==sha(Path('public/status.txt'))
 assert sha(bundle/'probe.sh')==sha(Path('probe.sh'))
 assert (bundle/'miniserve').stat().st_mode & 0o777==0o755
 print('verified-exact-service-config-and-bundle')
else:
 bundle.mkdir();(bundle/'public').mkdir()
 for src,dst,mode in [(Path('runtime'),bundle/'miniserve',0o755),(Path('public/status.txt'),bundle/'public/status.txt',0o644),(Path('probe.sh'),bundle/'probe.sh',0o644)]:
  shutil.copyfile(src,dst);dst.chmod(mode)
 (bundle/'launch.sh').write_text(launch);(bundle/'launch.sh').chmod(0o755)
 (bundle/'configuration.json').write_text(json.dumps(proof,sort_keys=True)+'\n');(bundle/'configuration.json').chmod(0o644)
 print('prepared-declared-service-bundle')
