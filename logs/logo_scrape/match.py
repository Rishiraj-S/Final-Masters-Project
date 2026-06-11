"""Match Opta team_names + competitions to the scraped logo index.

Outputs:
  logs/logo_scrape/team_matches.json   {opta_name: {slug,country,name,svg_url,score}}
  logs/logo_scrape/comp_matches.json   {competition: {...}}
  prints unmatched / low-confidence for review
"""
import json, os, re, unicodedata, difflib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))

index = json.load(open(os.path.join(HERE, "index.json"), encoding="utf-8"))
targets = json.load(open(os.path.join(HERE, "targets_by_country.json"), encoding="utf-8"))

FOLDER2SITE = {
    "Belgium": "belgium", "Czech_Republic": "czech-republic", "Denmark": "denmark",
    "England": "england", "France": "france", "Germany": "germany",
    "Greece": "greece", "Spain": "spain", "Europe": None,  # any
}

# club affixes to strip for fuzzy comparison
AFFIX = {
    "fc", "cf", "cd", "sc", "ac", "afc", "bv", "sk", "sl", "kv", "fk", "ssc",
    "ud", "rc", "rcd", "as", "ss", "us", "club", "calcio", "futbol", "football",
    "fussball", "spor", "kulubu", "kulube", "de", "the", "09", "1893", "1899",
    "balompie", "bergamasca", "internazionale", "spielverein", "borussia",
}


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("&", " and ").replace("/", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t and t not in AFFIX]
    return " ".join(toks)


# precompute normalized forms for index, grouped by country
for e in index:
    e["_n_name"] = norm(e["name"])
    e["_n_slug"] = norm(e["slug"].replace("-", " "))

by_country = {}
for e in index:
    by_country.setdefault(e["country"], []).append(e)


def score(a, b):
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / len(ta | tb) if (ta | tb) else 0
    bonus = 0.1 if (ta & tb) and (ta <= tb or tb <= ta) else 0
    return max(r, jac) + bonus


def best_match(opta_name, countries):
    """countries: set of site slugs to prefer; None-element means search all."""
    na = norm(opta_name)
    pools = []
    if None in countries:
        pools = index
    else:
        for c in countries:
            pools += by_country.get(c, [])
        if not pools:
            pools = index
    best, bs = None, 0.0
    for e in pools:
        s = max(score(na, e["_n_name"]), score(na, e["_n_slug"]))
        if s > bs:
            bs, best = s, e
    return best, round(bs, 3)


# manual overrides: opta_name -> (country, slug)  [verified against index]
TEAM_OVERRIDES = {
    "OGC Nice Côte d'Azur": ("france", "nice"),
    "Reial Club Deportiu Espanyol de Barcelona": ("spain", "espanyol"),
    "FC København": ("denmark", "copenhagen"),
    "København": ("denmark", "copenhagen"),
    "FC Kobenhavn": ("denmark", "copenhagen"),
    "Panaitolikos GFS Agrinio": ("greece", "panetolikos"),
    "Angers Sporting Club de l'Ouest": ("france", "angers"),
    "Association Jeunesse Auxerroise": ("france", "auxerre"),
    "Aarhus Gymnastikforening": ("denmark", "agf"),
}

# alternate spellings used elsewhere in the app (config.yaml / opposition) — keep mapped
EXTRA_NAMES = {
    "Alavés", "Alaves", "Atlético de Madrid", "Atletico de Madrid", "Barcelona",
    "Celta de Vigo", "Athletic Club", "København", "FC Kobenhavn", "Bayern München",
    "Bodø/Glimt", "Inter Milan", "Espanyol", "Newcastle United", "Olympiakos Piraeus",
    "Paris Saint-Germain", "Real Betis", "Real Madrid", "Real Sociedad", "Sevilla",
    "Slavia Praha", "Villarreal", "Leverkusen", "Tottenham", "Union Saint-Gilloise",
}
idx_by_cs = {(e["country"], e["slug"]): e for e in index}

# ---- teams ----
# distinct opta team_name -> set of site countries it appears in
team_countries = {}
for folder, teams in targets.items():
    site = FOLDER2SITE.get(folder)
    for t in teams:
        team_countries.setdefault(t, set()).add(site)
for n in EXTRA_NAMES:
    team_countries.setdefault(n, {None})

team_matches, low = {}, []
for name in sorted(team_countries):
    if name in TEAM_OVERRIDES:
        co, sl = TEAM_OVERRIDES[name]
        e = idx_by_cs.get((co, sl))
        rec = {"slug": e["slug"], "country": e["country"], "site_name": e["name"],
               "svg_url": e["svg_url"], "score": 1.0, "override": True} if e else None
        team_matches[name] = rec
        continue
    e, sc = best_match(name, team_countries[name])
    rec = {"slug": e["slug"], "country": e["country"], "site_name": e["name"],
           "svg_url": e["svg_url"], "score": sc} if e else None
    team_matches[name] = rec
    if not rec or sc < 0.6:
        low.append((name, sc, rec["site_name"] if rec else None,
                    rec["country"] if rec else None))

json.dump(team_matches, open(os.path.join(HERE, "team_matches.json"), "w"),
          ensure_ascii=False, indent=2)

# ---- competitions ----
COMP_NAMES = {
    "Belgium_Cup": "Belgian Cup", "Belgium_First_Division_A": "Pro League",
    "Czech_Cup": "Czech Cup", "Czech_First_League": "Czech First League",
    "Denmark_DBU_Pokalen": "DBU Pokalen", "Denmark_Superliga": "Superliga",
    "England_EFL_Cup": "EFL Cup", "England_FA_Cup": "FA Cup",
    "England_Premier_League": "Premier League",
    "UEFA_Champions_League": "Champions League",
    "France_Coupe_de_France": "Coupe de France", "France_Ligue_1": "Ligue 1",
    "Germany_Bundesliga": "Bundesliga", "Germany_DFB_Pokal": "DFB Pokal",
    "Greece_Cup": "Greek Cup", "Greece_Super_League": "Super League Greece",
    "Spain_Copa_del_Rey": "Copa del Rey",
    "Spain_Primera_Division": "La Liga", "Spain_Super_Cup": "Supercopa",
}
# comp overrides: folder -> (country, slug) | None (absent on site, keep existing asset)
COMP_OVERRIDES = {
    "England_FA_Cup": ("england", "emirates-fa-cup"),
    "Germany_Bundesliga": ("germany", "bundesliga"),
    "Czech_First_League": ("czech-republic", "chance-liga"),
    "Denmark_DBU_Pokalen": ("denmark", "danish-cup"),
    "Greece_Super_League": ("greece", "super-league-1"),
    "UEFA_Champions_League": None,   # not on site — keep existing asset
    "Czech_Cup": None,
    "France_Coupe_de_France": None,
    "Greece_Cup": None,
}
comp_matches, comp_low = {}, []
for folder, disp in COMP_NAMES.items():
    if folder in COMP_OVERRIDES:
        ov = COMP_OVERRIDES[folder]
        if ov is None:
            comp_matches[folder] = {"display": disp, "absent": True}
            continue
        e = idx_by_cs.get(ov)
        comp_matches[folder] = {"display": disp, "slug": e["slug"],
                                "country": e["country"], "site_name": e["name"],
                                "svg_url": e["svg_url"], "score": 1.0, "override": True}
        continue
    site = FOLDER2SITE.get(folder.split("_")[0] if folder.startswith(("Belgium","Czech","Denmark","England","France","Germany","Greece","Spain")) else folder)
    # competition logos may live in the country category; search that country first, else all
    country_folder = folder.split("_")[0]
    # map e.g. "Czech" -> Czech_Republic, "Europe"
    site_country = {"Belgium":"belgium","Czech":"czech-republic","Denmark":"denmark",
                    "England":"england","France":"france","Germany":"germany",
                    "Greece":"greece","Spain":"spain","UEFA":None}.get(country_folder)
    e, sc = best_match(disp, {site_country})
    rec = {"slug": e["slug"], "country": e["country"], "site_name": e["name"],
           "svg_url": e["svg_url"], "score": sc} if e else None
    comp_matches[folder] = {"display": disp, **(rec or {})}
    if not rec or sc < 0.6:
        comp_low.append((folder, disp, sc, rec["site_name"] if rec else None))

json.dump(comp_matches, open(os.path.join(HERE, "comp_matches.json"), "w"),
          ensure_ascii=False, indent=2)

# ---- report ----
print(f"TEAMS: {len(team_matches)} total, "
      f"{sum(1 for v in team_matches.values() if v and v['score']>=0.6)} confident (>=0.6)")
print(f"LOW/UNMATCHED TEAMS ({len(low)}):")
for name, sc, sn, co in sorted(low, key=lambda x: x[1]):
    print(f"  {sc:>5}  {name!r:45} -> {sn} [{co}]")
print(f"\nCOMPETITIONS low/unmatched ({len(comp_low)}):")
for f, d, sc, sn in comp_low:
    print(f"  {sc:>5}  {f} ({d}) -> {sn}")
