import socket,http.client,json,sys
class UnixHTTP(http.client.HTTPConnection):
 def connect(self):
  self.sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
  self.sock.settimeout(4)
  self.sock.connect('/Users/admin/.docker/run/docker.sock')
c=UnixHTTP('localhost',timeout=4)
c.request('GET','/system/df')
response=c.getresponse()
raw=response.read(4*1024*1024+1)
c.close()
if response.status!=200 or len(raw)>4*1024*1024:raise RuntimeError('Docker accounting unavailable')
# Raw Docker metadata never leaves this process. Node validates the selected result.
document=json.loads(raw)
volumes=document.get('Volumes')
if not isinstance(volumes,list):raise RuntimeError('Incomplete Docker volume inventory')
project=sys.argv[1];selected=[]
for volume in volumes:
 labels=volume.get('Labels') or {}
 if labels.get('buildctl.project')==project:
  selected.append(dict(Name=volume.get('Name'),Labels={'buildctl.project':project},UsageData=volume.get('UsageData')))
print(json.dumps({'Volumes':selected},separators=(',',':')))
