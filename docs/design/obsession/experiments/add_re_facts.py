"""Append the 2026-10-22 re_ (Indian Ocean / East Asia residency) group and
the Formosa ownership records to world_facts.json.

Inclusion rule: 24 §1 R1 unchanged (institutionally recognised foreign merchant
community, >=10 years, any nationality). Loose compilation at user request:
sources are standard reference works; some URLs are general topic pages.
"""
import json, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = Path(sys.argv[1])
data = json.loads(PATH.read_text(encoding="utf-8"))

EIC = "Encyclopaedia Britannica, 'East India Company'; https://www.britannica.com/topic/East-India-Company"
VOC = "Encyclopaedia Britannica, 'Dutch East India Company'; https://www.britannica.com/topic/Dutch-East-India-Company"
MOCHA = "Encyclopaedia Britannica, 'Mokha (Mocha)' (factories of the English and Dutch East India Companies); https://www.britannica.com/place/Mocha-Yemen ; Nancy Um, The Merchant Houses of Mocha (University of Washington Press, 2009), ch. 1"
PRAKASH = "Om Prakash, European Commercial Enterprise in Pre-Colonial India (New Cambridge History of India II.5, Cambridge UP, 1998), ch. 3-4"
CANTON = "Encyclopaedia Britannica, 'Canton system' (British, Dutch, French, American, Swedish, Danish factories); https://www.britannica.com/event/Canton-system ; Paul A. Van Dyke, The Canton Trade: Life and Enterprise on the China Coast, 1700-1845 (Hong Kong UP, 2005), ch. 1"
AYU = "UNESCO World Heritage Centre, 'Historic City of Ayutthaya' (foreign settlements); https://whc.unesco.org/en/list/576/"
MELAKA = "UNESCO World Heritage Centre, 'Melaka and George Town, Historic Cities of the Straits of Malacca'; https://whc.unesco.org/en/list/1223/"
MANILA = "Ryan Dominic Crewe, 'Pacific Purgatory: Spanish Dominicans, Chinese Sangleys, and the Entanglement of Mission and Commerce in Manila, 1580-1620', Journal of Early Modern History 19:4 (2015); https://brill.com/view/journals/jemh/19/4/article-p337_3.xml"
BATAVIA = "Leonard Blusse, Strange Company: Chinese Settlers, Mestizo Women and the Dutch in VOC Batavia (Foris, 1986), ch. 4; Encyclopaedia Britannica, 'Jakarta'; https://www.britannica.com/place/Jakarta"
MACAU = "Encyclopaedia Britannica, 'Macau' (Portuguese settlement from 1557); https://www.britannica.com/place/Macau ; C. R. Boxer, The Great Ship from Amacon (1959), introduction"
JAPAN = "C. R. Boxer, The Christian Century in Japan 1549-1650 (University of California Press, 1951), ch. 3 and 9; Encyclopaedia Britannica, 'Nagasaki'; https://www.britannica.com/place/Nagasaki-Japan"
KYAKHTA = "Encyclopaedia Britannica, 'Treaty of Kyakhta'; https://www.britannica.com/topic/Treaty-of-Kyakhta ; Oxford Research Encyclopedia of Asian History, 'China-Russia Trade through Nerchinsk and Kiakhta'; https://oxfordre.com/asianhistory/display/10.1093/acrefore/9780190277727.001.0001/acrefore-9780190277727-e-497"
FORMOSA = "Tonio Andrade, How Taiwan Became Chinese: Dutch, Spanish, and Han Colonization in the Seventeenth Century (Columbia UP, 2008), ch. 1-4 and 11; http://www.gutenberg-e.org/andrade/"

facts = []
def res(key, actor, location, start, end, grade, fact, source):
    row = {"id": "re_" + key, "kind": "residency", "location": location, "start": start, "end": end,
           "grade": grade, "source": source, "fact": fact, "goods": "all"}
    kind, value = actor
    row[kind] = value
    facts.append(row)

T = lambda tag: ("actor_tag", tag)
C = lambda key: ("actor_country", key)
LOC = lambda loc: ("actor_location", loc)

# Red Sea / Persian Gulf
res("eng_mocha", T("ENG"), "al_mukha", 1618, [1750, 1770], "W-B", "The English East India Company keeps a factory with resident factors at Mocha under the port's rulers.", MOCHA)
res("ned_mocha", C("F_DUTCH"), "al_mukha", [1618, 1620], 1738, "W-B", "The Dutch East India Company keeps a factory with resident factors at Mocha.", MOCHA)
res("guj_mocha", LOC("surat"), "al_mukha", [1550, 1600], 1837, "W-B", "A recognised community of Gujarati (Banyan) merchants from Surat resides at Mocha.", MOCHA)
res("eng_gamrun", T("ENG"), "gamrun", 1623, 1763, "W-A", "After the fall of Portuguese Hormuz the English East India Company keeps a factory at Bandar Abbas (Gamrun) under Safavid rule.", EIC + " ; Rudi Matthee, The Politics of Trade in Safavid Iran (Cambridge UP, 1999), ch. 4")
res("ned_gamrun", C("F_DUTCH"), "gamrun", 1623, 1759, "W-A", "The Dutch East India Company keeps a factory at Bandar Abbas (Gamrun) under Safavid rule.", VOC + " ; Rudi Matthee, The Politics of Trade in Safavid Iran (Cambridge UP, 1999), ch. 4")
res("eng_basra", T("ENG"), "basra", [1643, 1723], 1837, "W-B", "The English East India Company maintains a resident agency at Basra.", EIC)
# India
res("eng_surat", T("ENG"), "surat", 1613, 1837, "W-A", "A Mughal farman admits an English East India Company factory at Surat.", EIC + " ; " + PRAKASH)
res("ned_surat", C("F_DUTCH"), "surat", [1616, 1620], 1795, "W-A", "The Dutch East India Company keeps a factory at Surat.", VOC + " ; " + PRAKASH)
res("fra_surat", T("FRA"), "surat", 1668, [1720, 1730], "W-B", "The French East India Company keeps a factory at Surat.", "Encyclopaedia Britannica, 'French East India Company'; https://www.britannica.com/topic/French-East-India-Company ; " + PRAKASH)
res("ned_masulipatnam", C("F_DUTCH"), "masulipatnam", 1606, 1756, "W-B", "The Dutch East India Company keeps a factory at Masulipatnam under Golconda and later rulers.", VOC + " ; " + PRAKASH)
res("eng_masulipatnam", T("ENG"), "masulipatnam", 1611, [1650, 1680], "W-B", "The English East India Company keeps a factory at Masulipatnam.", EIC + " ; " + PRAKASH)
res("por_hughli", LOC("lisbon"), "satgaon", 1579, 1632, "W-B", "Portuguese traders hold a licensed settlement at Hughli in Bengal until the Mughal siege of 1632.", PRAKASH)
res("eng_bengal", T("ENG"), "satgaon", 1651, 1765, "W-A", "The English East India Company keeps factories at Hughli and then Calcutta under Mughal and Nawabi sovereignty until the 1765 diwani.", EIC + " ; " + PRAKASH)
res("ned_chinsurah", C("F_DUTCH"), "satgaon", 1656, 1825, "W-B", "The Dutch East India Company keeps a factory at Chinsurah in Bengal.", VOC + " ; " + PRAKASH)
res("fra_chandernagore", T("FRA"), "satgaon", [1688, 1690], 1757, "W-B", "The French East India Company keeps a factory at Chandernagore in Bengal.", "Encyclopaedia Britannica, 'French East India Company'; https://www.britannica.com/topic/French-East-India-Company ; " + PRAKASH)
res("por_calicut", LOC("lisbon"), "kozhikode", 1500, [1513, 1525], "W-B", "Portugal keeps a feitoria at Calicut under the Zamorin, with interruptions.", PRAKASH + " ; Encyclopaedia Britannica, 'Kozhikode'; https://www.britannica.com/place/Kozhikode")
# Southeast Asia
res("eng_bantam", T("ENG"), "banten", 1602, 1682, "W-A", "The English East India Company keeps a factory at Bantam under the sultanate.", EIC)
res("ned_bantam", C("F_DUTCH"), "banten", 1603, 1619, "W-A", "The Dutch East India Company keeps a factory at Bantam before founding Batavia.", VOC)
res("ned_ayutthaya", C("F_DUTCH"), "ayodhya", 1608, 1767, "W-B", "The Dutch East India Company keeps a factory at Ayutthaya.", AYU + " ; " + VOC)
res("por_ayutthaya", LOC("lisbon"), "ayodhya", [1516, 1540], 1767, "W-B", "A recognised Portuguese settlement exists at Ayutthaya.", AYU)
res("jap_ayutthaya", T("JAP"), "ayodhya", [1600, 1610], [1680, 1690], "W-B", "A Japanese quarter with its own headman exists at Ayutthaya.", AYU)
res("chi_ayutthaya", T("CHI"), "ayodhya", [1400, 1450], 1767, "W-B", "A recognised Chinese merchant quarter exists at Ayutthaya.", AYU)
res("chi_manila", T("CHI"), "maynila", 1581, 1837, "W-A", "Spanish authorities establish the Parian, a licensed quarter for resident Chinese (Sangley) merchants at Manila.", MANILA)
res("jap_manila", T("JAP"), "maynila", [1585, 1600], [1640, 1650], "W-B", "A Japanese community resides at Dilao outside Manila under Spanish licence.", MANILA)
res("chi_batavia", T("CHI"), "sunda_kelapa", 1619, 1837, "W-A", "Batavia's Chinese community is organised under VOC-appointed Chinese officers (kapitan).", BATAVIA)
res("chi_malacca", T("CHI"), "malacca", [1400, 1450], 1837, "W-B", "A recognised Chinese merchant community resides at Malacca under successive rulers.", MELAKA)
# East Asia
res("por_canton", LOC("lisbon"), "guangzhou", 1557, 1837, "W-A", "Portuguese merchants settle at Macau with Ming permission and trade at Canton; the map has no separate Macau location.", MACAU)
res("por_japan", LOC("lisbon"), "nishisonogi", 1550, 1639, "W-A", "Portuguese merchants trade from Hirado and, from 1571, Nagasaki until their expulsion in 1639.", JAPAN)
res("ned_japan", C("F_DUTCH"), "nishisonogi", 1609, 1837, "W-A", "The Dutch East India Company keeps a factory at Hirado and, from 1641, on Dejima at Nagasaki.", VOC + " ; " + JAPAN)
res("eng_japan", T("ENG"), "nishisonogi", 1613, 1623, "W-A", "The English East India Company keeps a factory at Hirado.", EIC + " ; " + JAPAN)
res("chi_nagasaki", T("CHI"), "nishisonogi", 1635, 1837, "W-B", "Chinese merchants are confined to and licensed at Nagasaki, from 1689 in the Tojin yashiki.", JAPAN)
res("jap_waegwan", T("JAP"), "dongnae", 1407, 1837, "W-B", "Japanese traders from Tsushima reside in the Waegwan at Busan under Joseon licence, with interruption in the 1590s war.", "Encyclopaedia Britannica, 'Korea: The Choson dynasty'; https://www.britannica.com/place/Korea/The-Choson-dynasty")
res("eng_amoy_taiwan", T("ENG"), "tongan", [1670, 1676], [1681, 1683], "W-B", "The English East India Company keeps factories on Taiwan and at Amoy under the Zheng regime.", EIC + " ; " + FORMOSA)
res("eng_canton", T("ENG"), "guangzhou", [1699, 1715], 1837, "W-A", "The English East India Company keeps a factory at Canton.", CANTON)
res("ned_canton", C("F_DUTCH"), "guangzhou", 1729, 1837, "W-A", "The Dutch keep a factory at Canton after direct VOC China voyages begin.", CANTON)
res("fra_canton", T("FRA"), "guangzhou", [1698, 1728], 1837, "W-B", "The French keep a factory at Canton.", CANTON)
res("dan_canton", T("DAN"), "guangzhou", 1732, 1837, "W-A", "The Danish Asiatic Company keeps a factory at Canton.", CANTON)
res("swe_canton", T("SWE"), "guangzhou", 1732, 1813, "W-A", "The Swedish East India Company keeps a factory at Canton.", CANTON)
res("hab_canton", T("HAB"), "guangzhou", [1717, 1719], 1731, "W-B", "The Ostend Company of the Austrian Netherlands trades from a factory at Canton until its suspension.", CANTON)
res("usa_canton", C("F_USA"), "guangzhou", 1784, 1837, "W-A", "American merchants keep a factory at Canton from the voyage of the Empress of China.", CANTON)
res("mos_beijing", T("MOS"), "dadu", 1698, 1762, "W-A", "Russian state caravans licensed by the Treaty of Nerchinsk trade and reside for months at Beijing.", KYAKHTA + " ; Clifford M. Foust, Muscovite and Mandarin (University of North Carolina Press, 1969), ch. 1-2")
res("mos_kyakhta", T("MOS"), "kyakhta", 1728, 1837, "W-A", "The Treaty of Kyakhta confines Russo-Chinese trade to the Kyakhta-Maimaicheng border market, where Russian merchants reside.", KYAKHTA)
res("bukhara_suzhou", LOC("bukhara"), "suzhou_gansu", [1560, 1605], 1644, "W-B", "A recognised quarter of Central Asian Muslim merchants resides at Suzhou (Gansu), witnessed by Bento de Gois in 1605.", "Matteo Ricci and Nicolas Trigault, De Christiana expeditione apud Sinas (1615), book V ch. 11-13; Morris Rossabi, 'The Tea and Horse Trade with Inner Asia during the Ming', Journal of Asian History 4 (1970); Encyclopaedia Britannica, 'Bento de Gois'; https://www.britannica.com/biography/Bento-de-Gois")

# Formosa ownership (ea_ group, T1 overseas outposts)
def own(key, actor, provinces, start, end, grade, fact):
    kind, value = actor
    facts.append({"id": "ea_" + key, "kind": "ownership_region", kind: value, "where": {"province": provinces},
                  "start": start, "end": end, "grade": grade, "source": FORMOSA, "fact": fact, "goods": "all"})
own("ned_formosa_south", C("F_DUTCH"), ["south_taiwan_province"], 1624, 1662, "W-A", "The Dutch East India Company governs southwestern Taiwan from Fort Zeelandia.")
own("ned_formosa_west", C("F_DUTCH"), ["west_taiwan_province"], [1635, 1645], 1662, "W-B", "The Dutch extend direct rule over the western plains of Taiwan.")
own("cas_formosa_north", T("CAS"), ["north_taiwan_province"], 1626, 1642, "W-A", "Spain holds northern Taiwan from Keelung and Tamsui.")
own("ned_formosa_north", C("F_DUTCH"), ["north_taiwan_province"], 1642, 1662, "W-A", "The Dutch expel the Spanish and hold northern Taiwan.")

# Input repair found while checking re_ (disclosed): the 1712 capital record moves
# Muscovy to `neva`, but no fact ever transfers `neva` (held by ORE in 1337) to MOS,
# so Russia had no capital from 1712. Petersburg is founded on captured Swedish
# Ingria in 1703 (T1: concerns a capital).
facts.append({"id": "ru_mos_neva_1703", "kind": "ownership", "actor_tag": "MOS", "location": "neva",
              "start": 1703, "end": 1837, "grade": "W-A", "goods": "all",
              "fact": "Russian forces take Nyenskans on the Neva in 1703 and found Saint Petersburg there.",
              "source": "Encyclopaedia Britannica, 'Saint Petersburg: History'; https://www.britannica.com/place/Saint-Petersburg-Russia",
              "repair_of": "ru_capital_petersburg"})

existing = {f["id"] for f in data["facts"]}
clash = [f["id"] for f in facts if f["id"] in existing]
if clash:
    raise SystemExit("duplicate ids: " + ", ".join(clash))
data["facts"].extend(facts)
groups = data.get("groups", {})
groups["re"] = sum(f["id"].startswith("re_") for f in data["facts"])
groups["ea"] = sum(f["id"].startswith("ea_") for f in data["facts"])
data["groups"] = groups
data["version"] = "2026-10-22-round3-asia-residency/1"
data["description"] += " 2026-10-22: auditor added the re_ group (Indian Ocean and East Asian foreign merchant residency, 24 R1 unchanged, loose sourcing at user request) and four Formosa ownership records (ea_)."
data["known_gaps"] = [g for g in data["known_gaps"] if not g.startswith("re_")] + [
    "re_ compiled loosely on 2026-10-22 by the auditor (who had seen round-2 fit results); reference-work sources, some URLs are topic pages. Not included: Armenian and other diaspora communities without institutional recognition, Danish/French Mocha (brief), Hoi An (no map key found), Ryukyu.",
    "ea_ still minimal: only Formosa 1624-1662; Yuan-Ming-Qing, Zheng Taiwan 1662-1683, Qing Taiwan 1683-, Japanese unification and Korean changes absent."]
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"added {len(facts)} facts; total {len(data['facts'])}")
