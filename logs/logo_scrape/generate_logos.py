"""Regenerate utils/logos.py — authoritative file → team-name mapping.

The app passes TWO different spellings to get_team_logo_path:
  * home_team / away_team columns  (short: 'Chelsea', 'Real Madrid')   -> match_report, Barca pages
  * team_name column               (full Opta: 'Chelsea FC', 'Real Madrid CF') -> opposition analysis

So every logo file is mapped to ALL of its data name variants below. Names are
copied verbatim from the data's home/away and team_name columns (+ a few config
aliases). Edit FILE_TEAMS and re-run to regenerate utils/logos.py.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TEAM_DIR = os.path.join(ROOT, "assets", "logos", "team")
TOUR_DIR = os.path.join(ROOT, "assets", "logos", "tournament")
LOGOS_PY = os.path.join(ROOT, "utils", "logos.py")

# logo file -> every team-name spelling seen in the data (short + full + aliases)
FILE_TEAMS = {
    # ── scraped slug files ───────────────────────────────────────────────
    'aek-athens.svg': ['AEK Athens FC', 'AEK Athens'],
    'agf.svg': ['Aarhus Gymnastikforening', 'AGF'],
    'ajax.svg': ['AFC Ajax', 'Ajax'],
    'albacete.svg': ['Albacete Balompié', 'Albacete'],
    'angers.svg': ["Angers Sporting Club de l'Ouest", 'Angers SCO'],
    'aris-thessaloniki.svg': ['Aris Thessaloniki FC', 'Aris'],
    'arsenal.svg': ['Arsenal FC', 'Arsenal'],
    'as-monaco.svg': ['AS Monaco FC', 'Monaco'],
    'asteras.svg': ['Asteras Tripolis Aktor FC', 'Asteras Tripolis'],
    'aston-villa.svg': ['Aston Villa FC', 'Aston Villa'],
    'atalanta.svg': ['Atalanta Bergamasca Calcio', 'Atalanta'],
    'athletic-club.svg': ['Athletic Club'],
    'atletico-madrid.svg': ['Club Atlético de Madrid', 'Atlético de Madrid', 'Atletico de Madrid'],
    'auxerre.svg': ['Association Jeunesse Auxerroise', 'Auxerre'],
    'barcelona.svg': ['FC Barcelona', 'Barcelona'],
    'bayer-leverkusen.svg': ['Bayer 04 Leverkusen', 'Bayer Leverkusen', 'Leverkusen'],
    'bayern-munchen.svg': ['FC Bayern München', 'Bayern München'],
    'bodo-glimt.svg': ['FK Bodø / Glimt', 'Bodø / Glimt', 'Bodø/Glimt'],
    'bohemians-praha.svg': ['Bohemians Praha 1905', 'Bohemians 1905'],
    'borussia-dortmund.svg': ['BV Borussia 09 Dortmund', 'Borussia Dortmund'],
    'borussia-monchengladbach.svg': ['Borussia VfL Mönchengladbach', "Borussia M'gladbach"],
    'bournemouth.svg': ['AFC Bournemouth'],
    'bradford.svg': ['Bradford City AFC', 'Bradford City'],
    'brentford.svg': ['Brentford FC', 'Brentford'],
    'brondby.svg': ['Brøndby IF', 'Brøndby'],
    'burgos.svg': ['Burgos CF', 'Burgos'],
    'burnley.svg': ['Burnley FC', 'Burnley'],
    'cardiff-city.svg': ['Cardiff City FC', 'Cardiff City'],
    'cd-ebro.svg': ['CD Ebro', 'Ebro'],
    'celta.svg': ['Real Club Celta de Vigo', 'Celta de Vigo'],
    'ceuta.svg': ['AD Ceuta FC', 'Ceuta'],
    'cf-talavera-de-la-reina.svg': ['CF Talavera de la Reina', 'Talavera'],
    'copenhagen.svg': ['FC København', 'København', 'FC Kobenhavn'],
    'cultural-leonesa.svg': ['Cultural y Deportiva Leonesa', 'Cultural Leonesa'],
    'drita.svg': ['KF Drita', 'Drita'],
    'eintracht-frankfurt.svg': ['Eintracht Frankfurt'],
    'fc-cartagena.svg': ['FC Cartagena'],
    'fc-heidenheim.svg': ['1. FC Heidenheim 1846', 'Heidenheim'],
    'fc-metz.svg': ['FC Metz', 'Metz'],
    'fredericia.svg': ['FC Fredericia', 'Fredericia'],
    'hradec-kralove.svg': ['FC Hradec Králové', 'Hradec Králové'],
    'koln.svg': ['1. FC Köln', 'Köln'],
    'larissa.svg': ['AE Larissa', 'Larissa'],
    'lorient.svg': ['FC Lorient', 'Lorient'],
    'mainz-05.svg': ['1. FSV Mainz 05', 'Mainz 05'],
    'midtjylland.svg': ['FC Midtjylland', 'Midtjylland'],
    'osasuna.svg': ['CA Osasuna', 'Osasuna'],
    'oviedo.svg': ['Real Oviedo'],
    'randers.svg': ['Randers FC', 'Randers'],
    'real-betis.svg': ['Real Betis Balompié', 'Real Betis'],
    'slovacko.svg': ['1. FC Slovácko', 'Slovácko'],
    'sparta-praha.svg': ['AC Sparta Praha', 'Sparta Praha'],
    'union-berlin.svg': ['1. FC Union Berlin', 'Union Berlin'],
    'wolves.svg': ['Wolverhampton Wanderers FC', 'Wolverhampton Wanderers'],
    # ── existing version-style assets ────────────────────────────────────
    'Chelsea-FC-v2006.svg': ['Chelsea FC', 'Chelsea'],
    'Club-Brugge-KV-v2017.svg': ['Club Brugge KV', 'Club Brugge'],
    'Club-Deportivo-Leganes-v2014.svg': ['CD Leganés', 'Leganés'],
    'Deportivo-Alaves-v2020.svg': ['Deportivo Alavés', 'Alavés', 'Alaves'],
    'Deportivo-de-La-Coruna-v2000.svg': ['RC Deportivo de La Coruña', 'Deportivo de La Coruña'],
    'Elche-CF-v2009.svg': ['Elche CF', 'Elche'],
    'FC-Inter-Milan-v2021.svg': ['FC Internazionale Milano', 'Internazionale', 'Inter Milan'],
    'FC-Kairat-Almaty-v2019.svg': ['FK Kairat Almaty', 'Kairat'],
    'Galatasaray-SK-v2007.svg': ['Galatasaray Spor Kulübü', 'Galatasaray'],
    'Getafe-Club-de-Futbol-v2011.svg': ['Getafe CF', 'Getafe'],
    'Girona-Futbol-Club-v2021.svg': ['Girona FC', 'Girona'],
    'Granada-CF-v2023.svg': ['Granada CF', 'Granada'],
    'Juventus-FC-v2017.svg': ['Juventus FC', 'Juventus'],
    'Levante-UD-v2010.svg': ['Levante UD', 'Levante'],
    'Liverpool-Football-Club-v2024-minor.svg': ['Liverpool FC', 'Liverpool'],
    'Manchester-City-v2016.svg': ['Manchester City FC', 'Manchester City'],
    'Newcastle-United-Football-Club-v1988.svg': ['Newcastle United FC', 'Newcastle United'],
    'Olympiacos-Football-Club-v2003.svg': ['Olympiakos FC', 'Olympiakos Piraeus'],
    'Olympique-de-Marseille-v2004.svg': ['Olympique de Marseille', 'Olympique Marseille'],
    'PSV-Eindhoven-v2016.svg': ['PSV Eindhoven', 'PSV'],
    'Pafos-FC-v0000.svg': ['Pafos FC', 'Pafos'],
    'Paris-Saint-Germain-v2013.svg': ['Paris Saint-Germain FC', 'Paris Saint-Germain'],
    'Qarabag-FK-v0000.svg': ['Qarabağ Ağdam FK', 'Qarabağ'],
    'RCD-Espanyol-v2005.svg': ['Reial Club Deportiu Espanyol de Barcelona', 'Espanyol'],
    'Racing-de-Santander-v2003.svg': ['Real Racing Club', 'Racing de Santander'],
    'Rayo-Vallecano-de-Madrid-v2012.svg': ['Rayo Vallecano de Madrid', 'Rayo Vallecano'],
    'Real-Club-Deportivo-Mallorca-v1996.svg': ['Real Club Deportivo Mallorca', 'Mallorca'],
    'Real-Madrid-CF-v2002.svg': ['Real Madrid CF', 'Real Madrid'],
    'Real-Sociedad-de-Futbol-v1997.svg': ['Real Sociedad de Fútbol', 'Real Sociedad'],
    'Real-Sporting-de-Gijon-v2000.svg': ['Real Sporting de Gijón', 'Sporting de Gijón'],
    'Royale-Union-Saint-Gilloise-v2015.svg': ['Royale Union Saint-Gilloise', 'Union Saint-Gilloise'],
    'SD-Eibar-v2015.svg': ['SD Eibar', 'Eibar'],
    'SD-Huesca-v2024.svg': ['SD Huesca', 'Huesca'],
    'SK-Slavia-Praha-v0000.svg': ['SK Slavia Praha', 'Slavia Praha'],
    'SSC-Napoli-v2024.svg': ['SSC Napoli', 'Napoli'],
    'Sevilla-Futbol-Club-v1995.svg': ['Sevilla FC', 'Sevilla'],
    'Sport-Lisboa-e-Benfica-v1999.svg': ['SL Benfica', 'Benfica'],
    'Sporting-Clube-de-Portugal-v2011.svg': ['Sporting Clube de Portugal', 'Sporting CP'],
    'Tottenham-Hotspur-Football-Club-v2024.svg': ['Tottenham Hotspur FC', 'Tottenham Hotspur'],
    'Valencia-Club-de-Futbol-v2012.svg': ['Valencia CF', 'Valencia'],
    'Villarreal-Club-de-Futbol-v2009.svg': ['Villarreal CF', 'Villarreal'],
    # ── on disk but team not in current data (kept, unmapped intentionally) ──
    # Cadiz-CF-v2009.svg, UD-Las-Palmas-v2011.svg, Real-Valladolid-...v2024.svg
}

# competition folder key -> tournament logo filename
TOUR_LOGOS = {
    'Spain_Primera_Division': 'LALIGA-Primera-Division-v2023.svg',
    'UEFA_Champions_League': 'UEFA-Champions-League-v2021.svg',
    'Spain_Copa_del_Rey': 'Copa del Rey logo - Brandlogos.net.svg',
    'Spain_Super_Cup': 'supercopa-de-espana-seeklogo.svg',
}

# merge auto-generated extras from the second download pass (missing teams)
_extra_path = os.path.join(HERE, "extra_file_teams.json")
if os.path.exists(_extra_path):
    import json as _json
    for fn, names in _json.load(open(_extra_path, encoding="utf-8")).items():
        FILE_TEAMS.setdefault(fn, [])
        for nm in names:
            if nm not in FILE_TEAMS[fn]:
                FILE_TEAMS[fn].append(nm)

# ── build TEAM_LOGOS: every name variant -> file (file must exist) ────────────
team_logos, dupe = {}, []
for fn, names in FILE_TEAMS.items():
    if not os.path.exists(os.path.join(TEAM_DIR, fn)):
        raise SystemExit(f"ERROR: mapped file missing on disk: {fn}")
    for nm in names:
        if nm in team_logos and team_logos[nm] != fn:
            dupe.append((nm, team_logos[nm], fn))
        team_logos[nm] = fn
team_logos = {k: team_logos[k] for k in sorted(team_logos)}

tour_logos = {k: v for k, v in sorted(TOUR_LOGOS.items())
              if os.path.exists(os.path.join(TOUR_DIR, v))}


def fmt(d):
    return "\n".join(f"    {k!r}: {v!r}," for k, v in d.items())


HEADER = ('"""\nCuléVision - Logo Utilities\n'
          'Mapping from data team/competition names to asset file paths.\n\n'
          'GENERATED by logs/logo_scrape/generate_logos.py.\n'
          'TEAM_LOGOS keys cover BOTH the home/away column spelling (short) and the\n'
          'team_name column spelling (full Opta) because different pages pass each.\n'
          'TOURNAMENT_LOGOS is keyed by competition folder key.\n'
          '"""\n\nfrom dash import html\n\n')

TEAM_BLOCK = "# ── Team name → logo filename ──\nTEAM_LOGOS = {\n" + fmt(team_logos) + "\n}\n\n"

FLAGS_BLOCK = '''COUNTRY_FLAGS = {
    'Belgium':        'be',
    'Czech Republic': 'cz',
    'Denmark':        'dk',
    'England':        'gb-eng',
    'France':         'fr',
    'Germany':        'de',
    'Greece':         'gr',
    'Italy':          'it',
    'Netherlands':    'nl',
    'Portugal':       'pt',
    'Scotland':       'gb-sct',
    'Spain':          'es',
    'Turkey':         'tr',
    'Wales':          'gb-wls',
}

'''

TOUR_BLOCK = ("# ── Competition folder key → logo filename ──\n"
              "TOURNAMENT_LOGOS = {\n" + fmt(tour_logos) + "\n}\n\n"
              "# Barca pages pass display names; bridge them to folder keys.\n"
              "_COMP_DISPLAY_ALIASES = {\n"
              "    'La Liga': 'Spain_Primera_Division',\n"
              "    'Champions League': 'UEFA_Champions_League',\n"
              "    'Copa del Rey': 'Spain_Copa_del_Rey',\n"
              "    'Spanish Super Cup': 'Spain_Super_Cup',\n"
              "}\n\n")

HELPERS = '''def get_team_logo_path(team_name: str) -> str:
    """Return the Dash-relative asset path for a team logo, or empty string."""
    filename = TEAM_LOGOS.get(team_name)
    if filename:
        return f'/assets/logos/team/{filename}'
    return ''


def get_country_flag_path(country: str) -> str:
    """Return the Dash-relative asset path for a country flag SVG, or empty string."""
    iso = COUNTRY_FLAGS.get(country)
    if iso:
        return f'/assets/logos/flag/{iso}.svg'
    return ''


def get_tournament_logo_path(competition: str) -> str:
    """Return the tournament logo path. Accepts a competition folder key
    (e.g. 'Spain_Primera_Division') or a Barca display name (e.g. 'La Liga')."""
    key = competition if competition in TOURNAMENT_LOGOS else \\
        _COMP_DISPLAY_ALIASES.get(competition, competition)
    filename = TOURNAMENT_LOGOS.get(key)
    if filename:
        return f'/assets/logos/tournament/{filename}'
    return ''


def team_logo_img(team_name: str, size: str = '24px') -> html.Img:
    """Return an html.Img element for a team logo, or an empty span if not found."""
    path = get_team_logo_path(team_name)
    if path:
        return html.Img(src=path, style={
            'height': size, 'width': size, 'objectFit': 'contain',
        })
    return html.Span()


def tournament_logo_img(competition: str, size: str = '24px') -> html.Img:
    """Return an html.Img element for a tournament logo, or an empty span."""
    path = get_tournament_logo_path(competition)
    if path:
        return html.Img(src=path, style={
            'height': size, 'width': size, 'objectFit': 'contain',
        })
    return html.Span()
'''

open(LOGOS_PY, "w", encoding="utf-8").write(
    HEADER + TEAM_BLOCK + FLAGS_BLOCK + TOUR_BLOCK + HELPERS)

print(f"WROTE {LOGOS_PY}")
print(f"TEAM_LOGOS: {len(team_logos)} name keys -> {len(set(team_logos.values()))} files")
print(f"TOURNAMENT_LOGOS: {len(tour_logos)}")
if dupe:
    print("DUPLICATE name conflicts:")
    for n, a, b in dupe:
        print(f"  {n!r}: {a} vs {b}")
