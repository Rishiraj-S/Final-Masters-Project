from __future__ import annotations
import io, base64
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from dash import html, dcc
import dash_bootstrap_components as dbc
from utils.config import COLORS
from utils.data_utils import get_match_events, exclude_own_goals
from utils.xt_utils import add_xt_column
from .shared import CARD_STYLE, section_header, build_info_box, build_legend_box, build_team_stats_table
from page_utils.visualizations import HOME_COLOR, AWAY_COLOR, GOLD, CHART_CONFIG, layout_config, add_pitch_background, PITCH_AXIS_FULL, render_xt_heatmap_img, render_lsc_heatmap_img
from page_utils.event_filters import SHOT_TYPES

_ZONE_RANGES  = {'Def. Third': (0, 33.33), 'Mid Third': (33.33, 66.67), 'Fin. Third': (66.67, 100)}
_FLANK_RANGES = {'Left': (0, 33.33), 'Centre': (33.33, 66.67), 'Right': (66.67, 100)}


def _apply_filters(events: pd.DataFrame, half: str, zones: list, flanks: list) -> pd.DataFrame:
    ev = events.copy()
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in ev.columns:
            ev[col] = pd.to_numeric(ev[col], errors='coerce')
    if half == '1':
        ev = ev[ev['period_id'] == 1]
    elif half == '2':
        ev = ev[ev['period_id'] == 2]
    if zones and set(zones) != set(_ZONE_RANGES):
        masks = []
        for z in zones:
            lo, hi = _ZONE_RANGES[z]
            masks.append((ev['x'] >= lo) & (ev['x'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]
    if flanks and set(flanks) != set(_FLANK_RANGES):
        masks = []
        for f in flanks:
            lo, hi = _FLANK_RANGES[f]
            masks.append((ev['y'] >= lo) & (ev['y'] <= hi))
        ev = ev[pd.concat(masks, axis=1).any(axis=1)]
    return ev


def _count_si(df: pd.DataFrame, col: str) -> int:
    if col not in df.columns:
        return 0
    return int((df[col] == 'Si').sum())


def _build_network(te: pd.DataFrame):
    cols = ['player_name', 'event_type', 'outcome', 'x', 'y', 'period_id', 'time_min', 'time_sec']
    ev = te[[c for c in cols if c in te.columns]].copy()
    ev = ev.dropna(subset=['player_name', 'x', 'y'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    edges: dict = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]
        nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1
                and pd.notna(nxt.get('player_name'))):
            a, b = str(row['player_name']), str(nxt['player_name'])
            if a != b:
                edges[(a, b)] = edges.get((a, b), 0) + 1
    edges = {k: v for k, v in edges.items() if v >= 2}
    pass_ev = ev[ev['event_type'] == 'Pass']
    if pass_ev.empty:
        return pd.DataFrame(), {}
    nodes = (
        pass_ev.groupby('player_name')
        .agg(x=('x', 'mean'), y=('y', 'mean'))
        .reset_index()
    )
    inv: dict = {}
    for (a, b), cnt in edges.items():
        inv[a] = inv.get(a, 0) + cnt
        inv[b] = inv.get(b, 0) + cnt
    nodes['involvement'] = nodes['player_name'].map(lambda p: inv.get(p, 1))
    if len(nodes) > 1 and nodes['involvement'].max() > nodes['involvement'].min():
        sc = MinMaxScaler(feature_range=(14, 36))
        nodes['size'] = sc.fit_transform(nodes[['involvement']]).flatten()
    else:
        nodes['size'] = 22.0
    nodes['label'] = nodes['player_name'].apply(
        lambda n: n.split()[-1] if isinstance(n, str) else n)
    return nodes, edges


def _build_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 1):
        row = ev.iloc[i]; nxt = ev.iloc[i + 1]
        if (row['event_type'] == 'Pass' and row.get('outcome') == 1 and pd.notna(nxt.get('player_name'))):
            a = str(row['player_name']).split()[-1]
            b = str(nxt['player_name']).split()[-1]
            if a != b:
                key = (a, b)
                combos[key] = combos.get(key, 0) + 1
                if row['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif row['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b}', 'Total': cnt,
             'H1': combos_h1.get((a, b), 0), 'H2': combos_h2.get((a, b), 0)}
            for (a, b), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


def _build_3player_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 2):
        r1 = ev.iloc[i]; r2 = ev.iloc[i + 1]; r3 = ev.iloc[i + 2]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and pd.notna(r2.get('player_name')) and pd.notna(r3.get('player_name'))):
            a = str(r1['player_name']).split()[-1]
            b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]
            if a != b and b != c:
                key = (a, b, c)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b} -> {c}', 'Total': cnt,
             'H1': combos_h1.get((a, b, c), 0), 'H2': combos_h2.get((a, b, c), 0)}
            for (a, b, c), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


def _build_4player_combos(te: pd.DataFrame) -> pd.DataFrame:
    ev = te[['player_name', 'event_type', 'outcome', 'period_id', 'time_min', 'time_sec']].copy()
    ev = ev.dropna(subset=['player_name'])
    ev = ev.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    combos: dict = {}; combos_h1: dict = {}; combos_h2: dict = {}
    for i in range(len(ev) - 3):
        r1 = ev.iloc[i]; r2 = ev.iloc[i+1]; r3 = ev.iloc[i+2]; r4 = ev.iloc[i+3]
        if (r1['event_type'] == 'Pass' and r1.get('outcome') == 1
                and r2['event_type'] == 'Pass' and r2.get('outcome') == 1
                and r3['event_type'] == 'Pass' and r3.get('outcome') == 1
                and pd.notna(r2.get('player_name')) and pd.notna(r3.get('player_name'))
                and pd.notna(r4.get('player_name'))):
            a = str(r1['player_name']).split()[-1]; b = str(r2['player_name']).split()[-1]
            c = str(r3['player_name']).split()[-1]; d = str(r4['player_name']).split()[-1]
            if a != b and b != c and c != d:
                key = (a, b, c, d)
                combos[key] = combos.get(key, 0) + 1
                if r1['period_id'] == 1:   combos_h1[key] = combos_h1.get(key, 0) + 1
                elif r1['period_id'] == 2: combos_h2[key] = combos_h2.get(key, 0) + 1
    if not combos:
        return pd.DataFrame(columns=['Combo', 'Total', 'H1', 'H2'])
    rows = [{'Combo': f'{a} -> {b} -> {c} -> {d}', 'Total': cnt,
             'H1': combos_h1.get((a, b, c, d), 0), 'H2': combos_h2.get((a, b, c, d), 0)}
            for (a, b, c, d), cnt in combos.items()]
    return pd.DataFrame(rows).sort_values('Total', ascending=False).head(8).reset_index(drop=True)


_league_avg_cache: dict = {}

_RADAR_KEYS = [
    ('Total Passes',     'passes'),
    ('Pass Accuracy',    'pass_acc'),
    ('Field Tilt',       'field_tilt'),
    ('Avg Passes/Poss',  'avg_passes_per_poss'),
    ('Positional xT',    'total_xt'),
    ('Into Final Third', 'into_ft'),
    ('Long Balls',       'long_balls'),
    ('Through Balls',    'thru_balls'),
    ('Ball Carries',     'carries'),
    ('Dribble Attempts', 'dribbles'),
    ('Dribbles Won',     'drib_succ'),
    ('Dribble Success',  'drib_acc'),
]


def _compute_league_avg(events: pd.DataFrame) -> dict:
    from utils.data_utils import get_match_results
    global _league_avg_cache
    competition = ''
    if 'competition' in events.columns and not events.empty:
        competition = str(events['competition'].iloc[0])
    if not competition:
        try:
            from utils.match_data_adapter import get_match_metadata
            competition = get_match_metadata(events).get('competition', '')
        except Exception:
            pass
    if not competition:
        return {}
    if competition in _league_avg_cache:
        return _league_avg_cache[competition]
    try:
        keys = [k for _, k in _RADAR_KEYS]
        accumulated: dict = {k: [] for k in keys}
        for r in get_match_results():
            if r.get('competition') != competition:
                continue
            try:
                ev = get_match_events(r['match_id'])
                if ev.empty:
                    continue
                for pos in ('home', 'away'):
                    s = _compute_half_stats(ev, pos)
                    for k in keys:
                        v = s.get(k, 0)
                        if isinstance(v, (int, float)) and not np.isnan(float(v)):
                            accumulated[k].append(float(v))
            except Exception:
                continue
        avg = {k: round(sum(v) / len(v), 2) if v else 0.0 for k, v in accumulated.items()}
        _league_avg_cache[competition] = avg
        return avg
    except Exception:
        return {}


def _build_entries(te: pd.DataFrame, zone: str = 'final_third') -> pd.DataFrame:
    te_full = te.sort_values(['period_id', 'time_min', 'time_sec']).reset_index(drop=True)
    relevant_types = ['Pass', 'Take On', 'Ball touch']
    ev = (te_full[te_full['event_type'].isin(relevant_types)]
          .dropna(subset=['x', 'y'])
          .reset_index())
    entries = []
    for i in range(len(ev)):
        row = ev.iloc[i]
        etype = row['event_type']
        start_x = float(row['x'])
        if etype == 'Pass':
            if pd.notna(row.get('Pass End X')):
                end_x = float(row['Pass End X'])
                end_y = float(row['Pass End Y'])
            else:
                continue
        else:
            if i + 1 < len(ev):
                nxt = ev.iloc[i + 1]
                end_x = float(nxt['x'])
                end_y = float(nxt['y'])
            else:
                continue
        start_y = float(row['y'])
        dest_zone = None
        region = None
        if zone == 'final_third':
            if not (start_x < 66.67 and end_x >= 66.67):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')
        elif zone == 'zone14':
            in_z14 = (66.67 <= end_x <= 83.33) and (37 <= end_y <= 63)
            in_lhs = (end_x > 66.67) and (63 < end_y <= 79)
            in_rhs = (end_x > 66.67) and (21 <= end_y < 37)
            if not (in_z14 or in_lhs or in_rhs):
                continue
            dest_zone = ('Left Band'   if end_y > 66.67
                         else 'Right Band' if end_y < 33.33
                         else 'Centre Band')
            region = 'Zone 14' if in_z14 else ('Left HS' if in_lhs else 'Right HS')
        label_map = {'Pass': 'Pass', 'Take On': 'Dribble', 'Ball touch': 'Carry'}
        outcome  = row.get('outcome', None)
        time_min = row.get('time_min', 0)
        time_sec = row.get('time_sec', 0)
        te_idx   = int(row['index'])
        next_5   = te_full.iloc[te_idx + 1 : te_idx + 6]
        led_to_shot = bool(next_5['event_type'].isin(SHOT_TYPES).any()) if not next_5.empty else False
        led_to_goal = bool((next_5['event_type'] == 'Goal').any())      if not next_5.empty else False
        receiver_name = ''
        if etype == 'Pass' and outcome == 1 and te_idx + 1 < len(te_full):
            nxt_full = te_full.iloc[te_idx + 1]
            if pd.notna(nxt_full.get('player_name')):
                receiver_name = str(nxt_full['player_name'])
        entries.append({
            'player_name':   row.get('player_name', ''),
            'event_label':   label_map.get(etype, etype),
            'x': start_x, 'y': start_y, 'end_x': end_x, 'end_y': end_y,
            'outcome': outcome, 'time_min': time_min, 'time_sec': time_sec,
            'period_id':     row.get('period_id', 0),
            'dest_zone':     dest_zone,
            'region':        region,
            'led_to_shot':   led_to_shot,
            'led_to_goal':   led_to_goal,
            'receiver_name': receiver_name,
        })
    if not entries:
        return pd.DataFrame(columns=[
            'player_name', 'event_label', 'x', 'y', 'end_x', 'end_y',
            'outcome', 'time_min', 'time_sec', 'period_id', 'dest_zone', 'region',
            'led_to_shot', 'led_to_goal', 'receiver_name',
        ])
    return pd.DataFrame(entries)


def _compute(events: pd.DataFrame) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    out = {}
    for pos, team in (('home', home_team), ('away', away_team)):
        te = events[events['team_position'] == pos].copy().reset_index(drop=True)
        for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
            if col in te.columns:
                te[col] = pd.to_numeric(te[col], errors='coerce')
        passes   = te[te['event_type'] == 'Pass']
        succ_p   = passes[passes['outcome'] == 1]
        carries  = te[te['event_type'] == 'Ball touch']
        dribbles = te[te['event_type'] == 'Take On']
        succ_d   = dribbles[dribbles['outcome'] == 1]
        total_p = len(passes); total_d = len(dribbles)
        into_ft = 0
        if 'Pass End X' in passes.columns:
            into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())
        nodes, edges = _build_network(te)
        combos  = _build_combos(te)
        combos3 = _build_3player_combos(te)
        combos4 = _build_4player_combos(te)
        entries_ft  = _build_entries(te, zone='final_third')
        entries_z14 = _build_entries(te, zone='zone14')
        if not dribbles.empty and 'player_name' in dribbles.columns:
            _drib_grp = (
                dribbles.groupby('player_name', as_index=False)
                .agg(attempts=('outcome', 'count'),
                     successful=('outcome', lambda s: int((s == 1).sum())))
            )
            _drib_grp['success_rate'] = (_drib_grp['successful'] / _drib_grp['attempts'] * 100).round(1)
            player_drib_stats = _drib_grp.sort_values('attempts', ascending=False).head(8).reset_index(drop=True)
        else:
            player_drib_stats = pd.DataFrame(columns=['player_name', 'attempts', 'successful', 'success_rate'])
        touches = te.dropna(subset=['x', 'y'])
        touch_x = touches['x'].tolist()
        touch_y = touches['y'].tolist()
        if not touches.empty and 'player_name' in touches.columns:
            total_t = max(len(touches), 1)
            t_h1 = touches[touches['period_id'] == 1] if 'period_id' in touches.columns else pd.DataFrame()
            t_h2 = touches[touches['period_id'] == 2] if 'period_id' in touches.columns else pd.DataFrame()
            total_h1 = max(len(t_h1), 1); total_h2 = max(len(t_h2), 1)
            g_tot = touches.groupby('player_name').size().rename('total')
            g_h1  = (t_h1.groupby('player_name').size().rename('h1')
                     if not t_h1.empty else pd.Series(dtype=float, name='h1'))
            g_h2  = (t_h2.groupby('player_name').size().rename('h2')
                     if not t_h2.empty else pd.Series(dtype=float, name='h2'))
            poss_df = pd.concat([g_tot, g_h1, g_h2], axis=1).fillna(0).reset_index()
            poss_df.columns = ['player_name', 'total', 'h1', 'h2']
            poss_df['pct']    = (poss_df['total'] / total_t  * 100).round(1)
            poss_df['pct_h1'] = (poss_df['h1']    / total_h1 * 100).round(1)
            poss_df['pct_h2'] = (poss_df['h2']    / total_h2 * 100).round(1)
            poss_df = poss_df.sort_values('pct', ascending=False).head(12).reset_index(drop=True)
        else:
            poss_df = pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2', 'pct', 'pct_h1', 'pct_h2'])
        out[pos] = {
            'team': team, 'passes': total_p,
            'pass_acc': round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
            'long_balls': _count_si(passes, 'Long ball'),
            'crosses':    _count_si(passes, 'Cross'),
            'thru_balls': _count_si(passes, 'Through ball'),
            'into_ft': into_ft, 'carries': len(carries),
            'dribbles': total_d, 'drib_succ': len(succ_d),
            'drib_acc': round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
            'player_drib_stats': player_drib_stats,
            'nodes': nodes, 'edges': edges,
            'combos': combos, 'combos3': combos3, 'combos4': combos4,
            'entries_ft': entries_ft, 'entries_z14': entries_z14,
            'touch_x': touch_x, 'touch_y': touch_y,
            'player_poss_df': poss_df,
        }
    return out


def _compute_half_stats(events: pd.DataFrame, pos: str, period: int | None = None) -> dict:
    home_team = events['home_team'].iloc[0]
    away_team = events['away_team'].iloc[0]
    team = home_team if pos == 'home' else away_team
    te = events[events['team_position'] == pos].copy()
    if period is not None:
        te = te[te['period_id'] == period]
    for col in ('x', 'y', 'Pass End X', 'Pass End Y'):
        if col in te.columns:
            te[col] = pd.to_numeric(te[col], errors='coerce')
    passes   = te[te['event_type'] == 'Pass']
    succ_p   = passes[passes['outcome'] == 1]
    carries  = te[te['event_type'] == 'Ball touch']
    dribbles = te[te['event_type'] == 'Take On']
    succ_d   = dribbles[dribbles['outcome'] == 1]
    total_p = len(passes); total_d = len(dribbles)
    into_ft = 0
    if 'Pass End X' in passes.columns:
        into_ft = int((passes['Pass End X'].dropna() > 66.67).sum())
    total_xt = round(float(add_xt_column(passes)['xT'].sum()), 3) if total_p > 0 else 0.0
    _ev_f = events.copy()
    _sc_f = [c for c in ['period_id', 'time_min', 'time_sec'] if c in _ev_f.columns]
    if _sc_f:
        _ev_f = _ev_f.sort_values(_sc_f).reset_index(drop=True)
    if period is not None and 'period_id' in _ev_f.columns:
        _ev_f = _ev_f[_ev_f['period_id'] == period]
    if 'team_position' in _ev_f.columns and not _ev_f.empty:
        _is_t  = _ev_f['team_position'] == pos
        _n_poss = int((_is_t & ~_is_t.shift(1, fill_value=False)).sum())
    else:
        _n_poss = 0
    avg_passes_per_poss = round(total_p / _n_poss, 1) if _n_poss > 0 else 0.0
    _all_p = events[events['event_type'] == 'Pass'].copy()
    if period is not None and 'period_id' in _all_p.columns:
        _all_p = _all_p[_all_p['period_id'] == period]
    _all_p['x'] = pd.to_numeric(_all_p['x'], errors='coerce')
    _all_ft  = int((_all_p['x'].dropna() > 66.67).sum()) if not _all_p.empty else 0
    _team_ft = int((passes['x'].dropna() > 66.67).sum()) if total_p > 0 else 0
    field_tilt = round(_team_ft / _all_ft * 100, 1) if _all_ft > 0 else 0.0
    return {
        'team': team, 'passes': total_p,
        'pass_acc':            round(len(succ_p) / total_p * 100, 1) if total_p else 0.0,
        'avg_passes_per_poss': avg_passes_per_poss,
        'field_tilt':          field_tilt,
        'long_balls':          _count_si(passes, 'Long ball'),
        'crosses':             _count_si(passes, 'Cross'),
        'thru_balls':          _count_si(passes, 'Through ball'),
        'into_ft':             into_ft,
        'total_xt':            total_xt,
        'carries':             len(carries),
        'dribbles':            total_d,
        'drib_succ':           len(succ_d),
        'drib_acc':            round(len(succ_d) / total_d * 100, 1) if total_d else 0.0,
    }


_PITCH_HEIGHT = 480

_ENTRY_COLORS = {
    'Pass':    '#32cd32',
    'Dribble': '#ffa500',
    'Carry':   '#00bfff',
}

_BAND_COLORS = {
    'Left Band':   '#00ffff',
    'Centre Band': '#ff1493',
    'Right Band':  '#ffd700',
}


def _hex_to_rgba(hex_color: str, alpha: float = 0.12) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'rgba({r},{g},{b},{alpha})'
    except (ValueError, IndexError):
        return f'rgba(128,128,128,{alpha})'


def _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team) -> go.Figure:
    labels = [lbl for lbl, _ in _RADAR_KEYS]
    keys   = [k   for _,   k in _RADAR_KEYS]

    def _raw(stats):
        return [float(stats.get(k, 0) or 0) for k in keys]

    hv = _raw(home_stats); av = _raw(away_stats)
    lv = _raw(league_avg) if league_avg else None
    norm_h, norm_a, norm_l = [], [], []
    for i in range(len(keys)):
        candidates = [hv[i], av[i]] + ([lv[i]] if lv else [])
        max_v = max(candidates) if max(candidates) > 0 else 1.0
        norm_h.append(round(hv[i] / max_v * 100, 1))
        norm_a.append(round(av[i] / max_v * 100, 1))
        if lv:
            norm_l.append(round(lv[i] / max_v * 100, 1))
    labels_c = labels + [labels[0]]; norm_h_c = norm_h + [norm_h[0]]; norm_a_c = norm_a + [norm_a[0]]
    hv_c = hv + [hv[0]]; av_c = av + [av[0]]
    if lv:
        norm_l_c = norm_l + [norm_l[0]]; lv_c = lv + [lv[0]]

    def _fmt(v):
        return f'{v:.1f}' if v != int(v) else str(int(v))

    fig = go.Figure()
    if lv:
        fig.add_trace(go.Scatterpolar(
            r=norm_l_c, theta=labels_c, mode='lines', name='League Avg',
            line=dict(color=GOLD, width=1.5, dash='dot'), opacity=0.85,
            customdata=[[_fmt(lv_c[i])] for i in range(len(labels_c))],
            hovertemplate='<b>League Avg</b><br>%{theta}: %{customdata[0]}<extra></extra>',
        ))
    fig.add_trace(go.Scatterpolar(
        r=norm_a_c, theta=labels_c, mode='lines+markers+text', name=away_team,
        fill='toself', fillcolor=_hex_to_rgba(AWAY_COLOR, 0.12),
        line=dict(color=AWAY_COLOR, width=2), marker=dict(size=5, color=AWAY_COLOR),
        text=[_fmt(av_c[i]) for i in range(len(labels_c))],
        textposition='bottom center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(av_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{away_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.add_trace(go.Scatterpolar(
        r=norm_h_c, theta=labels_c, mode='lines+markers+text', name=home_team,
        fill='toself', fillcolor=_hex_to_rgba(HOME_COLOR, 0.12),
        line=dict(color=HOME_COLOR, width=2), marker=dict(size=5, color=HOME_COLOR),
        text=[_fmt(hv_c[i]) for i in range(len(labels_c))],
        textposition='top center', textfont=dict(size=10, color='#FFFFFF'),
        customdata=[[_fmt(hv_c[i])] for i in range(len(labels_c))],
        hovertemplate=f'<b>{home_team}</b><br>%{{theta}}: %{{customdata[0]}}<extra></extra>',
    ))
    fig.update_layout(
        polar=dict(
            bgcolor='rgba(26,29,46,0.6)',
            radialaxis=dict(visible=True, range=[0, 105], showticklabels=False,
                            gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
            angularaxis=dict(tickfont=dict(size=10, color=COLORS['text_primary']),
                             gridcolor='rgba(255,255,255,0.08)', linecolor='rgba(255,255,255,0.08)'),
        ),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=True,
        legend=dict(x=0.5, y=-0.06, xanchor='center', yanchor='top', orientation='h',
                    font=dict(color=COLORS['text_primary'], size=11), bgcolor='rgba(0,0,0,0)'),
        height=540, margin=dict(l=80, r=80, t=30, b=80),
        hoverlabel=dict(bgcolor='#1A1D2E', font_color='white', font_size=12),
    )
    return fig


def _add_attack_direction(fig: go.Figure, **_) -> None:
    fig.add_annotation(
        x=0.5, y=1.0, xref='paper', yref='paper',
        xanchor='center', yanchor='bottom',
        text='➡ Direction of Attack', showarrow=False,
        font=dict(color='black', size=16, family='Arial'),
        align='center', bgcolor='rgba(255,255,255,0.7)', borderpad=3,
    )


def _network_fig(nodes: pd.DataFrame, edges: dict, color: str, is_home: bool = True) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)
    if edges:
        max_cnt = max(edges.values())
        for (a, b), cnt in edges.items():
            an = nodes[nodes['player_name'] == a]
            bn = nodes[nodes['player_name'] == b]
            if an.empty or bn.empty:
                continue
            x0, y0 = float(an.iloc[0]['x']), float(an.iloc[0]['y'])
            x1, y1 = float(bn.iloc[0]['x']), float(bn.iloc[0]['y'])
            width = 1.0 + (cnt / max_cnt) * 5.0
            if (b, a) in edges:
                dx, dy = x1 - x0, y1 - y0
                length = (dx**2 + dy**2) ** 0.5 or 1.0
                ox, oy = -dy / length * 2.5, dx / length * 2.5
                xm, ym = (x0 + x1) / 2 + ox, (y0 + y1) / 2 + oy
                t = np.linspace(0, 1, 25)
                cx = (1-t)**2 * x0 + 2*(1-t)*t * xm + t**2 * x1
                cy = (1-t)**2 * y0 + 2*(1-t)*t * ym + t**2 * y1
            else:
                cx, cy = [x0, x1], [y0, y1]
                xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
            fig.add_trace(go.Scatter(
                x=cx, y=cy, mode='lines',
                line=dict(color=color, width=width),
                opacity=0.55, hoverinfo='skip', showlegend=False,
            ))
            short_a = str(a).split()[-1]; short_b = str(b).split()[-1]
            fig.add_trace(go.Scatter(
                x=[xm], y=[ym], mode='markers',
                marker=dict(size=14, color='rgba(0,0,0,0)', opacity=0),
                customdata=[[short_a, short_b, cnt]],
                hovertemplate='<b>%{customdata[0]} → %{customdata[1]}</b><br>Passes: %{customdata[2]}<extra></extra>',
                showlegend=False,
            ))
    if not nodes.empty:
        fig.add_trace(go.Scatter(
            x=nodes['x'], y=nodes['y'],
            mode='markers+text',
            marker=dict(size=nodes['size'], color=color, line=dict(width=2, color='white')),
            text=nodes['label'],
            textposition='middle center',
            textfont=dict(size=8, color='white', family='Arial Black'),
            customdata=nodes[['player_name', 'involvement']].values,
            hovertemplate='<b>%{customdata[0]}</b><br>Pass involvement: %{customdata[1]:.0f} connections<extra></extra>',
            showlegend=False,
        ))
    for size, label in ((34, 'High involvement'), (22, 'Medium'), (14, 'Low')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='markers',
            marker=dict(size=size, color=color, line=dict(width=2, color='white')),
            name=label, showlegend=True, legendgroup='nodes',
        ))
    for width, label in ((6.0, 'Frequent (≥8)'), (3.5, 'Moderate (4–7)'), (1.0, 'Occasional (2–3)')):
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode='lines',
            line=dict(color=color, width=width),
            name=label, showlegend=True, legendgroup='edges',
        ))
    _add_attack_direction(fig, is_home=is_home)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(
                orientation='v', x=0.01, xanchor='left', y=0.99, yanchor='top',
                bgcolor='rgba(0,0,0,0.55)',
                font=dict(color=COLORS['text_primary'], size=9),
                itemsizing='trace',
            ),
        ),
        hovermode='closest',
    )
    return fig


def _entries_fig(entries_df: pd.DataFrame, zone: str,
                 color: str, is_home: bool = True) -> go.Figure:
    fig = go.Figure()
    add_pitch_background(fig)
    if not entries_df.empty:
        entries_df = entries_df.copy()
        entries_df['time_display'] = entries_df.apply(
            lambda r: f"{int(r['time_min'])}:{int(r['time_sec']):02d}", axis=1)
        entries_df['outcome_label'] = entries_df['outcome'].map(
            {1: '✓ Successful', 0: '✗ Unsuccessful'}).fillna('—')
        entries_df['shot_label'] = entries_df.apply(
            lambda r: '<br>⚽ Led to Goal' if r.get('led_to_goal', False)
                      else ('<br>🎯 Led to Shot' if r.get('led_to_shot', False) else ''),
            axis=1,
        )
        if 'receiver_name' not in entries_df.columns:
            entries_df['receiver_name'] = ''
        if zone == 'zone14':
            groups = [('Entries', color, entries_df)]
        elif 'dest_zone' in entries_df.columns and entries_df['dest_zone'].notna().any():
            groups = [(g, c, entries_df[entries_df['dest_zone'] == g]) for g, c in _BAND_COLORS.items()]
        else:
            groups = [(g, c, entries_df[entries_df['event_label'] == g]) for g, c in _ENTRY_COLORS.items()]
        for group_name, ecolor, subset in groups:
            if subset.empty:
                continue
            passes_sub    = subset[subset['event_label'] == 'Pass']
            nonpasses_sub = subset[subset['event_label'] != 'Pass']
            if zone == 'zone14':
                for _, row in passes_sub.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'], ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )
                if not nonpasses_sub.empty:
                    xs, ys = [], []
                    for _, row in nonpasses_sub.iterrows():
                        xs.extend([row['x'], row['end_x'], None])
                        ys.extend([row['y'], row['end_y'], None])
                    fig.add_trace(go.Scatter(
                        x=xs, y=ys, mode='lines',
                        line=dict(color=ecolor, width=2, dash='dash'),
                        showlegend=False, hoverinfo='skip',
                    ))
            else:
                for _, row in subset.iterrows():
                    fig.add_annotation(
                        x=row['end_x'], y=row['end_y'], ax=row['x'], ay=row['y'],
                        xref='x', yref='y', axref='x', ayref='y',
                        showarrow=True, arrowhead=2, arrowsize=1.5,
                        arrowwidth=2, arrowcolor=ecolor, opacity=0.65,
                    )
            legend_name = f'{group_name} ({len(subset)})'
            legend_shown = False
            if not passes_sub.empty:
                if zone == 'zone14':
                    cd = passes_sub[['player_name', 'receiver_name', 'event_label',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>Pass: %{{customdata[0]}} → %{{customdata[1]}}<br>'
                          'Time: %{customdata[3]}<br>%{customdata[4]}%{customdata[5]}<extra></extra>')
                else:
                    cd = passes_sub[['player_name', 'receiver_name',
                                     'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[0]}} → %{{customdata[1]}}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=passes_sub['end_x'], y=passes_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name, showlegend=True, legendgroup=group_name,
                ))
                legend_shown = True
            if not nonpasses_sub.empty:
                if zone == 'zone14':
                    cd = nonpasses_sub[['player_name', 'event_label',
                                        'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[1]}}: %{{customdata[0]}}<br>'
                          'Time: %{customdata[2]}<br>%{customdata[3]}%{customdata[4]}<extra></extra>')
                else:
                    cd = nonpasses_sub[['player_name', 'time_display', 'outcome_label', 'shot_label']].values
                    ht = (f'<b>{group_name}</b><br>%{{customdata[0]}}<br>'
                          'Time: %{customdata[1]}<br>%{customdata[2]}%{customdata[3]}<extra></extra>')
                fig.add_trace(go.Scatter(
                    x=nonpasses_sub['end_x'], y=nonpasses_sub['end_y'], mode='markers',
                    marker=dict(size=8, color=ecolor, line=dict(width=1.5, color='white')),
                    customdata=cd, hovertemplate=ht,
                    name=legend_name if not legend_shown else '',
                    showlegend=not legend_shown, legendgroup=group_name,
                ))
    if zone == 'final_third':
        fig.add_shape(type='line', x0=66.67, y0=0, x1=66.67, y1=100,
                      line=dict(color='yellow', width=2, dash='dash'))
        for y_val in (66.67, 33.33):
            fig.add_shape(type='line', x0=0, y0=y_val, x1=100, y1=y_val,
                          line=dict(color='white', width=1.5, dash='dot'))
        for y_val, lbl, clr in ((83, 'Left Band', '#00ffff'), (50, 'Centre Band', '#ff1493'), (17, 'Right Band', '#ffd700')):
            fig.add_annotation(x=4, y=y_val, text=lbl, showarrow=False,
                               font=dict(color=clr, size=9, family='Arial Black'),
                               bgcolor='rgba(0,0,0,0.5)', borderpad=2)
    elif zone == 'zone14':
        fig.add_shape(type='rect', x0=66.67, y0=37, x1=83.33, y1=63,
                      line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
                      fillcolor='rgba(255,255,255,0.03)')
        for y0, y1 in ((63, 79), (21, 37)):
            fig.add_shape(type='rect', x0=66.67, y0=y0, x1=100, y1=y1,
                          line=dict(color='rgba(255,255,255,0.25)', width=1, dash='dash'),
                          fillcolor='rgba(255,255,255,0.03)')
        for y_pos, lbl in ((50, 'Zone 14'), (71, 'Left HS'), (29, 'Right HS')):
            fig.add_annotation(x=75, y=y_pos, text=lbl, showarrow=False,
                               font=dict(color='rgba(255,255,255,0.45)', size=8, family='Arial'),
                               bgcolor='rgba(0,0,0,0)', borderpad=2)
    _add_attack_direction(fig, is_home=is_home)
    fig.update_layout(
        **PITCH_AXIS_FULL,
        **layout_config(
            height=_PITCH_HEIGHT, margin=dict(l=0, r=0, t=48, b=0),
            legend=dict(orientation='v', x=0.99, xanchor='right', y=0.99, yanchor='top',
                        bgcolor='rgba(0,0,0,0.55)',
                        font=dict(color=COLORS['text_primary'], size=9)),
        ),
        hovermode='closest',
    )
    return fig


_REGION_ORDER = ['Zone 14', 'Left HS', 'Right HS']


def _zone14_bar_fig(entries_df: pd.DataFrame, color: str) -> go.Figure:
    """Stacked bar of Zone 14 / half-space entries split by successful vs unsuccessful."""
    succ, unsucc = [], []
    for reg in _REGION_ORDER:
        if entries_df.empty or 'region' not in entries_df.columns:
            succ.append(0); unsucc.append(0); continue
        sub = entries_df[entries_df['region'] == reg]
        s = int((sub['outcome'] == 1).sum())
        succ.append(s)
        unsucc.append(len(sub) - s)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=_REGION_ORDER, y=succ, name='Successful', marker_color='#32cd32',
        text=[str(v) if v else '' for v in succ], textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{x}<br>Successful: %{y}<extra></extra>',
    ))
    fig.add_trace(go.Bar(
        x=_REGION_ORDER, y=unsucc, name='Unsuccessful', marker_color='#dc3545',
        text=[str(v) if v else '' for v in unsucc], textposition='inside',
        textfont=dict(color='white', size=11),
        hovertemplate='%{x}<br>Unsuccessful: %{y}<extra></extra>',
    ))
    for reg, s, u in zip(_REGION_ORDER, succ, unsucc):
        if s + u:
            fig.add_annotation(x=reg, y=s + u, text=str(s + u), showarrow=False,
                               yshift=10, font=dict(color=color, size=12, family='Arial Black'))
    fig.update_layout(
        barmode='stack', height=_PITCH_HEIGHT,
        margin=dict(l=8, r=8, t=40, b=70),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        title=dict(text='Entries by Region', x=0.5, xanchor='center',
                   font=dict(color=color, size=12)),
        legend=dict(orientation='h', x=0.5, xanchor='center', y=-0.1, yanchor='top',
                    font=dict(color=COLORS['text_primary'], size=9), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(tickfont=dict(color=COLORS['text_primary'], size=9), showgrid=False),
        yaxis=dict(tickfont=dict(color=COLORS['text_secondary'], size=9),
                   gridcolor='rgba(255,255,255,0.08)', zeroline=False),
        bargap=0.35,
    )
    return fig


def _combo_table(combos: pd.DataFrame, color: str) -> html.Div:
    if combos.empty:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    _th = {'color': COLORS['text_secondary'], 'fontSize': '0.65rem', 'fontWeight': '600',
           'padding': '5px 8px', 'borderBottom': f'1px solid {COLORS["dark_border"]}',
           'textTransform': 'uppercase'}
    header = html.Tr([html.Th('Combination', style=_th),
                      html.Th('N (1H / 2H)', style={**_th, 'textAlign': 'right'})])
    rows = []
    for i, row in combos.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        count_str = f"{int(row['Total'])} ({int(row['H1'])} / {int(row['H2'])})"
        rows.append(html.Tr([
            html.Td(row['Combo'], style={'color': color, 'fontSize': '0.78rem',
                                        'padding': '4px 8px', 'fontWeight': '500'}),
            html.Td(count_str, style={'color': COLORS['text_primary'], 'fontSize': '0.78rem',
                                      'padding': '4px 8px', 'textAlign': 'right', 'fontWeight': '600'}),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


def _pitch_card(title: str, fig: go.Figure, color: str) -> dbc.Col:
    return dbc.Col(
        html.Div([
            html.Div(title, style={'color': color, 'fontWeight': '600',
                                   'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dcc.Graph(figure=fig, config=CHART_CONFIG),
        ], style=CARD_STYLE),
        md=6, className='mb-3',
    )


def _build_player_entries_table(entries_ft: pd.DataFrame, entries_z14: pd.DataFrame) -> pd.DataFrame:
    def _counts(df: pd.DataFrame, zone_filter=None) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        d = df.copy()
        if zone_filter is not None:
            d = d[d['dest_zone'] == zone_filter]
        if d.empty:
            return pd.DataFrame(columns=['player_name', 'total', 'h1', 'h2'])
        grp = d.groupby('player_name')
        total = grp.size().rename('total')
        h1 = grp.apply(lambda g: (g['period_id'] == 1).sum()).rename('h1')
        h2 = grp.apply(lambda g: (g['period_id'] == 2).sum()).rename('h2')
        return pd.concat([total, h1, h2], axis=1).reset_index()
    ft = _counts(entries_ft)
    lb = _counts(entries_z14, 'Left Band')
    cb = _counts(entries_z14, 'Centre Band')
    rb = _counts(entries_z14, 'Right Band')
    all_players: set = set()
    for df in [ft, lb, cb, rb]:
        if not df.empty:
            all_players.update(df['player_name'].tolist())
    if not all_players:
        return pd.DataFrame()
    result = pd.DataFrame({'player_name': sorted(all_players)})
    for prefix, df in [('ft', ft), ('lb', lb), ('cb', cb), ('rb', rb)]:
        if df.empty:
            result[f'{prefix}_total'] = 0; result[f'{prefix}_h1'] = 0; result[f'{prefix}_h2'] = 0
        else:
            merged = result.merge(df.rename(columns={'total': f'{prefix}_total',
                                                      'h1': f'{prefix}_h1',
                                                      'h2': f'{prefix}_h2'}),
                                  on='player_name', how='left')
            result = merged.fillna(0)
            for c in [f'{prefix}_total', f'{prefix}_h1', f'{prefix}_h2']:
                result[c] = result[c].astype(int)
    result['_grand_total'] = (result['ft_total'] + result['lb_total']
                               + result['cb_total'] + result['rb_total'])
    result = (result[result['_grand_total'] > 0]
              .sort_values('_grand_total', ascending=False)
              .drop(columns='_grand_total').reset_index(drop=True))
    return result


def _player_entries_table(df: pd.DataFrame, color: str) -> html.Div:
    _hdr = {'textAlign': 'center', 'padding': '6px 8px', 'fontSize': '0.63rem', 'fontWeight': '700',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.06em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}', 'whiteSpace': 'nowrap'}
    _lbl = {'padding': '5px 8px', 'fontSize': '0.77rem', 'color': COLORS['text_primary'],
            'whiteSpace': 'nowrap', 'maxWidth': '150px', 'overflow': 'hidden', 'textOverflow': 'ellipsis'}
    _val = {'textAlign': 'center', 'padding': '5px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    if df.empty:
        return html.Div('No entry data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                                'textAlign': 'center', 'marginTop': '8px'})
    def _fmt(total, h1, h2):
        return f"{int(total)}({int(h1)}/{int(h2)})"
    header = html.Tr([
        html.Th('Player', style={**_hdr, 'textAlign': 'left'}),
        html.Th('Final Third', style=_hdr), html.Th('Left Band', style=_hdr),
        html.Th('Centre Band', style=_hdr), html.Th('Right Band', style=_hdr),
    ])
    rows = []
    for i, row in df.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        short_name = str(row['player_name']).split()[-1] if pd.notna(row['player_name']) else '—'
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(_fmt(row['ft_total'], row['ft_h1'], row['ft_h2']), style=_val),
            html.Td(_fmt(row['lb_total'], row['lb_h1'], row['lb_h2']), style=_val),
            html.Td(_fmt(row['cb_total'], row['cb_h1'], row['cb_h2']), style=_val),
            html.Td(_fmt(row['rb_total'], row['rb_h1'], row['rb_h2']), style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


def _short_name(name) -> str:
    """'Marcus Rashford' -> 'M Rashford'; single-token names returned as-is."""
    if not isinstance(name, str) or not name.strip():
        return '—'
    parts = name.split()
    if len(parts) == 1:
        return parts[0]
    return f'{parts[0][0]} {parts[-1]}'


def _connections_table(edges: dict, color: str) -> html.Div:
    if not edges:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    top = sorted(edges.items(), key=lambda kv: kv[1], reverse=True)[:5]
    _hdr = {'fontSize': '0.63rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.04em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}', 'whiteSpace': 'nowrap'}
    _lbl = {'padding': '4px 8px', 'fontSize': '0.76rem', 'whiteSpace': 'nowrap'}
    _val = {'textAlign': 'right', 'padding': '4px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([html.Th('Connection', style={**_hdr, 'textAlign': 'left'}),
                      html.Th('Passes', style={**_hdr, 'textAlign': 'right'})])
    rows = []
    for i, ((a, b), cnt) in enumerate(top):
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        combo = f'{_short_name(a)} → {_short_name(b)}'
        rows.append(html.Tr([
            html.Td(combo, style={**_lbl, 'color': color}),
            html.Td(str(int(cnt)), style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div([
        html.Div('Top Connections', style={'color': color, 'fontWeight': '700', 'fontSize': '0.7rem',
                 'textTransform': 'uppercase', 'letterSpacing': '0.04em', 'marginBottom': '6px'}),
        html.Table([html.Thead(header), html.Tbody(rows)],
                   style={'width': '100%', 'borderCollapse': 'collapse'}),
    ], style={'overflowX': 'auto'})


def _player_possession_table(poss_df: pd.DataFrame, color: str) -> html.Div:
    if poss_df.empty:
        return html.Div('No data', style={'color': COLORS['text_secondary'], 'fontSize': '0.8rem',
                                          'textAlign': 'center', 'marginTop': '12px'})
    _hdr = {'fontSize': '0.65rem', 'fontWeight': '700', 'padding': '5px 8px',
            'color': COLORS['text_secondary'], 'textTransform': 'uppercase', 'letterSpacing': '0.04em',
            'borderBottom': f'1px solid {COLORS["dark_border"]}'}
    _lbl = {'padding': '4px 8px', 'fontSize': '0.77rem', 'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    _val = {'textAlign': 'right', 'padding': '4px 8px', 'fontSize': '0.76rem', 'fontWeight': '600',
            'color': COLORS['text_primary'], 'whiteSpace': 'nowrap'}
    header = html.Tr([html.Th('Player', style={**_hdr, 'textAlign': 'left'}),
                      html.Th('Touch %', style={**_hdr, 'textAlign': 'right'})])
    rows = []
    for i, row in poss_df.iterrows():
        bg = COLORS.get('dark_tertiary', 'rgba(255,255,255,0.03)') if i % 2 == 0 else 'transparent'
        short_name = _short_name(row['player_name'])
        pct_str = f"{row['pct']}% ({row['pct_h1']}%/{row['pct_h2']}%)"
        rows.append(html.Tr([
            html.Td(short_name, style={**_lbl, 'color': color}),
            html.Td(pct_str, style=_val),
        ], style={'backgroundColor': bg}))
    return html.Div(html.Table([html.Thead(header), html.Tbody(rows)],
                               style={'width': '100%', 'borderCollapse': 'collapse'}),
                    style={'overflowX': 'auto'})


_BUP_METRICS = [
    ('Total Passes',     'passes',              False),
    ('Pass Accuracy',    'pass_acc',            True),
    ('Field Tilt',       'field_tilt',          True),
    ('Avg Passes/Poss',  'avg_passes_per_poss', False),
    ('Positional xT',    'total_xt',            False),
    ('Into Final Third', 'into_ft',    False),
    ('Long Balls',       'long_balls', False),
    ('Crosses',          'crosses',    False),
    ('Through Balls',    'thru_balls', False),
    ('Ball Carries',     'carries',    False),
    ('Dribble Attempts', 'dribbles',   False),
    ('Dribbles Won',     'drib_succ',  False),
    ('Dribble Success',  'drib_acc',   True),
]


def _render_radar(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.Div()
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = _compute_half_stats(events, 'home')
    away_stats = _compute_half_stats(events, 'away')
    league_avg = _compute_league_avg(events)
    fig = _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)
    return html.Div([
        section_header('Build-Up Radar'),
        build_info_box('Each axis scaled 0–100 relative to the highest value among home, away, and league average. '
                       'Hover a point for the actual value.'),
        dcc.Graph(figure=fig, config=CHART_CONFIG),
    ], style={'marginBottom': '36px'})


def _render_stats(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    h_full = _compute_half_stats(events, 'home')
    h_h1   = _compute_half_stats(events, 'home', 1)
    h_h2   = _compute_half_stats(events, 'home', 2)
    a_full = _compute_half_stats(events, 'away')
    a_h1   = _compute_half_stats(events, 'away', 1)
    a_h2   = _compute_half_stats(events, 'away', 2)
    return html.Div([
        section_header('Pass / Carry / Dribble Stats'),
        build_info_box('Performance breakdown by half — Passing, Carries & Dribbles'),
        dbc.Row([
            dbc.Col(build_team_stats_table(h_full['team'], HOME_COLOR, _BUP_METRICS, h_full, h_h1, h_h2),
                    md=6, className='mb-3'),
            dbc.Col(build_team_stats_table(a_full['team'], AWAY_COLOR, _BUP_METRICS, a_full, a_h1, a_h2),
                    md=6, className='mb-3'),
        ], className='g-3'),
    ], style={'marginBottom': '8px'})


def _render_possession(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']

    def _heatmap_card(team, color, touch_x, touch_y, poss_df):
        img_src = render_lsc_heatmap_img(touch_x, touch_y, GOLD)
        return html.Div([
            html.Div(team, style={'color': color, 'fontWeight': '700',
                                  'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(html.Img(src=img_src, style={'width': '100%', 'borderRadius': '6px'}), md=8),
                dbc.Col(html.Div(_player_possession_table(poss_df, color),
                                 style={'overflowY': 'auto', 'maxHeight': '420px'}), md=4),
            ], className='g-2', align='start'),
        ], style=CARD_STYLE)

    heatmap_row = dbc.Row([
        dbc.Col(_heatmap_card(hs['team'], HOME_COLOR, hs['touch_x'], hs['touch_y'], hs['player_poss_df']),
                md=6, className='mb-3'),
        dbc.Col(_heatmap_card(as_['team'], AWAY_COLOR, as_['touch_x'], as_['touch_y'], as_['player_poss_df']),
                md=6, className='mb-3'),
    ], className='g-3')
    return html.Div([
        section_header('Possession Touch Map'),
        build_info_box('Touch density across the pitch — darker = more activity. '
                       'Player touch share (% of team touches) shown alongside · format: total% (1H%/2H%).'),
        heatmap_row,
    ], style={'marginBottom': '36px'})


def _render_network(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']

    def _team_block(team, color, nodes, edges, is_home):
        return dbc.Col([
            html.Div(team, style={'color': color, 'fontWeight': '700',
                                  'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=_network_fig(nodes, edges, color, is_home=is_home),
                                  config=CHART_CONFIG), md=9),
                dbc.Col(html.Div(_connections_table(edges, color),
                                 style={'overflowY': 'auto', 'maxHeight': '420px'}), md=3),
            ], className='g-2', align='start'),
        ], md=6, className='mb-3', style=CARD_STYLE)

    return html.Div([
        section_header('Pass Network'),
        build_info_box('Node size = pass involvement · Edge width = connection frequency · '
                       'Hover nodes/edges for details · Top 5 passer → receiver connections shown alongside'),
        dbc.Row([
            _team_block(hs['team'], HOME_COLOR, hs['nodes'], hs['edges'], is_home=True),
            _team_block(as_['team'], AWAY_COLOR, as_['nodes'], as_['edges'], is_home=False),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _render_combos(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']

    def _combo_section(title, info, combo_key):
        return html.Div([
            section_header(title),
            build_info_box(info),
            dbc.Row([
                dbc.Col(html.Div([
                    html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                               'fontSize': '0.85rem', 'marginBottom': '8px'}),
                    _combo_table(hs[combo_key], HOME_COLOR),
                ], style=CARD_STYLE), md=6, className='mb-3'),
                dbc.Col(html.Div([
                    html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                                'fontSize': '0.85rem', 'marginBottom': '8px'}),
                    _combo_table(as_[combo_key], AWAY_COLOR),
                ], style=CARD_STYLE), md=6, className='mb-3'),
            ], className='g-3'),
        ], style={'marginBottom': '24px'})

    return html.Div([
        _combo_section('Top Combinations', 'Most frequent passer → receiver combinations · N (1H / 2H)', 'combos'),
        _combo_section('Top 3-Player Combinations', 'Most frequent three-player passing chains (A → B → C) · N (1H / 2H)', 'combos3'),
        _combo_section('Top 4-Player Combinations', 'Most frequent four-player passing chains (A → B → C → D) · N (1H / 2H)', 'combos4'),
    ])


def _render_entries(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    def _entry_card(team, entries_df, color, is_home):
        total = len(entries_df)
        return dbc.Col(html.Div([
            html.Div(f"{team} ({total} entries)", style={'color': color, 'fontWeight': '600',
                     'fontSize': '0.85rem', 'marginBottom': '8px', 'textAlign': 'center'}),
            dbc.Row([
                dbc.Col(dcc.Graph(figure=_entries_fig(entries_df, 'zone14', color, is_home=is_home),
                                  config=CHART_CONFIG), md=9),
                dbc.Col(dcc.Graph(figure=_zone14_bar_fig(entries_df, color),
                                  config=CHART_CONFIG), md=3),
            ], className='g-2', align='start'),
        ], style=CARD_STYLE), md=6, className='mb-3')

    return html.Div([
        section_header('Zone 14 Entries'),
        build_info_box('Passes (solid arrows), dribbles and carries (dashed lines) ending in Zone 14, '
                       'Left Half Space (y 63–79) or Right Half Space (y 21–37). '
                       'Bars show entry counts per region, split successful (green) vs unsuccessful (red).'),
        dbc.Row([
            _entry_card(hs['team'], hs['entries_z14'], HOME_COLOR, is_home=True),
            _entry_card(as_['team'], as_['entries_z14'], AWAY_COLOR, is_home=False),
        ], className='g-3'),
    ], style={'marginBottom': '36px'})


def _render_tables(events: pd.DataFrame) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    d   = _compute(events)
    hs  = d['home']
    as_ = d['away']
    home_df = _build_player_entries_table(hs['entries_ft'], hs['entries_z14'])
    away_df = _build_player_entries_table(as_['entries_ft'], as_['entries_z14'])
    return html.Div([
        section_header('Player Zone Entries'),
        build_info_box('Final Third entries per player broken down by band — format: total(1H/2H)'),
        dbc.Row([
            dbc.Col(html.Div([
                html.Div(hs['team'], style={'color': HOME_COLOR, 'fontWeight': '700',
                                           'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _player_entries_table(home_df, HOME_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
            dbc.Col(html.Div([
                html.Div(as_['team'], style={'color': AWAY_COLOR, 'fontWeight': '700',
                                            'fontSize': '0.85rem', 'marginBottom': '8px'}),
                _player_entries_table(away_df, AWAY_COLOR),
            ], style=CARD_STYLE), md=6, className='mb-3'),
        ], className='g-3'),
    ])


def build_build_up_passing_tab(events: pd.DataFrame, **_) -> html.Div:
    if events.empty:
        return html.P('No event data.', style={'color': COLORS['text_secondary']})
    return html.Div([
        _render_possession(events),
        _render_network(events),
        _render_entries(events),
    ], style={'marginTop': '16px'})


def build_bup_radar(events: pd.DataFrame):
    if events.empty:
        return None
    home_team  = str(events['home_team'].iloc[0]) if 'home_team' in events.columns else 'Home'
    away_team  = str(events['away_team'].iloc[0]) if 'away_team' in events.columns else 'Away'
    home_stats = _compute_half_stats(events, 'home')
    away_stats = _compute_half_stats(events, 'away')
    league_avg = _compute_league_avg(events)
    return _build_radar_fig(home_stats, away_stats, league_avg, home_team, away_team)


def register_build_up_passing_callbacks(app) -> None:
    # Half filter removed — entries render statically inside build_build_up_passing_tab.
    return None
