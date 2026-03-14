# shot_animation.py
# Animated shot sequence viewer – adapted from G4_ahot animated sequence.ipynb
# Fixed for: parquet data source, correct column names, Python 3.9 compatibility

from __future__ import annotations
from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go

import dash
from dash import html, dcc, dash_table
from dash.dependencies import Input, Output

# ============================================================
# 1. CONFIG & DATA LOADING
# ============================================================

PARQUET_PATH = (
    "data/barcelona/result/Spain_Copa_del_Rey/2025-2026/match_event/"
    "2026-03-03_BAR_vs_ATM_3gqwvmig5roaq4qkddtgvp8gk.parquet"
)

PITCH_LENGTH = 105
PITCH_WIDTH  = 68

# Real goal dimensions
GOAL_WIDTH_M  = 7.32
GOAL_DEPTH_M  = 2.0
GOAL_MARGIN_X = 0.2

# Opta goal mouth column
GOAL_MOUTH_Y_COL = "Goal Mouth Y Coordinate"

# Goal mouth range in Opta 0-100 scale
GOAL_MOUTH_LEFT_OPT        = 45.2
GOAL_MOUTH_RIGHT_OPT       = 54.8
GOAL_MOUTH_CENTER_OPT      = 50.0
GOAL_MOUTH_HALF_SPAN_OPT   = GOAL_MOUTH_RIGHT_OPT - GOAL_MOUTH_CENTER_OPT  # ~4.8

IGNORED_MACRO_CATEGORIES = {"match_admin", "stoppage_restart", "feed_meta"}
IGNORED_EVENT_NAMES = {"deleted event"}

SHOT_EVENTS = [
    "Miss",
    "Post",
    "Saved Shot",
    "Goal",
]

GOAL_EVENTS = {"Goal"}


def _ev_lower(ev) -> str:
    if not isinstance(ev, str):
        return ""
    return ev.lower()


def is_shot_event(ev: str) -> bool:
    if ev in SHOT_EVENTS:
        return True
    return "shot" in _ev_lower(ev)


# ------- Load parquet -------
df = pd.read_parquet(PARQUET_PATH)
df = df.reset_index(drop=False).rename(columns={"index": "row_index"})

# Rename event_type → event to match the rest of the code
df = df.rename(columns={"event_type": "event"})

# Fix "N/A" strings in Pass End X/Y
df["Pass End X"] = pd.to_numeric(df["Pass End X"], errors="coerce")
df["Pass End Y"] = pd.to_numeric(df["Pass End Y"], errors="coerce")

# Goal Mouth Y/Z – ensure numeric
df[GOAL_MOUTH_Y_COL] = pd.to_numeric(df[GOAL_MOUTH_Y_COL], errors="coerce")
df["Goal Mouth Z Coordinate"] = pd.to_numeric(df["Goal Mouth Z Coordinate"], errors="coerce")

# macro_category – not available in this parquet; set to NaN
df["macro_category"] = np.nan

# ============================================================
# 1.b – COORDINATE CONVERSION
# ============================================================

def opta_to_meters_x(x):
    return x * PITCH_LENGTH / 100.0

def opta_to_meters_y(y):
    return y * PITCH_WIDTH / 100.0

df["x_m"] = opta_to_meters_x(df["x"].clip(0, 100))
df["y_m"] = opta_to_meters_y(df["y"].clip(0, 100))

df["pass_end_x_m"] = opta_to_meters_x(df["Pass End X"].clip(0, 100))
df["pass_end_y_m"] = opta_to_meters_y(df["Pass End Y"].clip(0, 100))

# All teams normalised so they attack left → right
df["x_plot_m"]          = df["x_m"]
df["y_plot_m"]          = df["y_m"]
df["pass_end_x_plot_m"] = df["pass_end_x_m"]
df["pass_end_y_plot_m"] = df["pass_end_y_m"]

mask_away = (df["team_position"] == "away")
df.loc[mask_away, "x_plot_m"]          = PITCH_LENGTH - df.loc[mask_away, "x_m"]
df.loc[mask_away, "y_plot_m"]          = PITCH_WIDTH  - df.loc[mask_away, "y_m"]
df.loc[mask_away, "pass_end_x_plot_m"] = PITCH_LENGTH - df.loc[mask_away, "pass_end_x_m"]
df.loc[mask_away, "pass_end_y_plot_m"] = PITCH_WIDTH  - df.loc[mask_away, "pass_end_y_m"]


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def has_valid_player_name(row_or_value) -> bool:
    if isinstance(row_or_value, pd.Series):
        pname = row_or_value.get("player_name", "")
    else:
        pname = row_or_value
    if pd.isna(pname):
        return False
    pname_str = str(pname).strip()
    if not pname_str:
        return False
    if pname_str.lower() in {"nan", "none"}:
        return False
    return True


def is_shot_saved_generic(row: pd.Series) -> bool:
    ev_low = _ev_lower(row.get("event", ""))
    if ("shot" not in ev_low) and (row.get("event") not in SHOT_EVENTS):
        return False
    if any(k in ev_low for k in ["saved shot", "saved", "save", "block", "blocked"]) and "goal" not in ev_low:
        return True
    outcome = str(row.get("outcome", "")).lower()
    keywords = ["saved", "save", "blocked", "block"]
    return any(kw in outcome for kw in keywords)


def is_goal_row(row: pd.Series) -> bool:
    return str(row.get("event", "")) in GOAL_EVENTS


def is_shot_off_target(row: pd.Series) -> bool:
    if is_goal_row(row):
        return False
    if is_shot_saved_generic(row):
        return False
    ev = str(row.get("event", ""))
    if ev in {"Miss", "Post"}:
        return True
    return False


def compute_shot_end_coordinates_default(row: pd.Series):
    x0 = float(row.get("x_plot_m", np.nan))
    y0 = float(row.get("y_plot_m", np.nan))

    x_end = row.get("pass_end_x_plot_m", np.nan)
    y_end = row.get("pass_end_y_plot_m", np.nan)

    if not pd.isna(x_end) and not pd.isna(y_end):
        return float(x_end), float(y_end)

    team_pos = row.get("team_position", "home")
    if team_pos == "home":
        goal_x_front = PITCH_LENGTH - GOAL_MARGIN_X
    else:
        goal_x_front = 0.0 + GOAL_MARGIN_X

    if (GOAL_MOUTH_Y_COL in row.index) and (not pd.isna(row.get(GOAL_MOUTH_Y_COL))):
        gm_y = float(row[GOAL_MOUTH_Y_COL])
        gm_y_clamped = min(max(gm_y, GOAL_MOUTH_LEFT_OPT), GOAL_MOUTH_RIGHT_OPT)
        rel_opt = (gm_y_clamped - GOAL_MOUTH_CENTER_OPT) / GOAL_MOUTH_HALF_SPAN_OPT

        goal_center_y = PITCH_WIDTH / 2.0
        goal_half_w   = GOAL_WIDTH_M / 2.0

        goal_y_raw = goal_center_y + rel_opt * goal_half_w
        goal_y = goal_y_raw if team_pos == "home" else PITCH_WIDTH - goal_y_raw
    else:
        goal_y = y0

    return goal_x_front, goal_y


def _iter_events_after_row(row_index: int):
    tail = df[df["row_index"] > row_index].sort_values("row_index")
    for _, r in tail.iterrows():
        yield r


def get_next_event_for_shot_row(shot_row: pd.Series) -> Optional[pd.Series]:
    idx = int(shot_row["row_index"])
    for r in _iter_events_after_row(idx):
        cat = str(r.get("macro_category", "")).strip().lower()
        if cat in IGNORED_MACRO_CATEGORIES:
            continue
        ev_low = str(r.get("event", "")).strip().lower()
        if ev_low in IGNORED_EVENT_NAMES:
            continue
        if not has_valid_player_name(r):
            continue
        return r
    return None


def find_next_save_event_for_shot(shot_row: pd.Series) -> Optional[pd.Series]:
    if "row_index" in shot_row.index:
        start_idx = int(shot_row["row_index"])
    else:
        start_idx = int(shot_row.name)

    shot_team_pos = shot_row.get("team_position")
    tail = df[df["row_index"] > start_idx].copy()
    if tail.empty:
        return None

    ev_low_series = tail["event"].astype(str).str.lower()
    mask_save_word = (
        ev_low_series.str.contains("save", na=False) |
        ev_low_series.str.contains("safe", na=False) |
        ev_low_series.str.contains("block", na=False)
    )

    mask_rival = (
        (tail["team_position"] != shot_team_pos)
        if isinstance(shot_team_pos, str) and "team_position" in tail.columns
        else pd.Series(True, index=tail.index)
    )

    mask_player_ok = tail.apply(has_valid_player_name, axis=1)
    mask_not_deleted = ~tail.apply(is_deleted_row, axis=1)

    mask1 = mask_save_word & mask_rival & mask_player_ok & mask_not_deleted
    candidates = tail[mask1].sort_values("row_index")
    if not candidates.empty:
        return candidates.iloc[0]

    if not is_shot_saved_generic(shot_row):
        return None

    for _, r in tail.sort_values("row_index").iterrows():
        if is_deleted_row(r):
            continue
        if not has_valid_player_name(r):
            continue
        if isinstance(shot_team_pos, str) and "team_position" in r.index:
            if r.get("team_position") == shot_team_pos:
                continue
        return r

    return None


def compute_shot_ball_end_for_timeline(
    this: pd.Series,
    is_trigger_row: bool,
    shot_saved: bool,
    focus_type: str,
):
    end_x, end_y = compute_shot_end_coordinates_default(this)

    if not is_goal_row(this):
        next_ev = get_next_event_for_shot_row(this)
        if next_ev is not None:
            ne_x = next_ev.get("x_plot_m")
            ne_y = next_ev.get("y_plot_m")
            if not pd.isna(ne_x) and not pd.isna(ne_y):
                end_x, end_y = float(ne_x), float(ne_y)

    if is_trigger_row and shot_saved:
        save_row = find_next_save_event_for_shot(this)
        if save_row is not None:
            pos = str(save_row.get("position", "")).upper()
            if focus_type == "saved_gk" and pos == "GK":
                end_x = save_row["x_plot_m"]
                end_y = save_row["y_plot_m"]
            elif focus_type == "blocked" and pos != "GK":
                end_x = save_row["x_plot_m"]
                end_y = save_row["y_plot_m"]

    return end_x, end_y


def is_error_event(ev: str) -> bool:
    ev_low = _ev_lower(ev)
    return ("error" in ev_low) or ("clearance" in ev_low)


def is_foul_event(ev: str) -> bool:
    return "foul" in _ev_lower(ev)


def is_start_delay_event(ev: str) -> bool:
    return "start delay" in _ev_lower(ev)


def is_end_delay_event(ev: str) -> bool:
    return "end delay" in _ev_lower(ev)


def is_contentious_ref_event(ev: str) -> bool:
    return "contentious referee decision" in _ev_lower(ev)


def is_admin_event(ev: str) -> bool:
    return (
        is_start_delay_event(ev) or
        is_end_delay_event(ev) or
        is_contentious_ref_event(ev)
    )


def is_card_event(ev: str) -> bool:
    return "card" in _ev_lower(ev)


def is_deleted_row(row: pd.Series) -> bool:
    ev_str = str(row.get("event", "")).lower()
    if "deleted event" in ev_str:
        return True
    if ev_str in IGNORED_EVENT_NAMES:
        return True
    if "penalty faced" in ev_str:
        return True
    return False


def is_field_event_row(row: pd.Series) -> bool:
    ev = row.get("event", "")
    if is_deleted_row(row):
        return False
    if is_admin_event(ev):
        return False
    if is_card_event(ev):
        return False
    if not has_valid_player_name(row):
        return False
    return True


def is_pass_intercepted(row: pd.Series) -> bool:
    ev_low = _ev_lower(row.get("event", ""))
    if "pass" not in ev_low:
        return False
    # In this parquet, outcome=0 means unsuccessful
    outcome_val = row.get("outcome", None)
    if outcome_val is not None and not pd.isna(outcome_val):
        try:
            if int(outcome_val) == 0:
                return True
        except (ValueError, TypeError):
            pass
    return False


def is_save_like_event_row(row: pd.Series) -> bool:
    ev_low = _ev_lower(row.get("event", ""))
    return ("save" in ev_low) or ("safe" in ev_low) or ("block" in ev_low)


# ============================================================
# 3. SHOT CLASSIFICATION
# ============================================================

def classify_shot_category(row: pd.Series) -> str:
    if not is_shot_event(str(row.get("event", ""))):
        return "other_event"
    if is_goal_row(row):
        return "goal"
    if is_shot_saved_generic(row):
        save_row = find_next_save_event_for_shot(row)
        if save_row is not None:
            pos = str(save_row.get("position", "")).upper()
            if pos == "GK":
                return "saved_gk"
            else:
                return "blocked"
        else:
            return "saved_other"
    return "other_shot"


def classify_shot_text(row: pd.Series) -> str:
    cat = row.get("trigger_type", "")
    if is_goal_row(row):
        return "Goal"
    if cat == "saved_gk":
        return "Shot saved (GK)"
    if cat == "blocked":
        return "Shot blocked"
    if cat == "saved_other":
        return "Shot saved/blocked"
    if is_shot_off_target(row):
        return "Shot off target"
    return "Shot"


# Build triggers dataframe
all_shots_mask = df["event"].apply(lambda ev: is_shot_event(ev))
triggers_df = df[all_shots_mask].copy()
triggers_df = triggers_df[~triggers_df.apply(is_deleted_row, axis=1)]
triggers_df = triggers_df[triggers_df.apply(has_valid_player_name, axis=1)]

triggers_df["trigger_type"] = triggers_df.apply(classify_shot_category, axis=1)
triggers_df["shot_desc"] = triggers_df.apply(classify_shot_text, axis=1)

valid_trigger_types = {"goal", "saved_gk", "blocked", "saved_other", "other_shot"}
triggers_df = triggers_df[triggers_df["trigger_type"].isin(valid_trigger_types)]
triggers_df = triggers_df.sort_values("row_index").reset_index(drop=True)


def format_trigger_label(row):
    minute = int(row.get("time_min", 0))
    second = int(row.get("time_sec", 0))
    t_str  = f"{minute:02d}:{second:02d}"
    period = row.get("period_id", 1)
    team   = row.get("team_name", "Team")
    player = row.get("player_name", "Player")
    desc   = row.get("shot_desc", "")
    return f"{t_str} - {team} - {player} ({desc}, half {period})"


triggers_df["label"] = triggers_df.apply(format_trigger_label, axis=1)

print(f"Loaded {len(df)} events. Found {len(triggers_df)} shots.")
print(triggers_df[["time_min", "time_sec", "team_name", "player_name", "event", "trigger_type"]].to_string())


# ============================================================
# 4. NEON PITCH FIGURE
# ============================================================

def create_pitch_figure():
    fig = go.Figure()

    fig.add_shape(
        type="rect", x0=0, y0=0, x1=PITCH_LENGTH, y1=PITCH_WIDTH,
        fillcolor="#02101f", layer="below", line=dict(width=0),
    )

    stripe_width = PITCH_LENGTH / 10
    for i in range(10):
        fig.add_shape(
            type="rect",
            x0=i * stripe_width, y0=0,
            x1=(i + 1) * stripe_width, y1=PITCH_WIDTH,
            fillcolor="rgba(0, 255, 180, 0.03)" if i % 2 == 0 else "rgba(0, 180, 255, 0.03)",
            opacity=1, layer="below", line=dict(width=0),
        )

    line_color = "#00f5ff"
    box_color  = "#00ffa3"

    field_lines = [
        [[0, 0], [0, PITCH_WIDTH]],
        [[0, PITCH_WIDTH], [PITCH_LENGTH, PITCH_WIDTH]],
        [[PITCH_LENGTH, PITCH_WIDTH], [PITCH_LENGTH, 0]],
        [[PITCH_LENGTH, 0], [0, 0]],
        [[PITCH_LENGTH / 2, 0], [PITCH_LENGTH / 2, PITCH_WIDTH]],
        [[16.5, (PITCH_WIDTH / 2) - 16.5], [16.5, (PITCH_WIDTH / 2) + 16.5]],
        [[PITCH_LENGTH - 16.5, (PITCH_WIDTH / 2) - 16.5], [PITCH_LENGTH - 16.5, (PITCH_WIDTH / 2) + 16.5]],
        [[0, (PITCH_WIDTH / 2) - 16.5], [16.5, (PITCH_WIDTH / 2) - 16.5]],
        [[0, (PITCH_WIDTH / 2) + 16.5], [16.5, (PITCH_WIDTH / 2) + 16.5]],
        [[PITCH_LENGTH, (PITCH_WIDTH / 2) - 16.5], [PITCH_LENGTH - 16.5, (PITCH_WIDTH / 2) - 16.5]],
        [[PITCH_LENGTH, (PITCH_WIDTH / 2) + 16.5], [PITCH_LENGTH - 16.5, (PITCH_WIDTH / 2) + 16.5]],
        [[5.5, (PITCH_WIDTH / 2) - 5.5], [5.5, (PITCH_WIDTH / 2) + 5.5]],
        [[PITCH_LENGTH - 5.5, (PITCH_WIDTH / 2) - 5.5], [PITCH_LENGTH - 5.5, (PITCH_WIDTH / 2) + 5.5]],
        [[0, (PITCH_WIDTH / 2) - 5.5], [5.5, (PITCH_WIDTH / 2) - 5.5]],
        [[0, (PITCH_WIDTH / 2) + 5.5], [5.5, (PITCH_WIDTH / 2) + 5.5]],
        [[PITCH_LENGTH, (PITCH_WIDTH / 2) - 5.5], [PITCH_LENGTH - 5.5, (PITCH_WIDTH / 2) - 5.5]],
        [[PITCH_LENGTH, (PITCH_WIDTH / 2) + 5.5], [PITCH_LENGTH - 5.5, (PITCH_WIDTH / 2) + 5.5]],
    ]

    for line in field_lines:
        fig.add_shape(
            type="line",
            x0=line[0][0], y0=line[0][1],
            x1=line[1][0], y1=line[1][1],
            line=dict(color=line_color, width=1.8),
            layer="above",
        )

    fig.add_shape(
        type="circle",
        x0=PITCH_LENGTH / 2 - 9.15, y0=PITCH_WIDTH / 2 - 9.15,
        x1=PITCH_LENGTH / 2 + 9.15, y1=PITCH_WIDTH / 2 + 9.15,
        line=dict(color=line_color, width=1.8),
        layer="above",
    )

    for cx, cy in [
        (PITCH_LENGTH / 2, PITCH_WIDTH / 2),
        (11, PITCH_WIDTH / 2),
        (PITCH_LENGTH - 11, PITCH_WIDTH / 2),
    ]:
        fig.add_shape(
            type="circle",
            x0=cx - 0.3, y0=cy - 0.3,
            x1=cx + 0.3, y1=cy + 0.3,
            fillcolor=line_color,
            line=dict(color=line_color, width=1),
            layer="above",
        )

    goal_center_y = PITCH_WIDTH / 2.0
    goal_half_w   = GOAL_WIDTH_M / 2.0
    goal_y_bottom = goal_center_y - goal_half_w
    goal_y_top    = goal_center_y + goal_half_w

    # Right goal (home team attacks toward here)
    grxf = PITCH_LENGTH - GOAL_MARGIN_X
    grxb = grxf - GOAL_DEPTH_M
    for (x0, y0, x1, y1) in [
        (grxf, goal_y_bottom, grxb, goal_y_bottom),
        (grxf, goal_y_top,    grxb, goal_y_top),
        (grxb, goal_y_bottom, grxb, goal_y_top),
    ]:
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=box_color, width=3), layer="above")

    # Left goal (away team attacks toward here)
    glxf = 0.0 + GOAL_MARGIN_X
    glxb = glxf + GOAL_DEPTH_M
    for (x0, y0, x1, y1) in [
        (glxf, goal_y_bottom, glxb, goal_y_bottom),
        (glxf, goal_y_top,    glxb, goal_y_top),
        (glxb, goal_y_bottom, glxb, goal_y_top),
    ]:
        fig.add_shape(type="line", x0=x0, y0=y0, x1=x1, y1=y1,
                      line=dict(color=box_color, width=3), layer="above")

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[0, PITCH_LENGTH], fixedrange=True, constrain="domain"),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False,
                   range=[0, PITCH_WIDTH], fixedrange=True, scaleanchor="x", scaleratio=1),
        plot_bgcolor="#020617",
        paper_bgcolor="#020617",
        width=900,
        height=550,
        margin=dict(l=40, r=40, t=40, b=230),
        uirevision="pitch-static",
    )
    return fig


# ============================================================
# 5. BUILD TIMELINE FOR A TRIGGER
# ============================================================

def build_timeline_for_trigger(selected_row_index: int, focus_type: str) -> pd.DataFrame:
    event_row = df[df["row_index"] == selected_row_index].iloc[0]
    idx_evt   = event_row.name

    # Walk back up to 10 valid field events
    count_field = 0
    start_idx   = idx_evt
    i = idx_evt
    while i >= 0 and count_field < 10:
        row_i = df.iloc[i]
        if is_field_event_row(row_i):
            count_field += 1
            start_idx = i
        i -= 1

    window_raw = df.iloc[start_idx: idx_evt + 1].copy()
    window_raw["is_goal"] = False
    if focus_type == "goal":
        window_raw.loc[window_raw.index[-1], "is_goal"] = True

    not_deleted_mask = ~window_raw.apply(is_deleted_row, axis=1)
    valid_name_mask  = window_raw.apply(has_valid_player_name, axis=1)
    window = window_raw[not_deleted_mask & valid_name_mask].copy()
    window = window[~window["event"].astype(str).str.lower().str.contains("card")]
    window = window.reset_index(drop=True)

    if len(window) == 0:
        return pd.DataFrame()

    timeline_rows   = []
    action_counter  = 1
    prev_ball_end_x = None
    prev_ball_end_y = None
    n = len(window)

    for k in range(n):
        this   = window.iloc[k].copy()
        ev_str = str(this["event"])

        # Admin / VAR
        if is_admin_event(ev_str):
            if is_contentious_ref_event(ev_str):
                var_row              = this.copy()
                var_row["kind"]      = "var"
                var_row["event"]     = "VAR Review"
                var_row["is_goal"]   = False
                var_row["order"]     = action_counter
                action_counter      += 1
                var_row["x_plot_m"]  = PITCH_LENGTH / 2.0
                var_row["y_plot_m"]  = PITCH_WIDTH  / 2.0
                ball_x = prev_ball_end_x if prev_ball_end_x is not None else var_row["x_plot_m"]
                ball_y = prev_ball_end_y if prev_ball_end_y is not None else var_row["y_plot_m"]
                var_row["ball_start_x"]    = ball_x
                var_row["ball_start_y"]    = ball_y
                var_row["ball_end_x"]      = ball_x
                var_row["ball_end_y"]      = ball_y
                var_row["has_line"]        = False
                var_row["line_is_dashed"]  = False
                prev_ball_end_x, prev_ball_end_y = ball_x, ball_y
                timeline_rows.append(var_row)
            continue

        # Error / Clearance bridge
        if is_error_event(ev_str):
            if 0 < k < n - 1:
                nxt    = window.iloc[k + 1]
                bridge = this.copy()
                bridge["kind"]      = "error_bridge"
                bridge["is_goal"]   = False
                bridge["order"]     = action_counter
                action_counter     += 1
                start_x = prev_ball_end_x if prev_ball_end_x is not None else this["x_plot_m"]
                start_y = prev_ball_end_y if prev_ball_end_y is not None else this["y_plot_m"]
                bridge["ball_start_x"]   = start_x
                bridge["ball_start_y"]   = start_y
                bridge["ball_end_x"]     = nxt["x_plot_m"]
                bridge["ball_end_y"]     = nxt["y_plot_m"]
                bridge["has_line"]       = False
                bridge["line_is_dashed"] = False
                prev_ball_end_x, prev_ball_end_y = bridge["ball_end_x"], bridge["ball_end_y"]
                timeline_rows.append(bridge)
            continue

        # Normal event
        this_kind = "event"
        this["order"] = action_counter
        action_counter += 1

        if is_save_like_event_row(this):
            pos = str(this.get("position", "")).upper()
            this_kind = "save_gk" if pos == "GK" else "save_block"

        is_pass = (
            ev_str == "Pass"
            and not pd.isna(this["pass_end_x_plot_m"])
            and not pd.isna(this["pass_end_y_plot_m"])
        )
        is_shot      = is_shot_event(ev_str)
        shot_saved   = is_shot and is_shot_saved_generic(this)
        pass_intercepted = is_pass and is_pass_intercepted(this)

        is_trigger_row = int(this.get("row_index", this.name)) == selected_row_index

        if is_pass:
            ball_start_x = this["x_plot_m"]
            ball_start_y = this["y_plot_m"]
            ball_end_x   = this["pass_end_x_plot_m"]
            ball_end_y   = this["pass_end_y_plot_m"]
        elif is_shot:
            ball_start_x = this["x_plot_m"]
            ball_start_y = this["y_plot_m"]
            end_x, end_y = compute_shot_ball_end_for_timeline(
                this, is_trigger_row=is_trigger_row,
                shot_saved=shot_saved, focus_type=focus_type,
            )
            ball_end_x = end_x
            ball_end_y = end_y
        else:
            if k == 0 or prev_ball_end_x is None:
                ball_start_x = this["x_plot_m"]
                ball_start_y = this["y_plot_m"]
            else:
                ball_start_x = prev_ball_end_x
                ball_start_y = prev_ball_end_y
            ball_end_x = this["x_plot_m"]
            ball_end_y = this["y_plot_m"]

        this["ball_start_x"]   = ball_start_x
        this["ball_start_y"]   = ball_start_y
        this["ball_end_x"]     = ball_end_x
        this["ball_end_y"]     = ball_end_y
        this["has_line"]       = bool(is_pass or is_shot)
        this["line_is_dashed"] = bool(shot_saved or pass_intercepted)
        this["kind"]           = this_kind

        prev_ball_end_x, prev_ball_end_y = ball_end_x, ball_end_y
        timeline_rows.append(this)

        # Carry between passes (same team, consecutive)
        if k < n - 1:
            nxt       = window.iloc[k + 1]
            same_team = this["team_name"] == nxt["team_name"]
            if (
                is_pass and same_team
                and not pd.isna(this["pass_end_x_plot_m"])
                and not pd.isna(this["pass_end_y_plot_m"])
                and not is_error_event(str(nxt["event"]))
                and not is_admin_event(str(nxt["event"]))
                and not is_deleted_row(nxt)
            ):
                carry                    = nxt.copy()
                carry["kind"]            = "carry"
                carry["event"]           = "Carry"
                carry["is_goal"]         = False
                carry["order"]           = action_counter
                action_counter          += 1
                carry["x_plot_m"]        = prev_ball_end_x
                carry["y_plot_m"]        = prev_ball_end_y
                carry["ball_start_x"]    = prev_ball_end_x
                carry["ball_start_y"]    = prev_ball_end_y
                carry["ball_end_x"]      = nxt["x_plot_m"]
                carry["ball_end_y"]      = nxt["y_plot_m"]
                carry["has_line"]        = False
                carry["line_is_dashed"]  = False
                prev_ball_end_x, prev_ball_end_y = carry["ball_end_x"], carry["ball_end_y"]
                timeline_rows.append(carry)

    # Add explicit GK save / block marker
    if focus_type in ("saved_gk", "blocked"):
        save_row = find_next_save_event_for_shot(event_row)
        if save_row is not None:
            pos    = str(save_row.get("position", "")).upper()
            add_it = (
                (focus_type == "saved_gk" and pos == "GK") or
                (focus_type == "blocked"  and pos != "GK")
            )
            if add_it:
                save_vis                  = save_row.copy()
                save_vis["kind"]          = "save_gk" if focus_type == "saved_gk" else "save_block"
                save_vis["is_goal"]       = False
                save_vis["order"]         = action_counter
                action_counter           += 1
                sx                        = float(save_row["x_plot_m"])
                sy                        = float(save_row["y_plot_m"])
                save_vis["x_plot_m"]      = sx
                save_vis["y_plot_m"]      = sy
                save_vis["ball_start_x"]  = sx
                save_vis["ball_start_y"]  = sy
                save_vis["ball_end_x"]    = sx
                save_vis["ball_end_y"]    = sy
                save_vis["has_line"]      = False
                save_vis["line_is_dashed"]= False
                timeline_rows.append(save_vis)

    timeline = pd.DataFrame(timeline_rows).reset_index(drop=True)
    return timeline


# ============================================================
# 6. EASING
# ============================================================

def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, float(t)))
    return 0.5 - 0.5 * np.cos(np.pi * t)


# ============================================================
# 7. BUILD FRAME TRACES
# ============================================================

def build_traces_for_frame(timeline: pd.DataFrame, step: int, substep: int, n_substeps: int):
    slice_k = timeline.iloc[:step]
    curr    = timeline.iloc[step - 1]

    # ---- Action points ----
    xs, ys, colors, symbols, texts, hover = [], [], [], [], [], []

    for _, row in slice_k.iterrows():
        xs.append(row["x_plot_m"])
        ys.append(row["y_plot_m"])

        ev_str  = str(row.get("event", ""))
        is_foul = is_foul_event(ev_str)
        kind    = row.get("kind", "event")
        is_goal = bool(row.get("is_goal", False))

        base_color = "#00b0ff" if row["team_position"] == "home" else "#ff4b4b"

        if kind == "var":
            color, symbol, text_label = "#ffd54f", "diamond", "V"
        elif is_goal:
            color, symbol, text_label = "#ff4fd8", "star", str(row["order"])
        elif kind == "save_gk":
            color, symbol, text_label = "#4ade80", "diamond", "GK"
        elif kind == "save_block":
            color, symbol, text_label = "#fb923c", "hexagon", "B"
        elif is_foul:
            color, symbol, text_label = "#ffa600", "triangle-up", str(row["order"])
        elif kind == "carry":
            color, symbol, text_label = base_color, "circle-open", str(row["order"])
        elif kind == "error_bridge":
            color, symbol, text_label = "#9ca3af", "x", str(row["order"])
        else:
            color, symbol, text_label = base_color, "circle", str(row["order"])

        colors.append(color)
        symbols.append(symbol)
        texts.append(text_label)

        minute = int(row.get("time_min", 0))
        second = int(row.get("time_sec", 0))
        t_str  = f"{minute:02d}:{second:02d}"
        hover.append(
            f"{row['order']}. {row.get('event','')} – {row.get('player_name','')} ({row.get('team_name','')})<br>"
            f"Time: {t_str}, Half: {row.get('period_id', 1)}<br>"
            f"Type: {kind}"
        )

    points_trace = go.Scatter(
        x=xs, y=ys,
        mode="markers+text",
        marker=dict(
            color=colors, symbol=symbols, size=12,
            line=dict(color="rgba(0,0,0,0.55)", width=1),
        ),
        text=texts,
        textfont=dict(color="white", size=8),
        textposition="middle center",
        hovertext=hover,
        hoverinfo="text",
        showlegend=False,
        name="Actions",
    )

    # ---- Animated ball position ----
    t_ease = ease_in_out(substep / n_substeps)
    bx0 = float(curr["ball_start_x"])
    by0 = float(curr["ball_start_y"])
    bx1 = float(curr["ball_end_x"])
    by1 = float(curr["ball_end_y"])
    bx  = bx0 + (bx1 - bx0) * t_ease
    by  = by0 + (by1 - by0) * t_ease
    x_partial = bx
    y_partial  = by

    ball_trace = go.Scatter(
        x=[bx], y=[by],
        mode="markers",
        marker=dict(color="white", size=9, symbol="circle",
                    line=dict(color="#cccccc", width=1)),
        hoverinfo="skip",
        showlegend=False,
        name="Ball",
    )

    # ---- Line traces ----
    pass_solid_x, pass_solid_y = [], []
    pass_dash_x,  pass_dash_y  = [], []
    shot_goal_x,  shot_goal_y  = [], []
    shot_saved_gk_x, shot_saved_gk_y   = [], []
    shot_blocked_x,  shot_blocked_y    = [], []
    shot_saved_other_x, shot_saved_other_y = [], []
    shot_out_x,   shot_out_y   = [], []
    shot_other_x, shot_other_y = [], []

    for step_k in range(1, step + 1):
        row_k = timeline.iloc[step_k - 1]
        if not bool(row_k.get("has_line", False)):
            continue

        x0 = float(row_k["ball_start_x"])
        y0 = float(row_k["ball_start_y"])
        ev_str_k = str(row_k.get("event", ""))

        is_last = (step_k == step)
        if is_last:
            xe = x_partial
            ye = y_partial
        else:
            xe = float(row_k["ball_end_x"])
            ye = float(row_k["ball_end_y"])

        is_dashed = bool(row_k.get("line_is_dashed", False))

        if not is_shot_event(ev_str_k):
            if is_dashed:
                pass_dash_x.extend([x0, xe, None])
                pass_dash_y.extend([y0, ye, None])
            else:
                pass_solid_x.extend([x0, xe, None])
                pass_solid_y.extend([y0, ye, None])
        else:
            cat_shot = classify_shot_category(row_k)
            if cat_shot == "goal":
                shot_goal_x.extend([x0, xe, None])
                shot_goal_y.extend([y0, ye, None])
            elif cat_shot == "saved_gk":
                shot_saved_gk_x.extend([x0, xe, None])
                shot_saved_gk_y.extend([y0, ye, None])
            elif cat_shot == "blocked":
                shot_blocked_x.extend([x0, xe, None])
                shot_blocked_y.extend([y0, ye, None])
            elif cat_shot == "saved_other":
                shot_saved_other_x.extend([x0, xe, None])
                shot_saved_other_y.extend([y0, ye, None])
            else:
                if is_shot_off_target(row_k):
                    shot_out_x.extend([x0, xe, None])
                    shot_out_y.extend([y0, ye, None])
                else:
                    shot_other_x.extend([x0, xe, None])
                    shot_other_y.extend([y0, ye, None])

    pass_lines_solid = go.Scatter(
        x=pass_solid_x, y=pass_solid_y, mode="lines",
        line=dict(color="#00eaff", width=2), hoverinfo="skip", showlegend=False, name="Passes",
    )
    pass_lines_dash = go.Scatter(
        x=pass_dash_x, y=pass_dash_y, mode="lines",
        line=dict(color="#00eaff", width=3, dash="dash"), hoverinfo="skip", showlegend=False, name="Incomplete passes",
    )
    shot_lines_goal_other = go.Scatter(
        x=shot_goal_x + shot_other_x, y=shot_goal_y + shot_other_y, mode="lines",
        line=dict(color="#ff6bcb", width=3), hoverinfo="skip", showlegend=False, name="Shots (goal/on target)",
    )
    shot_lines_saved_gk = go.Scatter(
        x=shot_saved_gk_x, y=shot_saved_gk_y, mode="lines",
        line=dict(color="#eab308", width=3, dash="dash"), hoverinfo="skip", showlegend=False, name="GK save",
    )
    shot_lines_blocked = go.Scatter(
        x=shot_blocked_x, y=shot_blocked_y, mode="lines",
        line=dict(color="#f97316", width=3, dash="dot"), hoverinfo="skip", showlegend=False, name="Blocked",
    )
    shot_lines_saved_other = go.Scatter(
        x=shot_saved_other_x, y=shot_saved_other_y, mode="lines",
        line=dict(color="#eab308", width=3, dash="dash"), hoverinfo="skip", showlegend=False, name="Saved/blocked",
    )
    shot_lines_out = go.Scatter(
        x=shot_out_x, y=shot_out_y, mode="lines",
        line=dict(color="#fb923c", width=1.5), hoverinfo="skip", showlegend=False, name="Shot off target",
    )

    return [
        pass_lines_solid, pass_lines_dash,
        shot_lines_goal_other, shot_lines_saved_gk, shot_lines_blocked,
        shot_lines_saved_other, shot_lines_out,
        points_trace, ball_trace,
    ]


# ============================================================
# 8. TIMELINE CARDS
# ============================================================

def build_timeline_cards(timeline: pd.DataFrame, active_order: int = 1):
    cards = []
    for _, row in timeline.iterrows():
        kind      = row.get("kind", "event")
        is_active = (row.get("order") == active_order)
        is_goal   = bool(row.get("is_goal", False))

        if row["team_position"] == "home":
            accent = "#38bdf8"
        else:
            accent = "#f87171"

        if kind == "var":
            badge_text = "VAR"
        elif is_goal:
            badge_text = "GOAL"
        elif kind == "save_gk":
            badge_text = "GK Save"
        elif kind == "save_block":
            badge_text = "Block"
        elif kind == "carry":
            badge_text = "Carry"
        elif kind == "error_bridge":
            badge_text = "Error"
        else:
            badge_text = str(row.get("event", ""))

        order  = row.get("order", "")
        minute = int(row.get("time_min", 0))
        second = int(row.get("time_sec", 0))
        t_str  = f"{minute:02d}:{second:02d}"
        player = str(row.get("player_name", ""))
        team   = str(row.get("team_name", ""))
        period = row.get("period_id", 1)

        base_style = {
            "padding": "6px 8px",
            "borderRadius": "4px",
            "background": "rgba(15,23,42,0.85)",
            "display": "flex",
            "flexDirection": "column",
            "gap": "3px",
            "fontSize": "11px",
        }
        if is_active:
            base_style.update({
                "border": f"1px solid {accent}",
                "boxShadow": f"0 0 10px rgba(56,189,248,0.45)",
                "background": "linear-gradient(90deg, rgba(15,23,42,1), rgba(8,47,73,1))",
            })
        else:
            base_style.update({"borderLeft": f"2px solid {accent}"})

        card = html.Div(
            style=base_style,
            children=[
                html.Div(
                    style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                    children=[
                        html.Span(f"{order}. {badge_text}", style={"fontWeight": "600", "color": accent}),
                        html.Span(t_str, style={"color": "#e5e7eb"}),
                    ],
                ),
                html.Div(row.get("event", ""), style={"color": "#e5e7eb"}),
                html.Div(player, style={"color": "#9ca3af"}),
                html.Div(f"{team} · Half {period}", style={"color": "#6b7280"}),
            ],
        )
        cards.append(card)

    return cards


# ============================================================
# 9. DASH APP LAYOUT
# ============================================================

app = dash.Dash(__name__)
app.title = "Shot Animation – BAR vs ATM 2026-03-03"

app.layout = html.Div(
    style={
        "backgroundColor": "#020617",
        "color": "#e5e7eb",
        "fontFamily": "'Inter', 'Segoe UI', sans-serif",
        "minHeight": "100vh",
        "padding": "16px",
    },
    children=[
        html.H2(
            "Shot Sequence Animation – BAR vs ATM (Copa del Rey, 03/03/2026)",
            style={"textAlign": "center", "color": "#38bdf8", "marginBottom": "12px"},
        ),

        html.Div(
            style={
                "display": "flex", "flexWrap": "wrap", "gap": "16px",
                "marginBottom": "12px", "alignItems": "flex-end",
            },
            children=[
                html.Div(
                    style={"flex": "1 1 300px"},
                    children=[
                        html.Label("Filter by shot type:", style={"fontWeight": "bold", "fontSize": "13px"}),
                        dcc.RadioItems(
                            id="filter-trigger-type",
                            options=[
                                {"label": "All", "value": "all"},
                                {"label": "Goals", "value": "goal"},
                                {"label": "GK saves", "value": "saved_gk"},
                                {"label": "Blocks", "value": "blocked"},
                                {"label": "Off target / post", "value": "other_shot"},
                            ],
                            value="all",
                            inline=True,
                            inputStyle={"marginRight": "4px", "marginLeft": "8px"},
                            labelStyle={
                                "marginRight": "12px",
                                "display": "inline-flex",
                                "alignItems": "center",
                                "color": "#e5e7eb",
                                "fontSize": "13px",
                            },
                        ),
                    ],
                ),
                html.Div(
                    style={"flex": "2 1 360px"},
                    children=[
                        html.Label("Shot event:", style={"fontWeight": "bold", "fontSize": "13px"}),
                        dcc.Dropdown(
                            id="trigger-dropdown",
                            options=[],
                            value=None,
                            placeholder="Select a shot event...",
                            style={"color": "#000"},
                            clearable=False,
                        ),
                    ],
                ),
                html.Div(
                    style={"flex": "1 1 200px"},
                    children=[
                        html.Label("Animation speed:", style={"fontWeight": "bold", "fontSize": "13px"}),
                        dcc.Slider(
                            id="speed-slider", min=1, max=3, step=1, value=2,
                            marks={1: "Slow", 2: "Medium", 3: "Fast"},
                        ),
                    ],
                ),
            ],
        ),

        html.Div(
            style={
                "display": "flex", "justifyContent": "center",
                "alignItems": "flex-start", "gap": "16px", "marginBottom": "10px",
            },
            children=[
                dcc.Graph(
                    id="pitch-graph",
                    config={"displayModeBar": False},
                    style={"flex": "0 0 780px", "height": "550px"},
                ),
                html.Div(
                    id="timeline-cards",
                    style={
                        "flex": "0 0 260px",
                        "maxHeight": "550px",
                        "overflowY": "auto",
                        "display": "flex",
                        "flexDirection": "column",
                        "gap": "6px",
                    },
                    children=[],
                ),
            ],
        ),

        html.Div(
            "Legend: circle = player action | star = Goal | GK = goalkeeper save | "
            "B = block | pink solid line = shot on target | dashed yellow = GK save | "
            "orange dotted = blocked | thin orange = off target | cyan = pass",
            style={"fontSize": "11px", "color": "#9ca3af", "marginBottom": "8px"},
        ),

        dash_table.DataTable(
            id="actions-table",
            style_header={"backgroundColor": "#111827", "fontWeight": "bold", "color": "white"},
            style_cell={
                "backgroundColor": "#020617", "color": "white",
                "border": "1px solid #1f2937", "fontSize": 12,
                "padding": "4px", "textAlign": "left", "maxWidth": 220, "whiteSpace": "normal",
            },
            style_table={"maxHeight": "360px", "overflowY": "auto"},
            page_size=30,
        ),
    ],
)


# ============================================================
# 10. MAIN CALLBACK
# ============================================================

@app.callback(
    [
        Output("pitch-graph", "figure"),
        Output("actions-table", "data"),
        Output("actions-table", "columns"),
        Output("timeline-cards", "children"),
        Output("trigger-dropdown", "options"),
        Output("trigger-dropdown", "value"),
    ],
    [
        Input("filter-trigger-type", "value"),
        Input("trigger-dropdown", "value"),
        Input("speed-slider", "value"),
    ],
)
def update_trigger_sequence(filter_value, selected_row_index, speed_value):
    fig = create_pitch_figure()

    if filter_value == "all":
        filtered = triggers_df
    else:
        filtered = triggers_df[triggers_df["trigger_type"] == filter_value]

    if filtered.empty:
        return (
            fig, [], [],
            html.Div("No events for this filter.", style={"color": "#9ca3af", "fontSize": "14px"}),
            [], None,
        )

    options = [
        {"label": f"{i}. {row['label']}", "value": int(row["row_index"])}
        for i, (_, row) in enumerate(filtered.iterrows(), start=1)
    ]

    valid_ids = {int(r["row_index"]) for _, r in filtered.iterrows()}
    if selected_row_index not in valid_ids:
        selected_row_index = int(filtered.iloc[0]["row_index"])

    sel_row    = filtered[filtered["row_index"] == selected_row_index].iloc[0]
    focus_type = sel_row["trigger_type"]

    timeline = build_timeline_for_trigger(selected_row_index, focus_type)

    if timeline.empty:
        return (
            fig, [], [],
            html.Div("Could not build sequence.", style={"color": "#9ca3af"}),
            options, selected_row_index,
        )

    # Timing
    timeline["abs_time_sec"] = (
        timeline["time_min"].astype(float) * 60.0
        + timeline["time_sec"].astype(float)
    )
    timeline["dt"] = timeline["abs_time_sec"].diff().fillna(1.0)
    timeline["dt"] = timeline["dt"].clip(lower=0.25, upper=3.0)

    BASE_FPS = 15.0

    timeline["n_sub"] = (timeline["dt"] * BASE_FPS).round().astype(int)
    timeline.loc[timeline["n_sub"] < 2, "n_sub"] = 2

    # Carry speed
    SPEED_CARRY_MPS = 5.0
    is_carry = (timeline["kind"] == "carry")
    if is_carry.any():
        dx         = timeline.loc[is_carry, "ball_end_x"] - timeline.loc[is_carry, "ball_start_x"]
        dy         = timeline.loc[is_carry, "ball_end_y"] - timeline.loc[is_carry, "ball_start_y"]
        dist       = np.sqrt(dx * dx + dy * dy)
        carry_time = (dist / SPEED_CARRY_MPS).clip(0.25, 2.0)
        carry_n    = (carry_time * BASE_FPS).round().astype(int)
        carry_n[carry_n < 2] = 2
        timeline.loc[is_carry, "n_sub"] = carry_n

    is_event_row = (timeline["kind"] == "event")
    is_pass_row  = is_event_row & (timeline["event"] == "Pass")
    is_shot_row  = is_event_row & timeline["event"].apply(is_shot_event)

    if is_pass_row.any():
        n_pass = max(3, int(round(1.1 * BASE_FPS)))
        timeline.loc[is_pass_row, "n_sub"] = n_pass

    if is_shot_row.any():
        n_shot = max(2, int(round(0.40 * BASE_FPS)))
        timeline.loc[is_shot_row, "n_sub"] = n_shot

    base_frame_ms = int(1000.0 / BASE_FPS)
    speed_factor  = {1: 1.5, 2: 1.0, 3: 0.5}.get(speed_value, 1.0)
    frame_duration = int(base_frame_ms * speed_factor)

    # Fixed legend traces
    legend_specs = [
        (dict(color="#00b0ff", symbol="circle", size=11), "Home team (FC Barcelona)"),
        (dict(color="#ff4b4b", symbol="circle", size=11), "Away team (Atletico)"),
        (dict(color="#ff4fd8", symbol="star",   size=12), "Goal"),
        (dict(color="#4ade80", symbol="diamond",size=11), "GK save"),
        (dict(color="#fb923c", symbol="hexagon",size=11), "Blocked shot"),
        (dict(color="#ffa600", symbol="triangle-up", size=11), "Foul"),
        (dict(color="#9ca3af", symbol="x",      size=11), "Error / Clearance"),
        (dict(color="#e5e7eb", symbol="circle-open", size=10), "Ball carry"),
    ]
    line_specs = [
        (dict(color="#00eaff", width=2),               "Completed pass"),
        (dict(color="#00eaff", width=2, dash="dash"),  "Incomplete pass"),
        (dict(color="#ff6bcb", width=3),               "Shot (goal / on target)"),
        (dict(color="#eab308", width=3, dash="dash"),  "Saved / blocked shot"),
        (dict(color="#fb923c", width=1.5),             "Shot off target"),
    ]
    for mspec, name in legend_specs:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="markers",
            marker=dict(**mspec, line=dict(color="rgba(0,0,0,0.6)", width=1)),
            name=name, showlegend=True, hoverinfo="skip",
        ))
    for lspec, name in line_specs:
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines",
            line=lspec, name=name, showlegend=True, hoverinfo="skip",
        ))

    fig.update_layout(
        legend=dict(
            orientation="v", yanchor="top", y=1.0, xanchor="right", x=1.02,
            font=dict(color="#e5e7eb", size=9),
            bgcolor="rgba(15,23,42,0.96)",
            bordercolor="rgba(148,163,184,0.4)", borderwidth=1, itemwidth=40,
        ),
    )

    n_steps = len(timeline)
    first_n_sub = int(timeline.loc[0, "n_sub"])
    start_dyn_idx = len(fig.data)

    initial_traces = build_traces_for_frame(timeline, step=1, substep=first_n_sub, n_substeps=first_n_sub)
    for tr in initial_traces:
        fig.add_trace(tr)
    dynamic_trace_indices = list(range(start_dyn_idx, start_dyn_idx + len(initial_traces)))

    # Build animation frames
    frames = []
    for step in range(1, n_steps + 1):
        n_sub_i = int(timeline.loc[step - 1, "n_sub"])
        for sub in range(1, n_sub_i + 1):
            traces_k   = build_traces_for_frame(timeline, step=step, substep=sub, n_substeps=n_sub_i)
            frame_name = f"{step}_{sub}"
            frames.append(go.Frame(data=traces_k, name=frame_name, traces=dynamic_trace_indices))
    fig.frames = frames

    # Slider steps
    slider_steps = []
    for step in range(1, n_steps + 1):
        n_sub_i     = int(timeline.loc[step - 1, "n_sub"])
        target_frame = f"{step}_{n_sub_i}"
        row         = timeline.iloc[step - 1]
        label       = "VAR" if row["kind"] == "var" else str(row["order"])
        slider_steps.append({
            "label": label,
            "method": "animate",
            "args": [
                [target_frame],
                {"frame": {"duration": frame_duration, "redraw": False},
                 "mode": "immediate", "transition": {"duration": 0}},
            ],
        })

    fig.update_layout(
        updatemenus=[{
            "type": "buttons", "direction": "left",
            "x": 0.5, "y": -0.10, "xanchor": "center", "yanchor": "top",
            "showactive": True,
            "bgcolor": "rgba(15,23,42,0.98)",
            "bordercolor": "rgba(56,189,248,0.5)", "borderwidth": 1,
            "pad": {"r": 6, "t": 4, "b": 2, "l": 6},
            "font": {"color": "#e5e7eb", "size": 11},
            "buttons": [
                {
                    "label": "Reset",
                    "method": "animate",
                    "args": [
                        [f"1_{int(timeline.loc[0,'n_sub'])}"],
                        {"frame": {"duration": frame_duration, "redraw": False},
                         "mode": "immediate", "transition": {"duration": 0}},
                    ],
                },
                {
                    "label": "Play",
                    "method": "animate",
                    "args": [
                        None,
                        {"frame": {"duration": frame_duration, "redraw": False},
                         "fromcurrent": True, "transition": {"duration": 0}},
                    ],
                },
                {
                    "label": "Pause",
                    "method": "animate",
                    "args": [
                        [None],
                        {"frame": {"duration": 0, "redraw": False},
                         "mode": "immediate", "transition": {"duration": 0}},
                    ],
                },
            ],
        }],
        sliders=[{
            "active": 0,
            "y": -0.20, "x": 0.5, "xanchor": "center", "yanchor": "top",
            "len": 0.88,
            "pad": {"b": 25, "t": 8},
            "steps": slider_steps,
            "transition": {"duration": 0},
            "bgcolor": "rgba(15,23,42,0.95)",
            "tickcolor": "#38bdf8",
            "activebgcolor": "rgba(56,189,248,0.35)",
            "currentvalue": {"prefix": "Action: ", "font": {"color": "#e5e7eb", "size": 11}},
        }],
    )

    # Table
    table = timeline[[
        "order", "period_id", "time_min", "time_sec",
        "team_name", "player_name", "event", "kind", "dt",
    ]].copy()
    table["time_str"]   = (
        table["time_min"].astype(int).astype(str).str.zfill(2) + ":" +
        table["time_sec"].astype(int).astype(str).str.zfill(2)
    )
    table["dt_clamped"] = table["dt"].round(2)
    table = table[["order", "time_str", "dt_clamped", "period_id", "team_name", "player_name", "event", "kind"]]
    columns = [
        {"name": "No.",    "id": "order"},
        {"name": "Time",   "id": "time_str"},
        {"name": "Δt (s)", "id": "dt_clamped"},
        {"name": "Half",   "id": "period_id"},
        {"name": "Team",   "id": "team_name"},
        {"name": "Player", "id": "player_name"},
        {"name": "Event",  "id": "event"},
        {"name": "Type",   "id": "kind"},
    ]

    cards = build_timeline_cards(timeline, active_order=1)

    return fig, table.to_dict("records"), columns, cards, options, selected_row_index


# ============================================================
# 11. RUN
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)
