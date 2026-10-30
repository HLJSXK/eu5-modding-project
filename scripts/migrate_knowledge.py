from pathlib import Path
import yaml,re,shutil
ROOT=Path(__file__).resolve().parents[1]; BASE=ROOT.parent/'eu5-modding-base'; SOL=ROOT; TV=ROOT.parent/'eu5-towards-victory'; OUT=ROOT/'tmp'/'knowledge_migration'; OUT.mkdir(parents=True,exist_ok=True)
def entries(root):
    snapshot=OUT/'base/docs/knowledge/MIGRATION_COVERAGE.yaml'
    if snapshot.exists():
        recorded=yaml.safe_load(snapshot.read_text(encoding='utf-8'))['entries']
        return [x['entry'] for x in recorded if x['source_project']==root.name]
    return [x for x in (yaml.safe_load((root/'docs/knowledge/anti_patterns.yaml').read_text(encoding='utf-8')) or []) if isinstance(x,dict) and x.get('id')]
A=entries(SOL); B=entries(TV)
sol_local_prefixes=('sol_','country_solver','country_substitution','substitution_','commodity_offset','capacity_floor','reduced_frequency','monthly_savings','yearly_january','empty_sol','pop_demand_','pop_needs_','solver_entry','retired_solver','gui_goods_tooltip_market_extension','gui_price_tier_selection','gui_substitution_','gui_missing_market_weight','gui_diagnostics_must','gui_fixed_group_row_overflows_with_compat_goods','requested_modifier_size')
tv_local_prefixes=('tv_','wonder_','io_','trade_league','philosophy_debate','unique_wonder','engineering_','court_','ceremony_','ritual_','unreleased_project','monthly_country_pulse_callback','mod_io_','mechanic_similarity_audit','noncapital_building_country_effects_via_capital_country_modifier','generated_static_modifier_key_flood_collision_risk')
project_markers=('src/','src_','scripts/','scripts_','data/','docs/error_log','runtime error','runtime observation','user error','user-reported','project owner','Towards Victory','SOL_','TV_','tv_','towards_victory','wonder','Wonder','trade_league','philosophy_debate','unique_wonder','engineering department')
sol_extra={'gui_weight_is_not_a_percentage'};tv_extra={'artist_selector_should_use_artist_column'}
force_local_ids={'cmm_default_off_alias_initialized','gui_blockoverride_cannot_parameterize_siblings','random_list_branch_modifier_filter','variable_map_callback_root_in_generic_action'}
def _text(e): return ' '.join(str(e.get(k,'')) for k in ('id','only_in_paths','bad','correction','source','notes'))
def sl(e):return e['id'].startswith(sol_local_prefixes) or e['id'] in sol_extra or any(m in _text(e) for m in project_markers)
def tl(e):return e['id'].startswith(tv_local_prefixes) or e['id'] in tv_extra or any(m in _text(e) for m in project_markers)
local_ids={e['id'] for e in A if sl(e)} | {e['id'] for e in B if tl(e)} | force_local_ids
base={e['id']:e for e in A if e['id'] not in local_ids}
for e in B:
 if e['id'] not in local_ids:base.setdefault(e['id'],e)
for e in B:
 if e['id'] in {'location_rank_invalid_hamlet','location_rank_invalid_metropolis','location_rank_invalid_village'}:base[e['id']]=e
for e in A:
 if e['id']=='location_auto_modifier_nonfunctional' and e['id'] in base:
  x=dict(base[e['id']]);x['correction']='Use main_menu/common/static_modifiers/: define new objects with game_data.category = location, or use a minimal TRY_INJECT delta when modifying an existing object.';x['source_variants']=[{'project':'eu5-modding-project','correction':e.get('correction'),'source':e.get('source')},{'project':'eu5-towards-victory','correction':base[e['id']].get('correction'),'source':base[e['id']].get('source')}];base[e['id']]=x
for project,es in [('eu5-modding-project',A),('eu5-towards-victory',B)]:
 for e in es:
  if e['id'] in base:
   oth=next((z for z in (B if project=='eu5-modding-project' else A) if z['id']==e['id']),None)
   if oth is not None and oth!=e:
    vs=base[e['id']].setdefault('source_variants',[])
    if not any(v.get('project')==project for v in vs):vs.append({'project':project,'entry':e})
base_entries=sorted(base.values(),key=lambda e:e['id']);sol_local=sorted([e for e in A if e['id'] not in base],key=lambda e:e['id']);tv_local=sorted([e for e in B if e['id'] not in base],key=lambda e:e['id'])
def dump(path,obj,header=''):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(header+yaml.safe_dump(obj,sort_keys=False,allow_unicode=True,width=120),encoding='utf-8')
dump(OUT/'base/docs/knowledge/anti_patterns.yaml',base_entries,'# Reusable EU5 engine/tooling anti-patterns. Project-specific rules stay in each workspace.\n')
dump(OUT/'sol/docs/knowledge/anti_patterns.yaml',sol_local,'# SOL project-specific anti-patterns; reusable entries are loaded from .eu5-base/docs/knowledge/anti_patterns.yaml.\n')
dump(OUT/'tv/docs/knowledge/anti_patterns.yaml',tv_local,'# Towards Victory project-specific anti-patterns; reusable entries are loaded from .eu5-base/docs/knowledge/anti_patterns.yaml.\n')
manifest={'schema_version':1,'description':'Complete source snapshots and migration destinations for every original anti-pattern entry.','entries':[]}
for project,es in [('eu5-modding-project',A),('eu5-towards-victory',B)]:
 for e in es:manifest['entries'].append({'source_project':project,'id':e['id'],'destination':'base' if e['id'] in base else 'local','destination_path':'.eu5-base/docs/knowledge/anti_patterns.yaml' if e['id'] in base else 'docs/knowledge/anti_patterns.yaml','entry':e})
dump(OUT/'base/docs/knowledge/MIGRATION_COVERAGE.yaml',manifest)
base_enum={'location_rank':{'values':['rural_settlement','town','city','megalopolis'],'source':'.eu5-base/reference_game_files/game/in_game/common/location_ranks/00_default.txt','notes':'Current EU5 1.x values.'},'government_type':{'values':['monarchy','republic','theocracy','tribe','steppe_horde'],'source':'.eu5-base/reference_game_files/game/in_game/common/government_types/00_default.txt','notes':'Exact government type IDs.'}}
dump(OUT/'base/docs/knowledge/valid_enums.yaml',base_enum,'# Reusable EU5 enum whitelist.\n');dump(OUT/'sol/docs/knowledge/valid_enums.yaml',{},'# Project additions merge with .eu5-base/docs/knowledge/valid_enums.yaml.\n');dump(OUT/'tv/docs/knowledge/valid_enums.yaml',{},'# Project additions merge with .eu5-base/docs/knowledge/valid_enums.yaml.\n')
# cards and gameplay copies (never delete source in migration generator)
for n in ['generic_actions.md','events.md','gui.md','localization.md','on_action.md','object_on_built.md','europedia.md']:
 p=TV/'docs/knowledge/risk_cards'/n
 if p.exists(): (OUT/'base/docs/knowledge/risk_cards'/n).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,OUT/'base/docs/knowledge/risk_cards'/n)
for p in sorted((TV/'docs/knowledge/gameplay').glob('*.md')):
 (OUT/'base/docs/knowledge/gameplay'/p.name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,OUT/'base/docs/knowledge/gameplay'/p.name)
ref=(TV/'docs/knowledge/EU5_Gameplay_Reference.md').read_text(encoding='utf-8');ls=ref.splitlines(True);st=next((i for i,l in enumerate(ls) if l.startswith('## 14.')),None);en=next((i for i,l in enumerate(ls) if st is not None and i>st and l.startswith('## 15.')),None)
if st is not None and en is not None:
 generic=''.join(ls[:st])+'## 14. Project application\n\nProject-specific application notes stay in the workspace-local reference.\n\n'+''.join(ls[en:]);local='# EU5 玩法参考：Towards Victory application notes\n\nRead `.eu5-base/docs/knowledge/EU5_Gameplay_Reference.md` first.\n\n'+''.join(ls[st:])
else:generic=ref;local='# Read `.eu5-base/docs/knowledge/EU5_Gameplay_Reference.md` first.\n\n'+ref
(OUT/'base/docs/knowledge/EU5_Gameplay_Reference.md').parent.mkdir(parents=True,exist_ok=True);(OUT/'base/docs/knowledge/EU5_Gameplay_Reference.md').write_text(generic,encoding='utf-8');(OUT/'tv/docs/knowledge/EU5_Gameplay_Reference.md').write_text(local,encoding='utf-8')
print('base',len(base_entries),'sol_local',len(sol_local),'tv_local',len(tv_local),'manifest',len(manifest['entries']))
