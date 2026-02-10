"""Tab 1: Match Overview - match narrative and key statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from barcelona_postmatch_app.config import (
    BARCELONA_GOLD,
    BARCELONA_PRIMARY,
    BARCELONA_SECONDARY,
    EVENT_TYPES,
    SHOT_TYPES,
)
from barcelona_postmatch_app.utils.helpers import compute_xg_simple, qualifier_is_set
from barcelona_postmatch_app.visualization.utils import (
    draw_pitch,
    get_team_colors,
)


def render(metadata: dict, events_df: pd.DataFrame) -> None:
    """Render the Match Overview tab."""
    create_match_header(metadata)
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Shot Map")
        fig = plot_shot_map(events_df, metadata)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Key Statistics")
        create_statistics_table(events_df, metadata)

    st.divider()

    st.subheader("Match Timeline")
    fig = plot_event_timeline(events_df, metadata)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Momentum (Cumulative xG)")
    fig = plot_momentum_chart(events_df, metadata)
    st.plotly_chart(fig, use_container_width=True)


def create_match_header(metadata: dict) -> None:
    """Display match header with teams, score, and formation."""
    col1, col2, col3 = st.columns([2, 1, 2])

    barca_is_home = metadata["barca_is_home"]
    barca_name = metadata["barca_team_name"]
    opp_name = metadata["opp_team_name"]

    with col1:
        team_label = f"{'(H)' if barca_is_home else '(A)'} {barca_name}"
        st.markdown(f"### {team_label}")
        st.caption(f"Formation: {metadata.get('barca_formation', 'N/A')}")

    with col2:
        home_score = metadata["home_score"]
        away_score = metadata["away_score"]
        st.markdown(
            f"<h1 style='text-align:center; color:{BARCELONA_GOLD};'>"
            f"{home_score} - {away_score}</h1>",
            unsafe_allow_html=True,
        )
        st.caption(f"{metadata['date']} | {metadata.get('venue', '')}")
        st.caption(f"{metadata.get('competition', '')} {metadata.get('season', '')}")

    with col3:
        team_label = f"{opp_name} {'(H)' if not barca_is_home else '(A)'}"
        st.markdown(f"### {team_label}")


def plot_shot_map(events_df: pd.DataFrame, metadata: dict) -> go.Figure:
    """Plot all shots on a pitch diagram with xG-weighted sizes."""
    fig = draw_pitch()

    barca_code = metadata["barca_code"]
    shots = events_df[events_df["event_type_id"].isin(SHOT_TYPES)]

    for team_flag, color, name in [
        (True, BARCELONA_PRIMARY, metadata["barca_team_name"]),
        (False, get_team_colors(metadata["opp_team_name"])[0], metadata["opp_team_name"]),
    ]:
        team_shots = shots[shots["is_barca"] == team_flag]

        if team_shots.empty:
            continue

        x_vals, y_vals, sizes, texts, colors_list = [], [], [], [], []

        for _, shot in team_shots.iterrows():
            x = shot.get("x_norm", shot.get("x", np.nan))
            y = shot.get("y_norm", shot.get("y", np.nan))

            if np.isnan(x) or np.isnan(y):
                continue

            # If it's opposition, show from their attacking perspective (flip)
            if not team_flag:
                x = 100 - x
                y = 100 - y

            is_header = qualifier_is_set(shot.get("Head"))
            xg = compute_xg_simple(
                shot.get("x_norm", shot.get("x", 50)),
                shot.get("y_norm", shot.get("y", 50)),
                is_header,
            )

            x_vals.append(x)
            y_vals.append(y)
            sizes.append(max(8, xg * 40))

            is_goal = shot["event_type_id"] == EVENT_TYPES["goal"]
            marker_symbol = "star" if is_goal else "circle"

            texts.append(
                f"{shot.get('player_name', 'Unknown')}<br>"
                f"xG: {xg:.2f} | {shot['event_type']}<br>"
                f"Min: {shot.get('minute', shot.get('time_min', ''))}"
            )

            if is_goal:
                colors_list.append(BARCELONA_GOLD)
            else:
                colors_list.append(color)

        fig.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode="markers",
            marker=dict(size=sizes, color=colors_list, line=dict(width=1, color="white")),
            text=texts,
            hoverinfo="text",
            name=name,
        ))

    fig.update_layout(
        title="Shot Map",
        showlegend=True,
        legend=dict(x=0.5, y=-0.05, xanchor="center", orientation="h"),
    )
    return fig


def plot_event_timeline(events_df: pd.DataFrame, metadata: dict) -> go.Figure:
    """Create an interactive timeline of key match events."""
    fig = go.Figure()

    key_events = events_df[events_df["event_type_id"].isin({
        EVENT_TYPES["goal"], EVENT_TYPES["card"],
        EVENT_TYPES["player_off"], EVENT_TYPES["player_on"],
        EVENT_TYPES["saved_shot"], EVENT_TYPES["miss"],
        EVENT_TYPES["post"],
    })].copy()

    if key_events.empty:
        fig.update_layout(title="No key events found")
        return fig

    # Assign y-positions by event type
    type_y = {
        EVENT_TYPES["goal"]: 3,
        EVENT_TYPES["saved_shot"]: 2,
        EVENT_TYPES["miss"]: 2,
        EVENT_TYPES["post"]: 2,
        EVENT_TYPES["card"]: 1,
        EVENT_TYPES["player_off"]: 0,
        EVENT_TYPES["player_on"]: 0,
    }

    type_colors = {
        EVENT_TYPES["goal"]: BARCELONA_GOLD,
        EVENT_TYPES["saved_shot"]: BARCELONA_SECONDARY,
        EVENT_TYPES["miss"]: "#999999",
        EVENT_TYPES["post"]: "#FF6B6B",
        EVENT_TYPES["card"]: "#FFD700",
        EVENT_TYPES["player_off"]: "#FF4444",
        EVENT_TYPES["player_on"]: "#44FF44",
    }

    for _, evt in key_events.iterrows():
        etype = evt["event_type_id"]
        minute = evt.get("minute", evt.get("time_min", 0))
        y = type_y.get(etype, 0)
        color = type_colors.get(etype, "#FFFFFF")
        is_barca = evt["is_barca"]

        marker_size = 14 if etype == EVENT_TYPES["goal"] else 10

        fig.add_trace(go.Scatter(
            x=[minute],
            y=[y if is_barca else -y],
            mode="markers",
            marker=dict(size=marker_size, color=color, symbol="diamond" if is_barca else "circle"),
            hoverinfo="text",
            text=f"{evt.get('player_name', '')} ({minute}')<br>{evt['event_type']}<br>{'Barcelona' if is_barca else metadata['opp_team_name']}",
            showlegend=False,
        ))

    # Add half-time line
    fig.add_vline(x=45, line_dash="dash", line_color="white", opacity=0.5)

    fig.update_layout(
        title="Match Timeline",
        xaxis=dict(title="Minute", range=[0, 95]),
        yaxis=dict(
            showticklabels=False, zeroline=True,
            zerolinecolor="white", zerolinewidth=1,
            range=[-4, 4],
        ),
        plot_bgcolor=BARCELONA_SECONDARY + "20",
        height=250,
        annotations=[
            dict(x=0.02, y=0.95, text=metadata["barca_team_name"], xref="paper", yref="paper",
                 showarrow=False, font=dict(color=BARCELONA_PRIMARY, size=12)),
            dict(x=0.02, y=0.05, text=metadata["opp_team_name"], xref="paper", yref="paper",
                 showarrow=False, font=dict(size=12)),
        ],
    )
    return fig


def create_statistics_table(events_df: pd.DataFrame, metadata: dict) -> None:
    """Display key match statistics for both teams."""
    barca = events_df[events_df["is_barca"]]
    opp = events_df[~events_df["is_barca"]]

    # Filter to in-play events only
    in_play_types = {1, 2, 3, 4, 7, 8, 9, 12, 13, 14, 15, 16, 44, 45, 49, 50, 61, 74}

    def _count(df, etype):
        return len(df[df["event_type_id"] == etype])

    def _count_set(df, etypes):
        return len(df[df["event_type_id"].isin(etypes)])

    def _pass_completion(df):
        passes = df[df["event_type_id"] == EVENT_TYPES["pass"]]
        total = len(passes)
        completed = len(passes[passes["outcome"] == 1])
        return f"{round(completed / total * 100, 1)}%" if total > 0 else "0%"

    def _progressive_passes(df):
        if "is_progressive" in df.columns:
            return int(df[(df["event_type_id"] == EVENT_TYPES["pass"]) & (df["is_progressive"])].shape[0])
        return 0

    def _xg(df):
        shots = df[df["event_type_id"].isin(SHOT_TYPES)]
        total = 0.0
        for _, s in shots.iterrows():
            x = s.get("x_norm", s.get("x", 50))
            y = s.get("y_norm", s.get("y", 50))
            is_header = qualifier_is_set(s.get("Head"))
            total += compute_xg_simple(x, y, is_header)
        return round(total, 2)

    stats = {
        "Possession (events)": (
            f"{round(len(barca[barca['event_type_id'].isin(in_play_types)]) / max(1, len(events_df[events_df['event_type_id'].isin(in_play_types)])) * 100)}%",
            f"{round(len(opp[opp['event_type_id'].isin(in_play_types)]) / max(1, len(events_df[events_df['event_type_id'].isin(in_play_types)])) * 100)}%",
        ),
        "Passes": (_count(barca, 1), _count(opp, 1)),
        "Pass Completion": (_pass_completion(barca), _pass_completion(opp)),
        "Progressive Passes": (_progressive_passes(barca), _progressive_passes(opp)),
        "Shots": (_count_set(barca, SHOT_TYPES), _count_set(opp, SHOT_TYPES)),
        "Shots on Target": (
            _count(barca, 15) + _count(barca, 16),
            _count(opp, 15) + _count(opp, 16),
        ),
        "xG": (_xg(barca), _xg(opp)),
        "Tackles": (_count(barca, 7), _count(opp, 7)),
        "Interceptions": (_count(barca, 8), _count(opp, 8)),
        "Fouls": (_count(barca, 4), _count(opp, 4)),
        "Corners": (_count(barca, 6), _count(opp, 6)),
    }

    stat_df = pd.DataFrame(
        [(k, v[0], v[1]) for k, v in stats.items()],
        columns=["Stat", metadata["barca_team_name"], metadata["opp_team_name"]],
    )
    st.dataframe(stat_df, hide_index=True, use_container_width=True)


def plot_momentum_chart(events_df: pd.DataFrame, metadata: dict) -> go.Figure:
    """Plot cumulative xG over time for both teams."""
    fig = go.Figure()

    for is_barca, name, color in [
        (True, metadata["barca_team_name"], BARCELONA_PRIMARY),
        (False, metadata["opp_team_name"], get_team_colors(metadata["opp_team_name"])[0]),
    ]:
        shots = events_df[
            (events_df["is_barca"] == is_barca) &
            (events_df["event_type_id"].isin(SHOT_TYPES))
        ].sort_values("minute")

        if shots.empty:
            continue

        minutes = [0]
        cum_xg = [0.0]

        for _, shot in shots.iterrows():
            x = shot.get("x_norm", shot.get("x", 50))
            y = shot.get("y_norm", shot.get("y", 50))
            is_header = qualifier_is_set(shot.get("Head"))
            xg = compute_xg_simple(x, y, is_header)

            minutes.append(shot.get("minute", shot.get("time_min", 0)))
            cum_xg.append(cum_xg[-1] + xg)

        # Extend to end of match
        max_min = int(events_df["minute"].max()) if "minute" in events_df else 90
        minutes.append(max_min)
        cum_xg.append(cum_xg[-1])

        fig.add_trace(go.Scatter(
            x=minutes, y=cum_xg,
            mode="lines+markers",
            name=name,
            line=dict(color=color, width=3),
            marker=dict(size=6),
        ))

    fig.add_vline(x=45, line_dash="dash", line_color="white", opacity=0.3)

    fig.update_layout(
        title="Cumulative xG",
        xaxis=dict(title="Minute"),
        yaxis=dict(title="xG"),
        plot_bgcolor="rgba(0,0,0,0)",
        height=350,
        legend=dict(x=0.02, y=0.98),
    )
    return fig
