import json
from pathlib import Path

from .relationships_export import extract_current_relations,archive_relationships
from .world_export import digest,atomic_json


TEXT=b'''peace_offers={
\t0={
\t\troyal_marriage={ first=9 second=8 }
\t}
}
diplomacy_manager={
0={ diplomats=1 }
\troyal_marriage={
\t\tfirst=2
\t\tsecond=3
\t\tstart_date=1337.4.1
\t}
\tscripted_mutual={
\t\tfirst=4
\t\tsecond=2
\t\tnamed_targets={ { flag="scripted_relation_type" target={ type=relation_type object=alliance } } }
\t}
\tscripted_mutual={
\t\tfirst=4
\t\tsecond=3
\t\tnamed_targets={ { target={ object=coalition } } }
\t}
\troyal_marriage={
\t\tfirst=9
\t\tsecond=2
\t\tend_date=1337.1.1
\t}
}
another_manager={
\troyal_marriage={ first=7 second=8 }
}
'''


def test_only_active_marriages_and_actual_alliances_are_exported():
    result=extract_current_relations(TEXT,'1338.4.1')
    assert result['complete']
    assert {(r['kind'],r['first'],r['second']) for r in result['relations']}=={
        ('marriage','2','3'),('diplomacy','2','4')}
    assert not extract_current_relations(b'other_manager={ }','1338.4.1')['complete']


def test_supplements_resume_without_touching_world_snapshots_or_original_saves(tmp_path):
    archive=tmp_path/'archive';worlds=tmp_path/'worlds'
    raw=archive/'test'/'sample.eu5';raw.parent.mkdir(parents=True);raw.write_bytes(TEXT)
    folder=worlds/'test';folder.mkdir(parents=True)
    source={'name':raw.name,'sha256':digest(raw),'size':raw.stat().st_size,'mtime_ns':raw.stat().st_mtime_ns}
    snapshot=folder/'sample.json'
    atomic_json(snapshot,{'format':'obsession.world-snapshot/2','metadata':{'date':'1338.4.1','playthrough_id':'test'},
                          'countries':{'2':{},'3':{},'4':{}},'source':source})
    before=snapshot.read_bytes();original=raw.read_bytes()
    atomic_json(folder/'timeline.json',{'format':'obsession.world-timeline/1','kind':'O','id':'test',
        'role':'independent_validation','snapshots':[{'file':snapshot.name,'date':'1338.4.1','sha256':digest(snapshot)}]})
    log=lambda *args,**kwargs:None
    archive_relationships(archive,worlds,log)
    first=(folder/'timeline.json').read_bytes()
    archive_relationships(archive,worlds,log)
    manifest=json.loads(first);entry=manifest['snapshots'][0]
    assert manifest['relations_complete'] and manifest['role']=='independent_validation'
    assert (folder/'timeline.json').read_bytes()==first
    assert raw.read_bytes()==original and snapshot.read_bytes()==before
    assert entry['relations_sha256']==digest(folder/entry['relations_file'])
