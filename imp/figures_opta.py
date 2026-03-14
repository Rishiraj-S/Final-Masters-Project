#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Sep 30 15:06:17 2025

@author: julieta
"""
import pandas as pd
import os
import numpy as np
import json
from mplsoccer import Radar, FontManager, grid
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup

from urllib.request import urlopen
from PIL import Image, UnidentifiedImageError, ImageDraw
from mplsoccer import PyPizza, add_image, Pitch, VerticalPitch

from highlight_text import fig_text
import xml.etree.ElementTree as ET
from matplotlib.colors import LinearSegmentedColormap
import imageio
from matplotlib.animation import FuncAnimation
from functools import partial
import matplotlib.lines as mlines
import warnings
from highlight_text import ax_text
import cmasher as cmr
import networkx as nx
from matplotlib.colors import to_rgba
import matplotlib.patheffects as path_effects
from matplotlib import rcParams
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from matplotlib.patches import FancyArrowPatch
import igraph as ig
import math
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch


def Heatmap_one_team(team_analizing, file_path_15, file_path_24):
    
    """
    Esta funcion devuelve un Heatmap de todas las acciones de un jugador en un cierto partido
    
    Parameters
    --------
    player_id_analizing: el ID de OPTA del jugador del cual queremos el heatmap
    
    file_path_24: hay que insertar la ruta del f24 para el partido en concreto que estamos estudiando
    
    file_path_15: hay que insertar la ruta del ES EL F40 para el partido en concreto que estamos estudiando
            
            este f15 lo usamos para sacar el nombre de los jugadores
    
    Returns
    -------
    tuple (matplotlib.figure.Figure, str)  
    Figura generada y ruta donde se guarda la imagen.  
    
    """
    if not os.path.exists(file_path_24):
        print(f"Error: El archivo '{file_path_24}' no existe.")
        return None, None
    
    tree = ET.parse(file_path_24)
    root = tree.getroot()
    
    URL = 'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf'
    URL2 = 'https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab[wght].ttf'
    robotto_regular = FontManager(URL)
    robboto_bold = FontManager(URL2)
    
    game = root.find("Game")
    game_data = {attr: game.attrib[attr] for attr in game.attrib}
    df_game = pd.DataFrame([game_data])
    team_names = df_game[["home_team_id", "home_team_name", "away_team_id", "away_team_name"]]
    
    event_list = []
    for event in game.findall("Event"):
        event_data = {attr: event.attrib[attr] for attr in event.attrib} 
        qualifiers = [{attr: qualifier.attrib[attr] for attr in qualifier.attrib} for qualifier in event.findall("Q")]
        event_data["qualifiers"] = qualifiers  
        event_list.append(event_data)
    
    df_events = pd.DataFrame(event_list).drop(["last_modified", "version"], axis=1)
    df_events["keypass"] = df_events["keypass"].fillna(0)
    df_events = df_events.astype({"id": float, "event_id": float, "type_id": float, "period_id": float,
                                  "min": float, "sec": float, "team_id": float, "outcome": float,
                                  "x": float, "y": float, "player_id": float, "keypass": float})
    
    teams = pd.concat([
        team_names[['home_team_id', 'home_team_name']].rename(columns={'home_team_id': 'team_id', 'home_team_name': 'team_name'}),
        team_names[['away_team_id', 'away_team_name']].rename(columns={'away_team_id': 'team_id', 'away_team_name': 'team_name'})
    ]).drop_duplicates().astype({"team_id": float})
    
    df_events = df_events.merge(teams, on="team_id", how="left")
    df_events[["timestamp", "timestamp_utc"]] = df_events[["timestamp", "timestamp_utc"]].apply(pd.to_datetime)
    df_events["first_qualifier_id"] = df_events["qualifiers"].apply(lambda q: q[0]["qualifier_id"] if q else None).astype(float)
    if not os.path.exists(file_path_15):
        print(f"Error: El archivo '{file_path_15}' no existe.")
        return None, None
    tree = ET.parse(file_path_15)
    root = tree.getroot()
    equipos = {team.get("uID"): team.find("Name").text for team in root.findall(".//Team")}
    
    data = []
    for team in root.findall(".//Team"):
        for player in team.findall("Player"):
            stats = {stat.get("Type"): stat.text for stat in player.findall("Stat")}
            row = {
                "team_id": team.get("uID"),
                "team_name": equipos.get(team.get("uID"), f"Equipo {team.get('uID')}"),
                "player_id": player.get("uID"),
                "player_name": player.find("Name").text if player.find("Name") is not None else None,
                **stats,
            }
            data.append(row)
    
    df = pd.DataFrame(data)
    # df["player_name"] = df["first name"] + " " + df["last name"]
    df_equipos = pd.DataFrame(list(equipos.items()), columns=["team_id", "team_name"])
    df_equipos["team_id"] = df_equipos["team_id"].str.extract('(\\d+)').astype(int)
    df_equipos.set_index("team_id", inplace=True)
    
    player_relations = df[["player_name", "player_id", "team_id", "team_name"]].copy()
    player_relations["player_id"] = player_relations["player_id"].str.extract('(\\d+)').astype(int)
    player_relations["team_id"] = player_relations["team_id"].str.extract('(\\d+)').astype(int)
    player_relations = player_relations.drop_duplicates(subset=["player_id", "team_id"]).set_index(["player_id", "team_id"])
    player_relations = player_relations.reset_index().merge(df_equipos, on="team_id", how="left")
    player_relations["team_name"] = player_relations["team_name_y"].fillna(player_relations["team_name_x"])
    player_relations.drop(columns=["team_name_x", "team_name_y"], inplace=True)
    player_relations.set_index(["player_id", "team_id"], inplace=True)

    home_team, away_team = team_names.iloc[0][["home_team_name", "away_team_name"]]
    #home_id ,away_id=team_names.iloc[0][["home_team_id", "away_team_id"]]
    df_events["team_id"] = df_events["team_id"].astype(int)
    home_id, away_id = team_names.iloc[0][["home_team_id", "away_team_id"]].astype(int)
    if team_analizing=="home":
        team_id=home_id
        team_analizing=home_team
    elif team_analizing=="away":
        team_id=away_id
        team_analizing=away_team
    
    #df_events = df_events.astype({"team_id": float})
    df_events_ = df_events[df_events["team_id"]==team_id][["x", "y"]]

    flamingo_cmap = LinearSegmentedColormap.from_list("Flamingo - 100 colors", ['#e3aca7', '#c03a1d'], N=100)
    pitch = VerticalPitch(pitch_type='opta', line_color='#000009', line_zorder=2)
    fig, axs = pitch.grid(figheight=10, title_height=0.08, endnote_space=0, title_space=0, axis=False, grid_height=0.82, endnote_height=0.03)
    
    pitch.kdeplot(df_events_.x, df_events_.y, ax=axs['pitch'], fill=True, levels=100, thresh=0, cut=4, cmap="cividis")
    arrow = FancyArrowPatch(
        (0.99, 0.4),    # start (just outside right side, near bottom)
        (0.99, 0.6),    # end (just outside right side, near top)
        transform=axs['pitch'].transAxes,   # relative to axes
        arrowstyle='simple', 
        color='black',
        mutation_scale=10,  # arrow size
        linewidth=2
        )
    axs['pitch'].add_patch(arrow)
    #axs['endnote'].text(1, 0.5, 'Julieta Schwartz', va='center', ha='right', fontsize=15, fontproperties=robotto_regular.prop)
    axs['title'].text(0.5, 0.7, f"{team_analizing}'s Actions", color='#000009', va='center', ha='center', fontproperties=robotto_regular.prop, fontsize=30)
    axs['title'].text(0.5, 0.25, f"{home_team} vs {away_team}", color='#000009', va='center', ha='center', fontproperties=robotto_regular.prop, fontsize=20)
    output_path = f"heatmap_{team_analizing}.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    plt.close(fig)
    return output_path

#Heatmap_one_team("home", "/Users/julieta/Desktop/data_madridcff/f40/f40-squad-102.xml", "/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")


def passnetwork_oneteam_thirds(filepath_f27, filepath_f40,type_third):
    """
    

    Parameters
    ----------
    filepath_f27 : Ruta del archivo f27 que contiene la matriz de pases de un unico equipo para un partido
                    en cada archivo f27 solo viene un equipo, si se quieren los 2 equipos hay que hacerlo por separado
                    
                    forma: pass_matrix_{competition_id}_{season_id}_g{game_id}_t{team_id}.xml

    filepath_f40 : Ruta del archivo f24 que contiene datos de todos los jugadores

    Returns
    --------
    tuple (matplotlib.figure.Figure, str)  
    Figura generada y ruta donde se guarda la imagen.  

    """
    if not os.path.exists(filepath_f27):
        print(f"Error: El archivo '{filepath_f27}' no existe.")
        return None, None

    tree = ET.parse(filepath_f27)
    root = tree.getroot()

    # Crear una lista para almacenar los datos

    # Obtener el atributo "team_name" del nodo <SoccerFeed>
    team_analizing = root.get("team_name")
    home_team = root.get("home_team_name")
    away_team = root.get("away_team_name")
    season = root.get("season_name")

    # print("Team Name:", team_name)
    pases_data = []

    for player in root.findall("Player"):
        passer_name = player.get("player_name")
        passer_position = player.get("position")  # Obtener la posición del jugador
        passer_x = float(player.get("x"))  # Obtener la coordenada X
        passer_y = float(player.get("y"))  # Obtener la coordenada Y
        sub_on = player.get("sub_on")  # Minuto en el que ingresó como suplente
        sub_on = int(eval(sub_on)) if sub_on is not None else None  # Convertir a entero si existe

        # Iterar sobre los jugadores a los que se les hacen los pases
        for pass_receiver in player.findall("Player"):
            receiver_name = pass_receiver.get("player_name")
            passes = int(pass_receiver.text)

            # Añadir los datos a la lista
            pases_data.append({
                "player": passer_name,
                "position": passer_position,
                "x": passer_x,
                "y": passer_y,
                "receiver": receiver_name,
                "pases": passes,
                "sub": sub_on is not None,  # True si salió como suplente
                "entry_minute": sub_on  # Minuto en el que entró, None si no es suplente
            })

    # Crear el DataFrame
    df_pases = pd.DataFrame(pases_data)
    
    if type_third=="first":
       df_pases = df_pases[df_pases["x"]<= 33.33].copy()
       pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
       )
    elif type_third=="second":
        
        df_pases = df_pases[(df_pases["x"] >= 33.33) & (df_pases["x"] <= 66.66)].copy()
        pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
           )
    elif type_third=="third":
        df_pases = df_pases[(df_pases["x"] >= 66.67)].copy()
        pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
           )
    elif type_third=="all":
        df_pases = df_pases.copy()
        pitch = Pitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,
           )
    #print(df_pases["x"])
    
    if not os.path.exists(filepath_f40):
        print(f"Error: El archivo '{filepath_f40}' no existe.")
        return None, None

    tree = ET.parse(filepath_f40)
    root = tree.getroot()

    jugadores_data = []

    for team in root.findall(".//Team"):
        team_name = team.find("Name").text  # Obtener el nombre del equipo

        # Iterar sobre los jugadores de cada equipo
        for player in team.findall(".//Player"):
            player_name = player.find("Name").text  # Obtener el nombre del jugador
            position = player.find("Position").text  # Obtener la posición del jugador
            jersey_stat = player.find('.//Stat[@Type="jersey_num"]')
            jersey_number = jersey_stat.text if jersey_stat is not None else None  # Manejar si no existe

            # Añadir los datos a la lista, incluyendo el equipo
            jugadores_data.append({
                "player": player_name,
                "position": position,
                "team": team_name,
                "jersey_num": jersey_number
            })

    # Crear un DataFrame con los datos extraídos
    df_jugadores = pd.DataFrame(jugadores_data)

    df_jugadores = df_jugadores[df_jugadores["team"] == team_analizing]
    # antes de juntar los dos dataframes voy a quitar todas las tildes prq a veces no coinciden
    replace_dict = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    df_jugadores["player"] = df_jugadores["player"].str.translate(replace_dict)
    df_pases["player"] = df_pases["player"].str.translate(replace_dict)
    df_pases["receiver"] = df_pases["receiver"].str.translate(replace_dict)

    df_pases = pd.merge(df_pases, df_jugadores, left_on="player", right_on="player", how="left")
    df_pases = pd.merge(df_pases, df_jugadores, left_on="receiver", right_on="player", how="left")

    df_pases = df_pases.drop(["position_y", "position", "team_y", "player_y"], axis=1)

    df_pases = df_pases.rename(columns={"position_x": "position", "player_x": "player", "team_x": "team", "jersey_num_x": "jersey_player", "jersey_num_y": "jersey_receiver"})

    subs = df_pases[df_pases["sub"] == True]
    subs_jerseynum = subs["jersey_player"].drop_duplicates()
    df_pases = df_pases[~df_pases["jersey_player"].isin(subs_jerseynum) & ~df_pases["jersey_receiver"].isin(subs_jerseynum)]

    #TEAM = "Barcelona"

    #FORMATION = '433'
    pass_cols = ['jersey_player', 'jersey_receiver']
    passes_formation = df_pases.loc[(df_pases.team == team_analizing) &
                                      df_pases.jersey_receiver.notnull(), pass_cols].copy()

    passes_subs = subs.loc[(subs.team == team_analizing) &
                                      subs.jersey_receiver.notnull(), pass_cols].copy()

    location_cols = ["jersey_player", "x", "y"]
    # claro pero esto es pass + receipt y yo solo tengo pass ojito
    location_formation = df_pases.loc[(df_pases.team == team_analizing), location_cols].copy()
    average_locs_and_count = (location_formation.groupby('jersey_player')
                              .agg({'x': ['mean'], 'y': ['mean', 'count']}))
    average_locs_and_count.columns = ['x', 'y', 'count']

    location_formation = location_formation.drop_duplicates()
    location_formation["jersey_player"] = location_formation["jersey_player"].astype(int)

    # calculate the number of passes between each position (using min/ max so we get passes both ways)
    passes_formation['pos_max'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .max(axis='columns'))
    passes_formation['pos_min'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .min(axis='columns'))
    passes_formation["pos_min"]=passes_formation["pos_min"].astype(int)
    passes_formation["pos_max"]=passes_formation["pos_max"].astype(int)

    passes_between = passes_formation.groupby(['pos_min', 'pos_max']).size().reset_index(name='pass_count')

    # passes_between = passes_formation.groupby(['pos_min', 'pos_max']).event_id.count().reset_index()
    # passes_between.rename({'event_id': 'pass_count'}, axis='columns', inplace=True)

    # add on the location of each player so we have the start and end positions of the lines
    passes_between = passes_between.merge(location_formation, left_on='pos_min', right_on="jersey_player")
    passes_between = passes_between.merge(location_formation, left_on='pos_max', right_on="jersey_player",
                                          suffixes=['', '_end'])

    ############################################
    MAX_LINE_WIDTH = 18
    MAX_MARKER_SIZE = 3000
    max_passesbetween=passes_between.pass_count.max()
    min_passesbetween=passes_between.pass_count.min()
    min_node_size = average_locs_and_count["count"].min()
    max_node_size = average_locs_and_count["count"].max()

    passes_between['width'] = (passes_between.pass_count / passes_between.pass_count.max() *
                               MAX_LINE_WIDTH)
    average_locs_and_count['marker_size'] = (average_locs_and_count['count']
                                             / average_locs_and_count['count'].max() * MAX_MARKER_SIZE)

    MIN_TRANSPARENCY = 0.3
    color = np.array(to_rgba('white'))
    color = np.tile(color, (len(passes_between), 1))
    c_transparency = passes_between.pass_count / passes_between.pass_count.max()
    c_transparency = (c_transparency * (1 - MIN_TRANSPARENCY)) + MIN_TRANSPARENCY
    color[:, 3] = c_transparency
    if team_analizing == home_team:
        OPPONENT = f"vs {away_team} (H) LaLiga {season}"

    elif team_analizing == away_team:
        OPPONENT = f"vs {home_team} (A) LaLiga {season}"
    # OPPONENT=" vs  Real Madrid (A) LaLiga 2023/24"
    URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf"
    oswald_regular = FontManager(URL)

    
    fig, axs = pitch.grid(
        figheight=10,
        title_height=0.08,
        endnote_space=0,
        # Turn off the endnote/title axis. I usually do this after
        # I am happy with the chart layout and text placement
        axis=False,
        title_space=0,
        grid_height=0.82,
        endnote_height=0.01,
    )
    ax = axs['pitch']  
    if type_third=="first":
       ax.set_ylim(0,50)
       ax.axhline(y=33.33, color='black', linestyle='--', linewidth=1)
       ax.spines['top'].set_visible(False)
       ax.spines['left'].set_visible(False)
       ax.xaxis.set_ticks_position('bottom')
       ax.yaxis.set_ticks_position('right')
    elif type_third=="second":
        ax.set_ylim(30,70)
        ax.axhline(y=33.33, color='black', linestyle='--', linewidth=1)
        ax.axhline(y=66.66, color='black', linestyle='--', linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('right')
    elif type_third=="third":
        ax.set_ylim(70,100)
        ax.axhline(y=66.67, color='black', linestyle='--', linewidth=1)
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.xaxis.set_ticks_position('bottom')
        ax.yaxis.set_ticks_position('right')
    fig.set_facecolor("white")
    pass_lines = pitch.lines(
        passes_between.x,
        passes_between.y,
        passes_between.x_end,
        passes_between.y_end,
        lw=passes_between.width,
        color="#BF616A",
        zorder=1,
        ax=axs["pitch"],
    )
    pass_nodes = pitch.scatter(
        average_locs_and_count.x,
        average_locs_and_count.y,
        s=average_locs_and_count.marker_size,
        color="#BF616A",
        edgecolors="black",
        linewidth=0.5,
        alpha=1,
        ax=axs["pitch"],
    )
    pass_nodes_internal = pitch.scatter(
        average_locs_and_count.x,
        average_locs_and_count.y,
        s=average_locs_and_count.marker_size / 2,
        color="white",
        edgecolors="black",
        linewidth=0.5,
        alpha=1,
        ax=axs["pitch"],
    )
    for index, row in average_locs_and_count.iterrows():
        text = pitch.annotate(
            row.name,
            xy=(row.x, row.y),
            c="black",
            va="center",
            ha="center",
            size=15,
            weight="bold",
            ax=axs["pitch"],
            fontproperties=oswald_regular.prop,
        )
        text.set_path_effects([path_effects.withStroke(linewidth=1, foreground="white")])

    TITLE_TEXT = f"{team_analizing}"
    axs["title"].text(
        0.5,
        0.7,
        TITLE_TEXT,
        color="black",
        va="center",
        ha="center",
        fontproperties=oswald_regular.prop,
        fontsize=30,
    )
    axs["title"].text(
        0.5,
        0.15,
        OPPONENT,
        color="black",
        va="center",
        ha="center",
        fontproperties=oswald_regular.prop,
        fontsize=18,
    )
    ax_leg = axs["endnote"]

    # Example circles representing node sizes
    circle1 = mpatches.Ellipse((5, -10), width=4, height=6 * ax_leg.get_data_ratio(),
                               color="#BF616A", clip_on=False)
    ax_leg.add_patch(circle1)

    circle2 = mpatches.Ellipse((11, -10), width=5.5, height=8 * ax_leg.get_data_ratio(),
                               color="#BF616A", clip_on=False)
    ax_leg.add_patch(circle2)

    circle3 = mpatches.Ellipse((19, -10), width=7.5, height=11 * ax_leg.get_data_ratio(),
                           color="#BF616A", clip_on=False)
    ax_leg.add_patch(circle3)

    # Arrow showing scale
    arrow = FancyArrowPatch(posA=(2, -18), posB=(25, -18),
                            arrowstyle="->", color="black",
                            mutation_scale=15, lw=2, clip_on=False)
    ax_leg.add_patch(arrow)

    ax_leg.text(11, -20,
                f"{min_node_size} passes        {max_node_size} passes",
                fontsize=8, va="top", ha="center", color="black")

    # Example line thickness scale
    ax_leg.plot([40, 45], [-10, -6], color="black", linewidth=1, clip_on=False)
    ax_leg.plot([45, 50], [-10, -6], color="black", linewidth=2, clip_on=False)
    ax_leg.plot([50, 55], [-10, -6], color="black", linewidth=4, clip_on=False)

    arrow = FancyArrowPatch(posA=(40, -18), posB=(60, -18),
                            arrowstyle="->", color="black",
                            mutation_scale=15, lw=2, clip_on=False)
    ax_leg.add_patch(arrow)

    ax_leg.text(50, -20,
                f"{min_passesbetween} passes           {max_passesbetween} passes",
                fontsize=8, va="top", ha="center", color="black")

    # Extra explanatory text
    ax_leg.text(80, -5,
                f"Minimum Passes: {min_passesbetween}",
                fontsize=10, va="top", ha="right", color="black")

    # Hide the axis frame for the legend area
    ax_leg.axis("off")

    output_path = f"passnetwork_{team_analizing}_{type_third}.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    return fig, output_path     
    
passnetwork_oneteam_thirds("/Users/julieta/Desktop/data_madridcff/f27/pass_matrix_903_2025_g2572345_t13320.xml", "/Users/julieta/Desktop/data_madridcff/f40/f40-squad-102.xml","second")
