"""Read-only PP/SOL inventory. Writes audit artifacts beside this script only.

Uses the shared structural parser; records collisions, not engine-resolved state.
No upstream constructor workflow is run (its editable sibling dependencies are absent).
"""
from pathlib import Path
import collections
import csv
import gzip
import hashlib
import json
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
sys.path.insert(0, str(ROOT / '.eu5-base/ai_gui_assessment/renderer'))
from eu5_gui_renderer.pdx import parse

ROOTS = {
    'sol': ROOT / 'src/stable',
    'standalone': ROOT / 'src/sol_standalone',
    'compat': ROOT / 'src/sol_pp_compatibility_submod',
    'old': ROOT / '.eu5-base/reference_mods/3613232232',
    'pp': ROOT.parent / 'prosper-or-perish-upstream/mod/Prosper or Perish (Population Growth & Food Rework)',
    'seasonal': ROOT.parent / 'prosper-or-perish-upstream/mod/Prosper or Perish Seasonal Harvests',
}
OPS = ('INJECT_OR_CREATE', 'REPLACE_OR_CREATE', 'TRY_INJECT', 'TRY_REPLACE', 'INJECT', 'REPLACE')
def digest(data):
    return hashlib.sha256(data).hexdigest()
def serialize(node):
    return [node.key, node.op, [serialize(x) for x in node.value] if node.is_block() else node.value]
def compact_value(node):
    if not node.is_block():
        return node.value
    value = [serialize(x) for x in node.value]
    encoded = json.dumps(value, sort_keys=True).encode()
    if len(encoded) <= 1800:
        return value
    return {'block_sha256': digest(encoded), 'child_count': len(node.value)}
def db_for(rel):
    parts = rel.split('/')
    if 'common' in parts:
        return parts[parts.index('common') + 1]
    if 'gui' in parts:
        return 'gui'
    if 'map_modes' in parts:
        return 'map_modes'
    if 'events' in parts:
        return 'events'
    return None
def write_csv(name, rows, fields):
    with (OUT / name).open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
def scan(label, root):
    print('Scanning', label, flush=True)
    files, records, locs, errors = {}, [], {}, []
    for path in sorted(root.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        files[rel] = {'sha256': digest(raw), 'bytes': len(raw)}
        if path.suffix == '.yml':
            loc_text = raw.decode('utf-8-sig', errors='replace')
            header = re.search(r'^\s*l_(\w+):', loc_text, re.M)
            lang = header.group(1) if header else ''
            for i, line in enumerate(loc_text.splitlines(), 1):
                m = re.match(r'\s*([^\s:#]+):\d*\s+"(.*)"', line)
                if m:
                    locs.setdefault(lang + ':' + m[1], []).append({'path': rel, 'line': i, 'value': m[2]})
        db = db_for(rel)
        if path.suffix not in ('.txt', '.gui') or not db:
            continue
        try:
            nodes = parse(raw.decode('utf-8-sig'), rel)
        except Exception as e:
            errors.append({'path': rel, 'error': str(e)})
            continue
        if db == 'gui':
            nodes = [child for n in nodes for child in (n.value if n.key.lower() == 'types' and n.is_block() else [n])]
        for n in nodes:
            if not n.op:
                continue
            key, op = n.key, 'DEFINE'
            if ':' in key and key.split(':', 1)[0] in OPS:
                op, key = key.split(':', 1)
            fields = collections.defaultdict(list)
            if n.is_block():
                for child in n.value:
                    fields[child.key].append(compact_value(child))
            records.append({'root': label, 'db': db, 'key': key, 'op': op, 'path': rel, 'line': n.line,
                            'fields': dict(fields), 'body_hash': digest(json.dumps(serialize(n)[2], sort_keys=True).encode())})
    return {'files': files, 'records': records, 'locs': locs, 'errors': errors}
def index(data):
    result = collections.defaultdict(list)
    for row in data['records']:
        result[(row['db'], row['key'])].append(row)
    return result
def main():
    data = {label: scan(label, root) for label, root in ROOTS.items()}
    indexes = {label: index(d) for label, d in data.items()}
    collisions, same_paths, loc_overlaps = [], [], []
    for side in ('sol', 'compat', 'standalone'):
        for k in sorted(indexes[side].keys() & indexes['pp'].keys()):
            a, b = indexes[side][k], indexes['pp'][k]
            collisions.append({'side': side, 'db': k[0], 'key': k[1], 'sol': a, 'pp': b,
                               'shared_fields': sorted(set().union(*(r['fields'] for r in a)) & set().union(*(r['fields'] for r in b)))})
        for p in sorted(data[side]['files'].keys() & data['pp']['files'].keys()):
            same_paths.append({'side': side, 'path': p, 'same_bytes': data[side]['files'][p]['sha256'] == data['pp']['files'][p]['sha256']})
        for k in sorted(data[side]['locs'].keys() & data['pp']['locs'].keys()):
            loc_overlaps.append({'side': side, 'key': k, 'sol': data[side]['locs'][k], 'pp': data['pp']['locs'][k]})
    changes = []
    for p in sorted(data['old']['files'].keys() | data['pp']['files'].keys()):
        old, new = data['old']['files'].get(p), data['pp']['files'].get(p)
        state = 'added' if old is None else 'removed' if new is None else 'unchanged' if old['sha256'] == new['sha256'] else 'changed'
        changes.append({'state': state, 'path': p})
    symbol_changes = []
    for k in sorted(indexes['old'].keys() | indexes['pp'].keys()):
        old, new = indexes['old'].get(k), indexes['pp'].get(k)
        state = 'added' if old is None else 'removed' if new is None else 'unchanged' if [(r['op'],r['body_hash']) for r in old] == [(r['op'],r['body_hash']) for r in new] else 'changed'
        symbol_changes.append({'state': state, 'db': k[0], 'key': k[1], 'old': old, 'pp': new})
    report = {'roots': {k: str(v) for k,v in ROOTS.items()}, 'data': data, 'collisions': collisions,
              'same_paths': same_paths, 'localization_overlaps': loc_overlaps, 'file_changes': changes, 'symbol_changes': symbol_changes}
    with gzip.open(OUT / 'inventory.json.gz', 'wt', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, separators=(',', ':'))
    write_csv('same_paths.csv', same_paths, ['side','path','same_bytes'])
    write_csv('file_changes.csv', changes, ['state','path'])
    write_csv('symbol_changes.csv', symbol_changes, ['state','db','key'])
    write_csv('object_collisions.csv', [{'side': r['side'], 'db': r['db'], 'key': r['key'], 'shared_fields': ';'.join(r['shared_fields']),
              'sol': ';'.join(f"{x['op']} {x['path']}:{x['line']}" for x in r['sol']),
              'pp': ';'.join(f"{x['op']} {x['path']}:{x['line']}" for x in r['pp'])} for r in collisions], ['side','db','key','shared_fields','sol','pp'])
    summary = {'roots': {label: {'files': len(d['files']), 'objects': len(d['records']), 'errors': d['errors']} for label,d in data.items()},
               'file_delta': dict(collections.Counter(r['state'] for r in changes)),
               'collision_counts': {side: dict(collections.Counter(r['db'] for r in collisions if r['side']==side)) for side in ('sol','compat','standalone')},
               'same_paths': same_paths, 'loc_overlaps': len(loc_overlaps)}
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
if __name__ == '__main__':
    main()
