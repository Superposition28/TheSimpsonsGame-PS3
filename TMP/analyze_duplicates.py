import json, collections, pathlib, hashlib
p=pathlib.Path('TMP/duplicate-str-audit.json')
a=json.loads(p.read_text())
archives=a['archives']; groups=collections.defaultdict(list); records=[]
for ar in archives:
 groups[(ar['size'],ar['sha256'])].append(ar['archive'])
 for s in ar['sections']:
  for r in s['records']:
   r={'archive':ar['archive'],'section':s['index'],**r}; records.append(r)
assets=[r for r in records if 'payload_sha256' in r]
g=collections.defaultdict(list)
for r in assets:g[(r['payload_size'],r['payload_sha256'])].append(r)
print('archives',len(archives),'errors',len(a['errors']),'unique',len(groups),'duplicate groups',sum(len(v)>1 for v in groups.values()),'redundant',sum(len(v)-1 for v in groups.values()))
for k,v in groups.items():
 if len(v)>1: print('ARCHIVE',k,*v,sep=' | ')
print('records',collections.Counter(r['type'] for r in records),'assets',len(assets),'unique',len(g),'dupe groups',sum(len(v)>1 for v in g.values()),'redundant',sum(len(v)-1 for v in g.values()))
samearch=collections.Counter(); collision=collections.defaultdict(list)
for r in assets: collision[(r['archive'],r['path'].lower())].append(r)
print('path collision groups',sum(len(v)>1 for v in collision.values()),'extra records',sum(len(v)-1 for v in collision.values()),'identical groups',sum(len(v)>1 and len({x['payload_sha256'] for x in v})==1 for v in collision.values()))
for key,v in sorted(collision.items(),key=lambda x:-len(x[1]))[:8]:
 if len(v)>1:print('COLLISION',key,'count',len(v),'hashes',len({x['payload_sha256'] for x in v}),[(x['section'],x['offset'],x['payload_size'],x['payload_sha256'][:12]) for x in v[:8]])
for suffix in ['.lh2','.alb','.smb','.tox.ps3']:
 rows=[r for r in assets if r['path'].lower().endswith(suffix)]; d=collections.defaultdict(list)
 for r in rows:d[(r['payload_size'],r['payload_sha256'])].append(r)
 print('SUFFIX',suffix,len(rows),len(d),'groups',sum(len(v)>1 for v in d.values()),'max',max(map(len,d.values()),default=0))
 for key,v in sorted(d.items(),key=lambda x:-len(x[1]))[:2]:
  print('TOP',key,'count',len(v),[(x['archive'],x['path'],x['section'],x['offset']) for x in v[:4]])
print('TOP ALL')
for key,v in sorted(g.items(),key=lambda x:-len(x[1]))[:10]:print(key,len(v),[(x['archive'],x['path']) for x in v[:3]])
