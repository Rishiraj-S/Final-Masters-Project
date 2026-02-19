"""
CuléVision - Logo Utilities
Mapping from data team/competition names to asset file paths.
"""

from dash import html

# ── Team name → logo filename mapping ────────────────────────────────────────
# Keys are team names exactly as they appear in the Opta/parquet data.
# Values are filenames inside assets/logos/team/.

TEAM_LOGOS = {
    'Alavés': 'Deportivo-Alaves-v2020.svg',
    'Albacete': 'Albacete-Balompie-v2009.svg',
    'Athletic Club': 'Athletic-Club-Bilbao-v2008.svg',
    'Atlético de Madrid': 'Atletico-Madrid-v2024.svg',
    'Barcelona': 'FC-Barcelona-v2002.svg',
    'Celta de Vigo': 'RC-Celta-de-Vigo-v2010.svg',
    'Chelsea': 'Chelsea-FC-v2006.svg',
    'Club Brugge': 'Club-Brugge-KV-v2017.svg',
    'Eintracht Frankfurt': 'Eintracht-Frankfurt-v1998.svg',
    'Elche': 'Elche-CF-v2009.svg',
    'Espanyol': 'RCD-Espanyol-v2005.svg',
    'Getafe': 'Getafe-Club-de-Futbol-v2011.svg',
    'Girona': 'Girona-Futbol-Club-v2021.svg',
    'København': 'FC-Copenhagen-v1992.svg',
    'Levante': 'Levante-UD-v2010.svg',
    'Mallorca': 'Real-Club-Deportivo-Mallorca-v1996.svg',
    'Newcastle United': 'Newcastle-United-Football-Club-v1988.svg',
    'Olympiakos Piraeus': 'Olympiacos-Football-Club-v2003.svg',
    'Osasuna': 'Club-Atletico-Osasuna-v2004.svg',
    'Paris Saint-Germain': 'Paris-Saint-Germain-v2013.svg',
    'Racing de Santander': 'Racing-de-Santander-v2003.svg',
    'Rayo Vallecano': 'Rayo-Vallecano-de-Madrid-v2012.svg',
    'Real Betis': 'Real-Betis-v2022.svg',
    'Real Madrid': 'Real-Madrid-CF-v2002.svg',
    'Real Oviedo': 'Real-Oviedo-v2019.svg',
    'Real Sociedad': 'Real-Sociedad-de-Futbol-v1997.svg',
    'Sevilla': 'Sevilla-Futbol-Club-v1995.svg',
    'Slavia Praha': 'SK-Slavia-Praha-v0000.svg',
    'Valencia': 'Valencia-Club-de-Futbol-v2012.svg',
    'Villarreal': 'Villarreal-Club-de-Futbol-v2009.svg',
    # Additional teams from other competitions
    'Ajax': 'AFC-Ajax-v2025.svg',
    'Atalanta': 'Atalanta-BC-v1993.svg',
    'Bayern München': 'FC-Bayern-Munchen-v2024.svg',
    'Benfica': 'Sport-Lisboa-e-Benfica-v1999.svg',
    'Bodø/Glimt': 'FK-Bodo-Glimt-v0000.svg',
    'Borussia Dortmund': 'Borussia-Dortmund-v1993.svg',
    'Galatasaray': 'Galatasaray-SK-v2007.svg',
    'Inter Milan': 'FC-Inter-Milan-v2021.svg',
    'Juventus': 'Juventus-FC-v2017.svg',
    'Leverkusen': 'Bayer-04-Leverkusen-v2006.svg',
    'Liverpool': 'Liverpool-Football-Club-v2024-minor.svg',
    'Manchester City': 'Manchester-City-v2016.svg',
    'Marseille': 'Olympique-de-Marseille-v2004.svg',
    'Monaco': 'AS-Monaco-v2021.svg',
    'Napoli': 'SSC-Napoli-v2024.svg',
    'PSV': 'PSV-Eindhoven-v2016.svg',
    'Sporting CP': 'Sporting-Clube-de-Portugal-v2011.svg',
    'Tottenham': 'Tottenham-Hotspur-Football-Club-v2024.svg',
    'Union Saint-Gilloise': 'Royale-Union-Saint-Gilloise-v2015.svg',
    'Arsenal': 'Arsenal-FC-v2002.svg',
    # Copa del Rey lower-division opponents
    'Guadalajara': None,
    'Ceuta': 'AD-Ceuta-FC-v2013.svg',
    'Leganés': 'Club-Deportivo-Leganes-v2014.svg',
    'Las Palmas': 'UD-Las-Palmas-v2011.svg',
    'Granada': 'Granada-CF-v2023.svg',
    'Cádiz': 'Cadiz-CF-v2009.svg',
    'Valladolid': 'Real-Valladolid-Club-de-Futbol-v2024.svg',
}

# ── Competition name → logo filename mapping ─────────────────────────────────
# Keys match COMPETITION_NAMES values from data_utils.py.

TOURNAMENT_LOGOS = {
    'La Liga': 'LALIGA-Primera-Division-v2023.svg',
    'Champions League': 'UEFA-Champions-League-v2021.svg',
    'Copa del Rey': 'Copa del Rey logo - Brandlogos.net.svg',
    'Spanish Super Cup': 'supercopa-de-espana-seeklogo.svg',
}


def get_team_logo_path(team_name: str) -> str:
    """Return the Dash-relative asset path for a team logo, or empty string."""
    filename = TEAM_LOGOS.get(team_name)
    if filename:
        return f'/assets/logos/team/{filename}'
    return ''


def get_tournament_logo_path(competition: str) -> str:
    """Return the Dash-relative asset path for a tournament logo, or empty string."""
    filename = TOURNAMENT_LOGOS.get(competition)
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
