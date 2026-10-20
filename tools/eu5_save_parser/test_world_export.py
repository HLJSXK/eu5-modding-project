"""Formal world exports use saved merchant power, not commodity trade."""
import csv
import json
from pathlib import Path

from .test_parser import SYNTHETIC_SAVE
from .world_export import export_world,upgrade_world
from .parser import parse_save,export_analysis
from copy import deepcopy


def test_world_snapshot_exports_population_roads_merchants_and_extended_locations(tmp_path):
    text=SYNTHETIC_SAVE.replace('\tdate=1337.6.2.16','\tdate=1337.6.2.16\n\tplaythrough_id="fixture"')
    text=text.replace('\tcountry_name="Hungary"','\tcountry_name="Hungary"\n\tcapital=1')
    text=text.replace('\t\t\tcontrol=1','\t\t\tcontrol=1\n\t\t\tculture=hungarian\n\t\t\treligion=catholic\n\t\t\tproximity=0.9\n\t\t\tmarket_access=0.8\n\t\t\troad_to_capital=yes\n\t\t\tinstitutions={\n\t\t\t\trenaissance=25\n\t\t\t}')
    text+='''
market_manager={
\tdatabase={
7={
\tcenter=1
\tmerchant={
\t\tcountry=1
\t\tpower=30
\t}
\tmerchant={
\t\tcountry=2
\t\tpower=10
\t}
}
\t}
}
road_network={
\troads={{
\t\tfrom=1
\t\tto=2
\t\ttype=paved_road
\t}}
}
'''
    save=tmp_path/'fixture.eu5';save.write_text(text,encoding='utf-8')
    out=tmp_path/'world.json';result=export_world(save,out)
    assert result['locations']['alpha']['population']==10
    assert result['locations']['alpha']['road_to_capital'] is True
    assert result['locations']['alpha']['institutions']=={'renaissance':25}
    assert result['locations']['alpha']['culture']=='hungarian'
    assert result['markets']['7']['merchants']=={'1':.75,'2':.25}
    assert result['countries']['1']['capital']=='alpha'
    assert result['roads']==[['alpha','beta','paved_road']]
    assert 'trades' not in result and 'goods' not in result['markets']['7']
    assert len(result['source']['sha256'])==64
    assert list(csv.DictReader(out.with_suffix('.roads.csv').open()))==[{'from':'alpha','to':'beta','type':'paved_road'}]


def test_runtime_identity_refs_and_primary_country_faith_are_decoded(tmp_path):
    text=SYNTHETIC_SAVE.replace('\tcountry_name="Hungary"','\tcountry_name="Hungary"\n\tcapital=1\n\tprimary_culture=10\n\tprimary_religion=20')
    text=text.replace('\t\t\tcontrol=1','\t\t\tcontrol=1\n\t\t\tculture=10\n\t\t\treligion=20')
    text+='''
culture_manager={
\tdatabase={
10={
\tname="Hungarian"
\tculture_definition=hungarian_culture
}
\t}
}
religion_manager={
\tdatabase={
20={
\tname="Catholic"
\tdefinition=catholic
\tgroup=christian
}
\t}
}
market_manager={
\tdatabase={
7={
\tcenter=1
}
\t}
}
road_network={
}
'''
    save=tmp_path/'ids.eu5';save.write_text(text,encoding='utf-8')
    out=tmp_path/'world.json';world=export_world(save,out)
    assert world['locations']['alpha']['culture']=='hungarian_culture'
    assert world['locations']['alpha']['religion']=='catholic'
    assert world['locations']['alpha']['religion_instance']=='20'
    assert world['countries']['1']['religion_group']=='christian'
    assert world['countries']['1']['culture']=='hungarian_culture'
    parsed=parse_save(save)
    assert parsed.religion_names['20']=='catholic'
    assert parsed.culture_names['10']=='hungarian_culture'
    old=deepcopy(world);old['format']='obsession.world-snapshot/1'
    for loc in old['locations'].values():
        loc['culture']=loc['culture_instance'];loc['religion']=loc['religion_instance']
    assert upgrade_world(save,old,out)==world
