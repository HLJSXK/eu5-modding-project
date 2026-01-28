tags = {
    'POR': 'Portuguese',
    'CAS': 'Castillian',
    'SPA': 'Spanish',
    'FRA': 'French',
    'ENG': 'English',
    'GBR': 'British',
    'NED': 'Dutch',
}

cons = '''text = {{
    localization_key = country_name_construction_{tag_lower}_colony
    trigger = {{
        is_subject_type = colonial_nation
        overlord = {{ tag = {tag} }}
    }}
}}'''

loc = '''  country_name_construction_{tag_lower}_colony: "$PREFIX$ of {adjective} $NAME$"
  country_name_construction_{tag_lower}_colony_map: "$NAME$"'''

print('\nLOCALIZATION KEYS:')
for tag, adj in tags.items():
    print(cons.format(tag_lower=tag.lower(), tag=tag))
print('\nLOCALIZATION:')
for tag, adj in tags.items():
    print(loc.format(tag_lower=tag.lower(), tag=tag, adjective=adj))
