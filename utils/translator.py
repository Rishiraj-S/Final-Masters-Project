"""
utils/translator.py
===================
Multi-language support for CuléVision.

Supported languages
-------------------
  en  English   (default — keys are their own translation)
  es  Castellano
  ca  Català

Usage
-----
    from utils.translator import t, get_available_languages

    # In a layout builder that receives `lang`:
    html.Div(t('Filters', lang))

    # Fallback: if a key is missing, the raw key is returned so nothing crashes.

Integration pattern
-------------------
1.  `dcc.Store(id='lang-store', data='en')` lives in the root app layout.
2.  The language dropdown in the navbar writes to that store.
3.  `update_main_container` in app.py takes `State('lang-store', 'data')` and
    passes `lang` to every `create_*_layout(lang=lang)` call.
4.  Callbacks that build dynamic content (KPI bars, tables) include
    `State('lang-store', 'data')` and call `t(key, lang)` for labels.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Translation table
# Each top-level key is the English string (used as-is when lang == 'en').
# Inner dict: {language_code: translated_string}
# ---------------------------------------------------------------------------
_T: dict[str, dict[str, str]] = {

    # ── Navigation ──────────────────────────────────────────────────────────
    'Home':                           {'es': 'Inicio',                      'ca': 'Inici'},
    'Match Report':                   {'es': 'Informe de Partido',          'ca': 'Informe del Partit'},
    'Opposition Analysis':            {'es': 'Análisis Rival',              'ca': 'Anàlisi Rival'},
    'Barça DNA':                      {'es': 'Barça DNA',                   'ca': 'Barça DNA'},
    'Barça IQ':                       {'es': 'Barça IQ',                    'ca': 'Barça IQ'},
    'Language':                       {'es': 'Idioma',                      'ca': 'Idioma'},

    # ── Common UI ────────────────────────────────────────────────────────────
    'Filters':                        {'es': 'Filtros',                     'ca': 'Filtres'},
    'Player':                         {'es': 'Jugador',                     'ca': 'Jugador'},
    'All players…':                   {'es': 'Todos los jugadores…',        'ca': 'Tots els jugadors…'},
    'Competition':                    {'es': 'Competición',                 'ca': 'Competició'},
    'All Tournaments':                {'es': 'Todas las Competiciones',     'ca': 'Totes les Competicions'},
    'Venue':                          {'es': 'Estadio',                     'ca': 'Estadi'},
    'Home (venue)':                   {'es': 'Local',                       'ca': 'Local'},
    'Away (venue)':                   {'es': 'Visitante',                   'ca': 'Visitant'},
    'All':                            {'es': 'Todos',                       'ca': 'Tots'},
    'No data':                        {'es': 'Sin datos',                   'ca': 'Sense dades'},
    'No data available.':             {'es': 'Sin datos disponibles.',      'ca': 'Sense dades disponibles.'},
    'Select a match from the calendar to begin analysis.': {
        'es': 'Selecciona un partido del calendario para comenzar el análisis.',
        'ca': 'Selecciona un partit del calendari per començar l\'anàlisi.',
    },
    'No event data available for this match.': {
        'es': 'No hay datos de eventos para este partido.',
        'ca': 'No hi ha dades d\'events per a aquest partit.',
    },
    'Download Match Report':          {'es': 'Descargar Informe',           'ca': 'Descarregar Informe'},
    'Direction of Attack':            {'es': 'Dirección de Ataque',         'ca': 'Direcció d\'Atac'},
    'Logout':                         {'es': 'Cerrar Sesión',               'ca': 'Tancar Sessió'},

    # ── Shot outcomes ────────────────────────────────────────────────────────
    'Goal':                           {'es': 'Gol',                         'ca': 'Gol'},
    'Goals':                          {'es': 'Goles',                       'ca': 'Gols'},
    'Saved Shot':                     {'es': 'Parada',                      'ca': 'Parada'},
    'Miss':                           {'es': 'Fallo',                       'ca': 'Fallada'},
    'Post':                           {'es': 'Poste',                       'ca': 'Pal'},
    'Blocked Shot':                   {'es': 'Bloqueado',                   'ca': 'Blocat'},

    # ── Set piece origins ────────────────────────────────────────────────────
    'Open Play':                      {'es': 'Juego Abierto',               'ca': 'Joc Obert'},
    'Set Piece':                      {'es': 'Balón Parado',                'ca': 'Pilota Aturada'},
    'Free Kick':                      {'es': 'Falta',                       'ca': 'Falta'},
    'Corner':                         {'es': 'Córner',                      'ca': 'Còrner'},
    'Penalty':                        {'es': 'Penalti',                     'ca': 'Penal'},

    # ── Match Report sections ────────────────────────────────────────────────
    'Overview':                       {'es': 'Resumen',                     'ca': 'Resum'},
    'Attack':                         {'es': 'Ataque',                      'ca': 'Atac'},
    'Build-Up & Passing':             {'es': 'Construcción y Pases',        'ca': 'Construcció i Passades'},
    'Defense':                        {'es': 'Defensa',                     'ca': 'Defensa'},
    'Transitions & Counterpressing':  {'es': 'Transiciones y Contrapress',  'ca': 'Transicions i Contrapressió'},
    'Goalkeeping':                    {'es': 'Portería',                    'ca': 'Porteria'},
    'Player Stats':                   {'es': 'Estadísticas de Jugadores',   'ca': 'Estadístiques de Jugadors'},
    'Selected Match':                 {'es': 'Partido Seleccionado',        'ca': 'Partit Seleccionat'},
    'No match selected':              {'es': 'Ningún partido seleccionado', 'ca': 'Cap partit seleccionat'},
    'Filter by Tournament:':          {'es': 'Filtrar por Competición:',    'ca': 'Filtrar per Competició:'},
    'All Tournaments':                {'es': 'Todas las Competiciones',     'ca': 'Totes les Competicions'},
    'All Venues':                     {'es': 'Todos los Estadios',          'ca': 'Tots els Estadis'},
    'All Competitions…':              {'es': 'Todas las Competiciones…',    'ca': 'Totes les Competicions…'},
    'Country':                        {'es': 'País',                        'ca': 'País'},
    'Club':                           {'es': 'Club',                        'ca': 'Club'},
    'Show matches up to':             {'es': 'Mostrar partidos hasta',      'ca': 'Mostrar partits fins a'},
    'All dates':                      {'es': 'Todas las fechas',            'ca': 'Totes les dates'},
    'Season Stats':                   {'es': 'Estadísticas de Temporada',   'ca': 'Estadístiques de Temporada'},
    'PLAYER':                         {'es': 'JUGADOR',                     'ca': 'JUGADOR'},
    'COMP':                           {'es': 'COMP',                        'ca': 'COMP'},
    'Season Overview 2025–26':   {'es': 'Resumen Temporada 2025–26', 'ca': 'Resum Temporada 2025–26'},
    'Matches':                        {'es': 'Partidos',                    'ca': 'Partits'},
    'Wins':                           {'es': 'Victorias',                   'ca': 'Victòries'},
    'Draws':                          {'es': 'Empates',                     'ca': 'Empats'},
    'Losses':                         {'es': 'Derrotas',                    'ca': 'Derrotes'},
    'Goals For':                      {'es': 'Goles a Favor',               'ca': 'Gols a Favor'},
    'Goals Against':                  {'es': 'Goles en Contra',             'ca': 'Gols en Contra'},

    # ── KPI / stat labels ─────────────────────────────────────────────────────
    'Shots':                          {'es': 'Tiros',                       'ca': 'Tirs'},
    'On Target':                      {'es': 'A Puerta',                    'ca': 'A Porteria'},
    'NP Goals':                       {'es': 'Goles NP',                    'ca': 'Gols NP'},
    'Set Piece G':                    {'es': 'G. Balón Parado',             'ca': 'G. Pilota Aturada'},
    'Assists':                        {'es': 'Asistencias',                 'ca': 'Assistències'},
    'Key Passes':                     {'es': 'Pases Clave',                 'ca': 'Passades Clau'},
    'Box Shots':                      {'es': 'Tiros en Área',               'ca': 'Tirs a l\'Àrea'},
    'Big Chances':                    {'es': 'Grandes Ocasiones',           'ca': 'Grans Ocasions'},
    'Passes':                         {'es': 'Pases',                       'ca': 'Passades'},
    'Pass Acc.':                      {'es': 'Precisión Pases',             'ca': 'Precisió Passades'},
    'Tackles':                        {'es': 'Entradas',                    'ca': 'Entrades'},
    'Interceptions':                  {'es': 'Intercepciones',              'ca': 'Intercepcions'},
    'Recoveries':                     {'es': 'Recuperaciones',              'ca': 'Recuperacions'},
    'Clearances':                     {'es': 'Despejes',                    'ca': 'Desblocaments'},
    'Appearances':                    {'es': 'Partidos',                    'ca': 'Partits'},
    'Minutes':                        {'es': 'Minutos',                     'ca': 'Minuts'},
    'Total Minutes':                  {'es': 'Minutos Totales',             'ca': 'Minuts Totals'},
    'Rating':                         {'es': 'Valoración',                  'ca': 'Valoració'},
    'Position':                       {'es': 'Posición',                    'ca': 'Posició'},
    'Season':                         {'es': 'Temporada',                   'ca': 'Temporada'},

    # ── Chance Creation ───────────────────────────────────────────────────────
    'Shot Map':                       {'es': 'Mapa de Tiros',               'ca': 'Mapa de Tirs'},
    'Shot Outcome':                   {'es': 'Resultado del Tiro',          'ca': 'Resultat del Tir'},
    'Shot Origin':                    {'es': 'Origen del Tiro',             'ca': 'Origen del Tir'},
    'Band':                           {'es': 'Banda',                       'ca': 'Banda'},
    'Left':                           {'es': 'Izquierda',                   'ca': 'Esquerra'},
    'Centre':                         {'es': 'Centro',                      'ca': 'Centre'},
    'Right':                          {'es': 'Derecha',                     'ca': 'Dreta'},
    'Top Scorers':                    {'es': 'Máximos Goleadores',          'ca': 'Màxims Golejadors'},
    'Top Assisters':                  {'es': 'Máximos Assistents',          'ca': 'Màxims Assistents'},
    'Key passes':                     {'es': 'Pases clave',                 'ca': 'Passades clau'},
    'Shooting & Threat Zones':        {'es': 'Zonas de Disparo y Amenaza',  'ca': 'Zones de Tir i Amenaça'},
    'Shot Sequence':                  {'es': 'Secuencia del Tiro',          'ca': 'Seqüència del Tir'},
    'Goal Sequence':                  {'es': 'Secuencia del Gol',           'ca': 'Seqüència del Gol'},

    # ── Pitch zones ───────────────────────────────────────────────────────────
    'Final Third':                    {'es': 'Último Tercio',               'ca': 'Últim Terç'},
    'Penalty Box':                    {'es': 'Área Penal',                  'ca': 'Àrea Penal'},
    'Half Spaces':                    {'es': 'Medioespacios',               'ca': 'Semiespaiss'},
    'Zone 14':                        {'es': 'Zona 14',                     'ca': 'Zona 14'},

    # ── Set Pieces ────────────────────────────────────────────────────────────
    'Free Kicks':                     {'es': 'Faltas',                      'ca': 'Faltes'},
    'Corners':                        {'es': 'Córners',                     'ca': 'Còrners'},
    'Penalties':                      {'es': 'Penaltis',                    'ca': 'Penals'},
    'Total FKs':                      {'es': 'Total Faltas',                'ca': 'Total Faltes'},
    'Completed':                      {'es': 'Completados',                 'ca': 'Completats'},
    'Completion %':                   {'es': '% Completados',               'ca': '% Completats'},
    'Connected':                      {'es': 'Conectados',                  'ca': 'Connectats'},
    'Connect %':                      {'es': '% Conectados',                'ca': '% Connectats'},
    'Inswingers':                     {'es': 'Internos',                    'ca': 'Interiors'},
    'Outswingers':                    {'es': 'Externos',                    'ca': 'Exteriors'},
    'Right Side':                     {'es': 'Lado Derecho',                'ca': 'Costat Dret'},
    'Left Side':                      {'es': 'Lado Izquierdo',              'ca': 'Costat Esquerre'},
    'Free Kick Shot Map':             {'es': 'Mapa de Tiros de Falta',      'ca': 'Mapa de Tirs de Falta'},
    'Goal Mouth — Shot Placement':    {'es': 'Portería — Colocación',       'ca': 'Porteria — Col·locació'},
    'By Taker':                       {'es': 'Por Lanzador',                'ca': 'Per Llançador'},
    'Scored %':                       {'es': '% Marcados',                  'ca': '% Marcats'},
    'Zone 3 Entries from Free Kicks': {'es': 'Entradas al Último Tercio',   'ca': 'Entrades a l\'Últim Terç'},
    'Final Third Entries':            {'es': 'Entradas al Último Tercio',   'ca': 'Entrades a l\'Últim Terç'},
    'Penalty Box Entries':            {'es': 'Entradas al Área',            'ca': 'Entrades a l\'Àrea'},

    # ── Build-Up / Passing ────────────────────────────────────────────────────
    'Pass Map':                       {'es': 'Mapa de Pases',               'ca': 'Mapa de Passades'},
    'Passing Network':                {'es': 'Red de Pases',                'ca': 'Xarxa de Passades'},
    'Progressive Passes':             {'es': 'Pases Progresivos',           'ca': 'Passades Progressives'},
    'Long Balls':                     {'es': 'Balones Largos',              'ca': 'Pilotes Llargues'},
    'Crosses':                        {'es': 'Centros',                     'ca': 'Centrades'},
    'Through Balls':                  {'es': 'Pases al Espacio',            'ca': 'Passades a l\'Espai'},
    'Own Half':                       {'es': 'Propio Campo',                'ca': 'Camp Propi'},
    'Opp. Half':                      {'es': 'Campo Rival',                 'ca': 'Camp Rival'},
    'Outcome':                        {'es': 'Resultado',                   'ca': 'Resultat'},
    'Accurate':                       {'es': 'Precisos',                    'ca': 'Precisos'},
    'Inaccurate':                     {'es': 'Imprecisos',                  'ca': 'Imprecisos'},
    'Start Zone':                     {'es': 'Zona de Inicio',              'ca': 'Zona d\'Inici'},
    'End Zone':                       {'es': 'Zona Final',                  'ca': 'Zona Final'},

    # ── Defensive ─────────────────────────────────────────────────────────────
    'Defensive Actions':              {'es': 'Acciones Defensivas',         'ca': 'Accions Defensives'},
    'Defensive Structure':            {'es': 'Estructura Defensiva',        'ca': 'Estructura Defensiva'},
    'Successful Tackles':             {'es': 'Entradas Exitosas',           'ca': 'Entrades Exitoses'},
    'Aerial Duels':                   {'es': 'Duelos Aéreos',               'ca': 'Duels Aeris'},
    'Aerial Won':                     {'es': 'Aéreos Ganados',              'ca': 'Aeris Guanyats'},
    'Fouls':                          {'es': 'Faltas Cometidas',            'ca': 'Faltes Comeses'},
    'PPDA':                           {'es': 'PPDA',                        'ca': 'PPDA'},

    # ── Transitions ───────────────────────────────────────────────────────────
    'Transitions':                    {'es': 'Transiciones',                'ca': 'Transicions'},
    'Attacking Transition':           {'es': 'Transición Atacante',         'ca': 'Transició Atacant'},
    'Defensive Transition':           {'es': 'Transición Defensiva',        'ca': 'Transició Defensiva'},
    'Counterpressing':                {'es': 'Contrapress',                 'ca': 'Contrapressió'},
    'Ball Won':                       {'es': 'Balón Recuperado',            'ca': 'Pilota Recuperada'},
    'Ball Lost':                      {'es': 'Balón Perdido',               'ca': 'Pilota Perduda'},

    # ── Goalkeeping ───────────────────────────────────────────────────────────
    'Saves':                          {'es': 'Paradas',                     'ca': 'Aturades'},
    'Saves %':                        {'es': '% Paradas',                   'ca': '% Aturades'},
    'Goals Conceded':                 {'es': 'Goles Encajados',             'ca': 'Gols Encaixats'},
    'Clean Sheets':                   {'es': 'Porterías a Cero',            'ca': 'Porteries a Zero'},
    'Sweeper Actions':                {'es': 'Acciones de Líbero',          'ca': 'Accions de Lliure'},

    # ── Opposition Analysis ───────────────────────────────────────────────────
    'Select Team':                    {'es': 'Seleccionar Equipo',          'ca': 'Seleccionar Equip'},
    'Select Competition':             {'es': 'Seleccionar Competición',     'ca': 'Seleccionar Competició'},
    'vs':                             {'es': 'vs',                          'ca': 'vs'},

    # ── Player Analysis (Barça DNA) ───────────────────────────────────────────
    'Player Analysis':                {'es': 'Análisis de Jugadores',       'ca': 'Anàlisi de Jugadors'},
    'Attacking':                      {'es': 'Ofensivo',                    'ca': 'Ofensiu'},
    'Defending':                      {'es': 'Defensivo',                   'ca': 'Defensiu'},
    'Physical':                       {'es': 'Físico',                      'ca': 'Físic'},
    'Percentile':                     {'es': 'Percentil',                   'ca': 'Percentil'},

    # ── Team Analysis (Barça IQ) ──────────────────────────────────────────────
    'Team Analysis':                  {'es': 'Análisis del Equipo',         'ca': 'Anàlisi de l\'Equip'},
    'Build-Up':                       {'es': 'Construcción',                'ca': 'Construcció'},
    'Chance Creation':                {'es': 'Creación de Ocasiones',       'ca': 'Creació d\'Ocasions'},
    'Set Pieces':                     {'es': 'Balones Parados',             'ca': 'Pilotes Aturades'},
    'Top FK Takers':                  {'es': 'Principales Lanzadores',      'ca': 'Principals Llançadors'},
    'By Taker (All Corners)':         {'es': 'Por Lanzador (Todos)',        'ca': 'Per Llançador (Tots)'},

    # ── Home / pipeline ───────────────────────────────────────────────────────
    'Season Overview':                {'es': 'Resumen de Temporada',        'ca': 'Resum de Temporada'},
    'Update Database':                {'es': 'Actualizar Base de Datos',    'ca': 'Actualitzar Base de Dades'},
    'Updating Databases with latest matches': {
        'es': 'Actualizando bases de datos con los últimos partidos',
        'ca': 'Actualitzant bases de dades amb els darrers partits',
    },
    'Please wait while the system downloads opposition match data...': {
        'es': 'Espera mientras el sistema descarga los datos de los partidos...',
        'ca': 'Espera mentre el sistema descarrega les dades dels partits...',
    },

    # ── Time / period ─────────────────────────────────────────────────────────
    'First Half':                     {'es': 'Primera Parte',               'ca': 'Primera Part'},
    'Second Half':                    {'es': 'Segunda Parte',               'ca': 'Segona Part'},
    'H1':                             {'es': 'P1',                          'ca': 'P1'},
    'H2':                             {'es': 'P2',                          'ca': 'P2'},
    'Min':                            {'es': 'Min',                         'ca': 'Min'},

    # ── Table column headers ──────────────────────────────────────────────────
    'Player':                         {'es': 'Jugador',                     'ca': 'Jugador'},
    'G':                              {'es': 'G',                           'ca': 'G'},
    'A':                              {'es': 'A',                           'ca': 'A'},
    'Sh':                             {'es': 'Tir',                         'ca': 'Tir'},
    'KP':                             {'es': 'PC',                          'ca': 'PC'},
    'Conv%':                          {'es': 'Conv%',                       'ca': 'Conv%'},
    'Comp':                           {'es': 'Comp',                        'ca': 'Comp'},
    'Comp%':                          {'es': 'Comp%',                       'ca': 'Comp%'},
    'Total':                          {'es': 'Total',                       'ca': 'Total'},
    'Shots (table)':                  {'es': 'Tiros',                       'ca': 'Tirs'},
    'Shot%':                          {'es': '% Tiro',                      'ca': '% Tir'},
    'Goal%':                          {'es': '% Gol',                       'ca': '% Gol'},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def t(key: str, lang: str = 'en') -> str:
    """Return the translation of *key* in *lang*.

    Behaviour:
    - ``lang == 'en'``: returns *key* unchanged (English is the master).
    - Missing *lang* entry: returns *key* (graceful fallback, nothing crashes).
    - Missing *key*: returns *key* (untranslated strings stay as English).
    """
    if lang == 'en':
        return key
    entry = _T.get(key)
    if entry is None:
        return key
    return entry.get(lang, key)


def get_available_languages() -> list[dict]:
    """Return the language options list for a ``dcc.Dropdown``."""
    return [
        {'label': 'English',    'value': 'en'},
        {'label': 'Castellano', 'value': 'es'},
        {'label': 'Català',     'value': 'ca'},
    ]
