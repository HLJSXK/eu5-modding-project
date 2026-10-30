"""Inventory required CMF and optional UI/seasonal surfaces against PP."""
import gzip
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scan import OUT, ROOT, scan, index
with gzip.open(OUT / 'inventory.json.gz', 'rt', encoding='utf-8') as f:
    base = json.load(f)
pp_index = index(base['data']['pp'])
rows, paths, summaries = [], [], {}
for name, folder in [('cmf','3692202776'), ('glorp','3812518640'), ('construction_manager','3736668860')]:
    data = scan(name, ROOT / '.eu5-base/reference_mods' / folder)
    ix = index(data)
    summaries[name] = {'files':len(data['files']), 'errors':data['errors']}
    for db,key in sorted(ix.keys() & pp_index.keys()):
        if db == 'events' and key == 'namespace':
            continue
        rows.append({'dependency':name,'db':db,'key':key,'dependency_defs':ix[(db,key)],'pp_defs':pp_index[(db,key)]})
    for path in sorted(data['files'].keys() & base['data']['pp']['files'].keys()):
        if path.startswith('.metadata/'):
            continue
        paths.append({'dependency':name, 'path':path, 'same_bytes':data['files'][path]['sha256']==base['data']['pp']['files'][path]['sha256']})
seasonal = []
for path,info in base['data']['seasonal']['files'].items():
    other = base['data']['pp']['files'].get(path)
    if not other or other['sha256'] != info['sha256']:
        seasonal.append({'path':path,'state':'different' if other else 'only_in_seasonal'})
result={'roots':summaries, 'same_paths':paths, 'candidates':rows, 'seasonal_differences':seasonal}
with gzip.open(OUT/'dependencies.json.gz','wt',encoding='utf-8') as f:
    json.dump(result,f,ensure_ascii=False,separators=(',',':'))
print(json.dumps({'roots':summaries,'same_paths':paths,'candidate_counts':{k:sum(r['dependency']==k for r in rows) for k in summaries},'seasonal_differences':seasonal},ensure_ascii=False,indent=2))
