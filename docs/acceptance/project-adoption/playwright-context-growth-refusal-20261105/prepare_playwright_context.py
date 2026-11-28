from pathlib import Path
import json,os,stat,hashlib
def materialize(B,F):
 base=Path(F['baseFilteredSnapshot']);full=Path(F['originalSnapshot']);dest=Path(F['filteredSnapshot'])
 m=json.loads((B/'repaired-context-manifest.json').read_text());d=json.loads((B/'repaired-context-definition.json').read_text())
 baseEntries=json.loads((base/'manifest.json').read_text())['entries'];original=json.loads((full/'manifest.json').read_text())['entries']
 assert m['digest']==F['filteredContextDigest']and set(m['entries'])==set(d['paths'])
 assert all(m['entries'][n]==row for n,row in baseEntries.items())
 additions=set(m['entries'])-set(baseEntries);assert len(additions)==F['addedContextEntries']
 assert all(m['entries'][n]==original[n]for n in additions)
 dest.mkdir(mode=0o700);data=dest/'data';data.mkdir(mode=0o700)
 for leaf,name in [('manifest.json','repaired-context-manifest.json'),('selection.json','repaired-context-definition.json')]:
  with(dest/leaf).open('xb')as out:
   os.fchmod(out.fileno(),0o600);out.write((B/name).read_bytes())
 roots=[os.open(p/'data',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)for p in[base,full]]
 linked=0;linkedNew=0
 try:
  for name,row in sorted(m['entries'].items(),key=lambda item:(item[0].count('/'),item[0])):
   parts=name.split('/');assert all(x not in['','.','..']for x in parts)
   target=data/name
   if row['kind']=='directory':target.mkdir(mode=0o700);continue
   if row['kind']=='symlink':continue # Manifest-only, as in native storage.
   assert row['kind']=='file'
   parent=os.dup(roots[name in additions])
   try:
    for part in parts[:-1]:
     nextfd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);os.close(parent);parent=nextfd
    leaf=parts[-1];before=os.stat(leaf,dir_fd=parent,follow_symlinks=False)
    assert stat.S_ISREG(before.st_mode)and stat.S_IMODE(before.st_mode)==0o600 and before.st_uid==os.getuid()and before.st_size==row['byteLength']
    os.link(leaf,target,src_dir_fd=parent,follow_symlinks=False)
    after=target.lstat()
    assert stat.S_ISREG(after.st_mode)and (after.st_dev,after.st_ino,after.st_size,after.st_mode,after.st_uid)==(before.st_dev,before.st_ino,before.st_size,before.st_mode,before.st_uid)
    linked+=1;linkedNew+=name in additions
   finally:os.close(parent)
 finally:
  for fd in roots:os.close(fd)
 return dict(entries=len(m['entries']),hardlinkedSealedFiles=linked,addedOriginalFiles=linkedNew,sourceFileBytesOrModesWritten=False,snapshotStorageOnly=True,stageCandidateMustBeIndependent=True)
