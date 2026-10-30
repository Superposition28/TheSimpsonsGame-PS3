from pathlib import Path
import hashlib,collections
root=Path('Source/PS3/EU/1/PS3_GAME')
paths=list(root.rglob('*.str')); sizes=collections.Counter(p.stat().st_size for p in paths); groups=collections.defaultdict(list)
for p in paths:
 if sizes[p.stat().st_size]>1:
  with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
  groups[(p.stat().st_size,h)].append(p.relative_to(root).as_posix())
print('archives',len(paths),'bytes',sum(p.stat().st_size for p in paths))
for (size,h),v in groups.items():
 if len(v)>1: print('GROUP',size,h,len(v),*v,sep=' | ')
