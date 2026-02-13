"""
Interactive Football Pitch Visualization with Plotly
=====================================================

Reusable function for creating interactive scatter plots on grass football pitches.
Features: Grass pitch with stripes, visible goal posts, hover tooltips showing player names and time.

Author: Rishi
Date: December 2025
"""

import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from mplsoccer import Pitch
import io
import base64


def create_interactive_pitch_scatter(
    df_event,
    df_players,
    home_team,
    away_team,
    team='both',
    player_id=0,
    event_name='Event',
    home_color='#6a380c',
    away_color='#feb04d'
):
    """
    Create an interactive scatter plot on a grass football pitch with hover tooltips.
    
    Parameters
    ----------
    df_event : pd.DataFrame
        Event data with columns: x, y, team_name, player_id, time_minutes
    df_players : pd.DataFrame
        Player data with columns: player_id, player (player name)
    home_team : str
        Name of the home team
    away_team : str
        Name of the away team
    team : str, default='both'
        Which team(s) to display: 'home', 'away', or 'both'
    player_id : int, default=0
        Specific player ID to filter (0 = all players)
    event_name : str, default='Event'
        Name of the event type for display purposes
    home_color : str, default='#6a380c'
        Hex color for home team markers (Cafe Royal)
    away_color : str, default='#feb04d'
        Hex color for away team markers (Texas Rose)
    
    Returns
    -------
    fig : plotly.graph_objects.Figure
        Plotly figure ready to display with st.plotly_chart()
    
    Examples
    --------
    >>> # Single team view
    >>> fig = create_interactive_pitch_scatter(
    ...     df_event=df_fouls,
    ...     df_players=df_players,
    ...     home_team='Barcelona',
    ...     away_team='Real Madrid',
    ...     team='home',
    ...     event_name='Faltas'
    ... )
    >>> st.plotly_chart(fig, use_container_width=True)
    
    >>> # Both teams view
    >>> fig = create_interactive_pitch_scatter(
    ...     df_event=df_interceptions,
    ...     df_players=df_players,
    ...     home_team='Barcelona',
    ...     away_team='Real Madrid',
    ...     team='both',
    ...     event_name='Intercepciones'
    ... )
    >>> st.plotly_chart(fig, use_container_width=True)
    
    >>> # Single player view
    >>> fig = create_interactive_pitch_scatter(
    ...     df_event=df_tackles,
    ...     df_players=df_players,
    ...     home_team='Barcelona',
    ...     away_team='Real Madrid',
    ...     team='home',
    ...     player_id=12345,
    ...     event_name='Entradas'
    ... )
    >>> st.plotly_chart(fig, use_container_width=True)
    """
    
    # Make a copy to avoid modifying original data
    df_event = df_event.copy()
    
    # Merge player names
    df_players_info = df_players[["player_id", "player"]].drop_duplicates()
    df_event = df_event.merge(df_players_info, on="player_id", how="left")
    
    # Format time for display (MM:SS)
    df_event["time_display"] = df_event["time_minutes"].apply(
        lambda x: f"{int(x)}:{int((x % 1) * 60):02d}"
    )
    
    # Determine which team(s) to show
    if team == home_team or team == 'home':
        display_mode = 'home'
        df_event = df_event[df_event["team_name"] == home_team]
        direction_text = "Dirección de ataque →"
    elif team == away_team or team == 'away':
        display_mode = 'away'
        df_event = df_event[df_event["team_name"] == away_team]
        # Flip coordinates for away team
        df_event["x"] = 100 - df_event["x"]
        df_event["y"] = 100 - df_event["y"]
        direction_text = "← Dirección de ataque"
    else:
        display_mode = 'both'
        direction_text = None
    
    # Filter by specific player if requested
    if player_id != 0:
        df_event = df_event[df_event["player_id"] == player_id]
    
    # Create mplsoccer pitch with grass and padding
    pitch = Pitch(
        pitch_type="opta",
        pitch_color='grass',
        line_color='white',
        stripe=True,
        pad_left=5,       # Shows left goal post
        pad_right=5,      # Shows right goal post
        pad_top=2,        # Small top padding
        pad_bottom=2,     # Small bottom padding
        goal_type='box',
        goal_alpha=0.8
    )
    fig_pitch, ax_pitch = pitch.draw(figsize=(15, 10))
    
    # Save pitch as base64 image
    buf = io.BytesIO()
    fig_pitch.savefig(buf, format='png', dpi=100, bbox_inches='tight', pad_inches=0)
    buf.seek(0)
    pitch_img = base64.b64encode(buf.read()).decode()
    plt.close(fig_pitch)
    
    # Create Plotly figure
    fig = go.Figure()
    
    # Add scatter points based on display mode
    if display_mode == 'home':
        fig.add_trace(go.Scatter(
            x=df_event["x"],
            y=df_event["y"],
            mode='markers',
            marker=dict(
                size=14,
                color=home_color,
                line=dict(width=2, color='white')
            ),
            customdata=df_event[['player', 'time_display']],
            hovertemplate='<b>%{customdata[0]}</b><br>Tiempo: %{customdata[1]}<extra></extra>',
            name=home_team
        ))
    elif display_mode == 'away':
        fig.add_trace(go.Scatter(
            x=df_event["x"],
            y=df_event["y"],
            mode='markers',
            marker=dict(
                size=14,
                color=away_color,
                line=dict(width=2, color='white')
            ),
            customdata=df_event[['player', 'time_display']],
            hovertemplate='<b>%{customdata[0]}</b><br>Tiempo: %{customdata[1]}<extra></extra>',
            name=away_team
        ))
    else:  # both teams
        df_home = df_event[df_event["team_name"] == home_team]
        df_away = df_event[df_event["team_name"] == away_team]
        
        # Home team scatter
        fig.add_trace(go.Scatter(
            x=df_home["x"],
            y=df_home["y"],
            mode='markers',
            marker=dict(
                size=14,
                color=home_color,
                line=dict(width=2, color='white')
            ),
            customdata=df_home[['player', 'time_display']],
            hovertemplate='<b>' + home_team + '</b><br>%{customdata[0]}<br>Tiempo: %{customdata[1]}<extra></extra>',
            name=home_team
        ))
        
        # Away team scatter
        fig.add_trace(go.Scatter(
            x=df_away["x"],
            y=df_away["y"],
            mode='markers',
            marker=dict(
                size=14,
                color=away_color,
                line=dict(width=2, color='white')
            ),
            customdata=df_away[['player', 'time_display']],
            hovertemplate='<b>' + away_team + '</b><br>%{customdata[0]}<br>Tiempo: %{customdata[1]}<extra></extra>',
            name=away_team
        ))
    
    # Add pitch background
    fig.add_layout_image(
        dict(
            source=f'data:image/png;base64,{pitch_img}',
            xref="x",
            yref="y",
            x=-5,
            y=102,
            sizex=110,
            sizey=104,
            sizing="stretch",
            opacity=1,
            layer="below"
        )
    )
    
    # Add direction arrow if single team
    if direction_text:
        fig.add_annotation(
            x=50,
            y=100,
            text=direction_text,
            showarrow=False,
            font=dict(size=14, color='white', family='Arial Black'),
            bgcolor='rgba(0,0,0,0.7)',
            borderpad=8
        )
    
    # Configure layout
    fig.update_layout(
        xaxis=dict(
            range=[-5, 105],
            showgrid=False,
            zeroline=False,
            visible=False
        ),
        yaxis=dict(
            range=[-2, 102],
            showgrid=False,
            zeroline=False,
            visible=False
        ),
        width=1200,
        height=700,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=(display_mode == 'both'),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=1.05,
            xanchor="center",
            x=0.5,
            bgcolor='rgba(255,255,255,0.9)',
            bordercolor='black',
            borderwidth=1
        ) if display_mode == 'both' else None,
        margin=dict(l=0, r=0, t=40 if display_mode == 'both' else 0, b=0),
        hovermode='closest'
    )
    
    return fig


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """
    Example usage of the create_interactive_pitch_scatter function.
    """
    import streamlit as st
    
    # Example 1: Show fouls for home team only
    st.header("Faltas - Barcelona")
    fig = create_interactive_pitch_scatter(
        df_event=df_fouls,
        df_players=df_players,
        home_team='Barcelona',
        away_team='Real Madrid',
        team='home',
        event_name='Faltas'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Example 2: Show interceptions for both teams
    st.header("Intercepciones - Ambos Equipos")
    fig = create_interactive_pitch_scatter(
        df_event=df_interceptions,
        df_players=df_players,
        home_team='Barcelona',
        away_team='Real Madrid',
        team='both',
        event_name='Intercepciones'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Example 3: Show tackles for specific player
    st.header("Entradas - Alexia Putellas")
    fig = create_interactive_pitch_scatter(
        df_event=df_tackles,
        df_players=df_players,
        home_team='Barcelona',
        away_team='Real Madrid',
        team='home',
        player_id=12345,  # Alexia's ID
        event_name='Entradas'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Example 4: Custom colors
    st.header("Duelos - Colores Personalizados")
    fig = create_interactive_pitch_scatter(
        df_event=df_duels,
        df_players=df_players,
        home_team='Barcelona',
        away_team='Real Madrid',
        team='both',
        home_color='#FF0000',  # Red
        away_color='#0000FF',  # Blue
        event_name='Duelos'
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# INTEGRATION EXAMPLE FOR EXISTING CODE
# ============================================================================

def integrate_with_existing_code_example():
    """
    Example of how to integrate this function into your existing pitch_events.py
    """
    import streamlit as st
    
    # In your existing code, replace the long scatter plot sections with:
    
    # Instead of 100+ lines of code for home team...
    if team == home_team:
        fig = create_interactive_pitch_scatter(
            df_event=df_specific_event,
            df_players=df_players,
            home_team=home_team,
            away_team=away_team,
            team='home',
            player_id=player_id,
            event_name=event_type
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Instead of 100+ lines of code for away team...
    elif team == away_team:
        fig = create_interactive_pitch_scatter(
            df_event=df_specific_event,
            df_players=df_players,
            home_team=home_team,
            away_team=away_team,
            team='away',
            player_id=player_id,
            event_name=event_type
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Instead of 100+ lines of code for both teams...
    else:
        fig = create_interactive_pitch_scatter(
            df_event=df_specific_event,
            df_players=df_players,
            home_team=home_team,
            away_team=away_team,
            team='both',
            player_id=player_id,
            event_name=event_type
        )
        st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# CUSTOMIZATION GUIDE
# ============================================================================

"""
CUSTOMIZATION OPTIONS:
======================

1. COLORS:
   - home_color: Hex color for home team (default: '#6a380c' Cafe Royal)
   - away_color: Hex color for away team (default: '#feb04d' Texas Rose)

2. PITCH APPEARANCE:
   - Modify Pitch() parameters for different pitch styles
   - pitch_color='grass' for grass, or use custom color
   - stripe=True/False for striped grass
   - goal_type='box'/'line' for goal appearance

3. MARKER STYLE:
   - size: Change marker size (default: 14)
   - line width: Change border width (default: 2)
   - line color: Change border color (default: 'white')

4. LAYOUT:
   - width/height: Adjust figure dimensions (default: 1200x700)
   - Padding: Adjust pad_left/right/top/bottom for different views

5. HOVER TEMPLATE:
   - Customize hovertemplate for different information display
   - Add more fields to customdata array

6. DIRECTION ARROW:
   - Customize text, position, styling
   - Add/remove based on preference

REQUIRED DATA STRUCTURE:
========================

df_event must have columns:
- x: X coordinate (0-100)
- y: Y coordinate (0-100)
- team_name: Team name matching home_team or away_team
- player_id: Player ID for merging with df_players
- time_minutes: Decimal minutes (e.g., 23.75 = 23:45)

df_players must have columns:
- player_id: Player ID matching df_event
- player: Player name for display
"""
