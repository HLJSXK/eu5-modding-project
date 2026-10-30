"""Current marriage/alliance supplements for immutable /2 world snapshots.

Only active diplomacy_manager records are read. Peace offers, opinion lists,
trade quantities and inferred friendships are not diplomatic connections.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mmap
from pathlib import Path
import re
import sys

if hasattr(sys.stdout,"reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8",errors="replace")

from .world_export import atomic_json,digest

FORMAT='obsession.world-relations/1'
ROOT=re.compile(rb'(?m)^diplomacy_manager[ \t]*=[ \t]*\{')
NEXT_ROOT=re.compile(rb'(?m)^[a-zA-Z_][a-zA-Z0-9_]*[ \t]*=[ \t]*\{')
RECORD=re.compile(rb'(?m)^\t(royal_marriage|scripted_mutual|alliance)[ \t]*=[ \t]*\{')
END_RECORD=re.compile(rb'(?m)^\t\}')


def date_key(value):
    return tuple(map(int,value.split('.')))


def extract_current_relations(raw,date):
    root=ROOT.search(raw)
    if root is None:
        return {'complete':False,'reason':'diplomacy_manager absent','relations':[]}
    following=NEXT_ROOT.search(raw,root.end())
    end=following.start() if following else len(raw)
    relations={}
    for match in RECORD.finditer(raw,root.end(),end):
        close=END_RECORD.search(raw,match.end(),end)
        if close is None:
            raise ValueError('unclosed active diplomatic relationship')
        body=raw[match.end():close.start()]
        relation_type=match.group(1).decode('ascii')
        if relation_type=='scripted_mutual':
            if not re.search(rb'\bobject[ \t]*=[ \t]*alliance\b',body):
                continue
            relation_type='alliance'
        first=re.search(rb'\bfirst[ \t]*=[ \t]*(\d+)\b',body)
        second=re.search(rb'\bsecond[ \t]*=[ \t]*(\d+)\b',body)
        if first is None or second is None:
            raise ValueError('diplomatic relationship lacks country endpoints')
        ended=re.search(rb'\bend_date[ \t]*=[ \t]*(\d+\.\d+\.\d+)\b',body)
        if ended and date_key(ended.group(1).decode())[0]>0 and date_key(ended.group(1).decode())<=date_key(date):
            continue
        a,b=sorted((first.group(1).decode(),second.group(1).decode()))
        if a==b:
            continue
        kind='marriage' if relation_type=='royal_marriage' else 'diplomacy'
        start=re.search(rb'\bstart_date[ \t]*=[ \t]*(\d+\.\d+\.\d+)\b',body)
        relations[kind,a,b]={'kind':kind,'relation_type':relation_type,'first':a,'second':b,
            'start_date':start.group(1).decode() if start else None}
    return {'complete':True,'relations':[relations[k] for k in sorted(relations)]}


def safe_child(root,name):
    target=(root/name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError('relationship path escapes its world directory')
    return target


def archive_relationships(archive,worlds,progress=print):
    updated=[]
    for manifest_path in sorted(Path(worlds).glob('*/timeline.json')):
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('kind')!='O':
            continue
        folder=manifest_path.parent
        for entry in manifest['snapshots']:
            snapshot_path=safe_child(folder,entry['file'])
            raw_snapshot=snapshot_path.read_bytes()
            if hashlib.sha256(raw_snapshot).hexdigest()!=entry['sha256']:
                raise ValueError('world snapshot changed before relationship export')
            snapshot=json.loads(raw_snapshot)
            if snapshot['metadata']['date']!=entry['date'] or snapshot['metadata']['playthrough_id']!=manifest['id']:
                raise ValueError('mixed relationship world/date')
            source=snapshot['source']
            source_root=Path(archive)/manifest['id']
            source_path=safe_child(source_root,source['name'])
            stat=source_path.stat()
            if stat.st_size!=source['size'] or stat.st_mtime_ns!=source['mtime_ns']:
                raise ValueError('original save changed after world export: '+source_path.name)
            relative='relations/'+snapshot_path.stem+'.json'
            target=safe_child(folder,relative)
            data=json.loads(target.read_text(encoding='utf-8')) if target.exists() else None
            reusable=(data is not None and data.get('format')==FORMAT and data.get('world_snapshot_sha256')==entry['sha256']
                      and data.get('source_sha256')==source['sha256'] and data.get('date')==entry['date']
                      and data.get('playthrough_id')==manifest['id'])
            if not reusable:
                progress('Relations '+source_path.name,flush=True)
                with source_path.open('rb') as stream,mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as raw:
                    if hashlib.sha256(raw).hexdigest()!=source['sha256']:
                        raise ValueError('original save hash mismatch: '+source_path.name)
                    data=extract_current_relations(raw,entry['date'])
                countries=snapshot['countries']
                original=len(data['relations'])
                data['relations']=[r for r in data['relations'] if r['first'] in countries and r['second'] in countries]
                data.update(format=FORMAT,date=entry['date'],playthrough_id=manifest['id'],
                    source_sha256=source['sha256'],world_snapshot_sha256=entry['sha256'],
                    discarded_absent_countries=original-len(data['relations']))
                atomic_json(target,data)
            entry.update(relations_file=relative,relations_sha256=digest(target),relations_complete=data['complete'])
            manifest['relations_complete']=all(e.get('relations_complete') is True for e in manifest['snapshots'])
            atomic_json(manifest_path,manifest)
        updated.append(str(manifest_path))
    return updated


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive',type=Path,default=Path('data/saves/observer_archive'))
    ap.add_argument('--worlds',type=Path,default=Path('tmp/obsession_worlds'))
    args=ap.parse_args(argv)
    archive_relationships(args.archive,args.worlds)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
