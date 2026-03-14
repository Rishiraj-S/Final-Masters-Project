#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Oct  1 14:58:40 2025

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
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
import mplsoccer
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

pd.options.mode.chained_assignment = None  # Oculta SettingWithCopyWarning
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
def parse_f27(filepath_f27):
    
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
    
    return df_pases, team_analizing,home_team,away_team, season

def parse_f40(filepath_f40,team_analizing):
    
    if not os.path.exists(filepath_f40):
        print(f"Error: El archivo '{filepath_f40}' no existe.")
        return None , None

    tree = ET.parse(filepath_f40)
    root = tree.getroot()
    equipos = {team.get("uID"): team.find("Name").text for team in root.findall(".//Team")}
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
    
    return df_jugadores, equipos 

def parse_f24(file_path_24):
    if not os.path.exists(file_path_24):
        print(f"Error: El archivo '{file_path_24}' no existe.")
        return None, None
    
    tree = ET.parse(file_path_24)
    root = tree.getroot()
 
   
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
    return df_events,team_names

def get_goals(file_path_24):
    df_events,team_names=parse_f24(file_path_24)
    goals=df_events[df_events["type_id"]==16]
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    goals["local_goals"] = (goals["team_id"] == int(home_id)).cumsum()
    goals["visitor_goals"] = (goals["team_id"] == int(away_id)).cumsum()
    #print(goals.columns)
    home_goals = (goals["team_id"] == int(home_id)).sum()
    away_goals = (goals["team_id"] == int(away_id)).sum()
    goals["resultado"] = goals["local_goals"].astype(str) + "-" + goals["visitor_goals"].astype(str)
    goals["time_minutes"] = goals["min"] + goals["sec"] / 60
    goals=goals[["time_minutes","resultado"]]
    
    return goals,home_goals,away_goals

def extract_end_coordinates(qualifiers):
    end_x = None
    end_y = None
    if isinstance(qualifiers, list):  # Asegurar que la celda contiene una lista
        for item in qualifiers:
            if item.get("qualifier_id") == "140":
                end_x = float(item.get("value", 0))  # Convertir a float si existe
            elif item.get("qualifier_id") == "141":
                end_y = float(item.get("value", 0))
    return pd.Series([end_x, end_y])

def parse_f73_possesionchain(filepath_f73):
    if not filepath_f73 or not os.path.exists(filepath_f73):
        print("Error: El archivo especificado no existe.")
        return None
    tree = ET.parse(filepath_f73)
    root = tree.getroot()
    data=[]
    game = root.find("Game")
    game_data = {attr: game.attrib[attr] for attr in game.attrib}
    df_game = pd.DataFrame([game_data])
    team_names=df_game[["home_team_id","home_team_name","away_team_id","away_team_name"]]
    home_team=team_names["home_team_name"][0]
    home_id=team_names["home_team_id"][0]
    away_team=team_names["away_team_name"][0]
    away_id=team_names["away_team_id"][0]

    
    
    # Extraer eventos
    event_list = []
    for event in game.findall("Event"):
        event_data = {attr: event.attrib[attr] for attr in event.attrib}

        qualifiers = []
        for qualifier in event.findall("Q"):
            qualifiers.append({attr: qualifier.attrib[attr] for attr in qualifier.attrib})

        event_data["qualifiers"] = qualifiers  
        event_list.append(event_data)
        
    df_events = pd.DataFrame(event_list)
    df_events=df_events.drop(["last_modified","version"],axis=1)
    df_events["keypass"]=df_events["keypass"].fillna(0)
    df_events[['id', 'event_id', 'type_id', 'period_id', 'min', 'sec', 'team_id','outcome', 'x', 'y','player_id','keypass', 'sequence_id', 'possession_id']]=df_events[['id',
                                                                                                                                                                                                                                                                                                    'event_id', 'type_id', 'period_id', 'min', 'sec', 'team_id','outcome', 'x', 'y',"player_id",'keypass', 'sequence_id', 'possession_id']].astype(float)
    df_events["time_minutes"] = df_events["min"] + df_events["sec"] / 60  
    df_events[["timestamp", "timestamp_utc"]] = df_events[["timestamp", "timestamp_utc"]].apply(pd.to_datetime)
    teams = pd.concat([
    team_names[['home_team_id', 'home_team_name']].rename(columns={'home_team_id': 'team_id', 'home_team_name': 'team_name'}),
    team_names[['away_team_id', 'away_team_name']].rename(columns={'away_team_id': 'team_id', 'away_team_name': 'team_name'})
    ]).drop_duplicates()
    teams["team_id"]=teams["team_id"].astype(float)
    
    df_events = df_events.merge(teams, on="team_id", how="left")
    team1, team2 = df_events.team_name.unique()
    df_pass=df_events[df_events["type_id"]==1]
    df_pass=df_pass[df_pass["outcome"]==1]
    
    def extract_end_coordinates(qualifiers):
        end_x = None
        end_y = None
        if isinstance(qualifiers, list):  # Asegurar que la celda contiene una lista
            for item in qualifiers:
                if item.get("qualifier_id") == "140":
                    end_x = float(item.get("value", 0))  # Convertir a float si existe
                elif item.get("qualifier_id") == "141":
                    end_y = float(item.get("value", 0))
        return pd.Series([end_x, end_y])
    
    # Aplicamos la función y creamos nuevas columnas
    df_pass[["end_x", "end_y"]] = df_pass["qualifiers"].apply(extract_end_coordinates)

    df_pass=df_pass[["x","y","end_x","end_y","team_id","team_name","possession_id","type_id","time_minutes"]]
    #me quedo solo con las que pertenecen a un 

    df_pass=df_pass[df_pass["possession_id"].notna()]
    
    return df_pass,team_names

def ensure_and_convert_columns(events: pd.DataFrame) -> pd.DataFrame:
    """
    Asegura que ciertas columnas existan en el DataFrame 'events'.
    Si existen, las convierte a numérico con string_to_numeric.
    Si no existen, las crea vacías (NaN).
    Retorna el DataFrame modificado.
    """
    # Lista de columnas a asegurar
    cols = ['min', 'sec', 'x', 'y', '102', '103', '146', '147', 'outcome']

    for col in cols:
        if col in events.columns:
            events[col] = string_to_numeric(events[col])
        else:
            events[col] = 0  # crea columna vacía

    return events

def string_to_numeric(x):
    return pd.to_numeric(x, errors='coerce')

def parse_f70_events(xml_filename):
    """
    Parses an XML file containing event data from a sports game and enriches it with player names based on team and player information.

    Parameters:
    -----------
    xml_filename : str
        The file path to the XML file containing event data.

    Returns:
    --------
    events : pandas.DataFrame
        A DataFrame containing the parsed events, enriched with player names and numeric values for relevant fields.

    Notes:
    ------
    - The function reads and parses the XML data to extract event attributes and values, including qualifiers.
    - Player names are matched to events based on player IDs, derived from team data in the same XML file.
    - Certain string fields are converted to numeric types to facilitate further analysis.
    - The function constructs a comprehensive DataFrame with columns for event details, player names, and statistics.

    Example:
    ---------
    >>> events_df = parse_f70_events('events.xml')
    """
    import xml.etree.ElementTree as ET
    
    # Define functions to be used

    
    
    ## Pick the Maximum (non-NA) Values
    
    def pick_out_the_maximum_values(qualifier_values):
        
        max_values = []
        for c in range(qualifier_values.shape[1]):
            col_2_test = qualifier_values.iloc[:, c]
            max_val = col_2_test.dropna().iloc[0]
            max_values.append(max_val)
        results_Q = pd.DataFrame([max_values], columns=qualifier_values.columns)
        return results_Q
    
    ## The Main Unpacking Function
    
    def convert_event_node_row(xml_2_spread):
      
        ## convert the info in the event node header into a dataframe 
        results = pd.DataFrame(xml_2_spread['attrs'], index=[0])
    
        ## find the number of qualifiers for this event 
        no_of_qualifiers = len(xml_2_spread['value'])
        
        if no_of_qualifiers > 0:
            ## create a list of qualifiers 
            Qualifier_Unpacked_Step1 = pd.DataFrame()
        
            ## loop through each qualifer and pull out the info then bind it to the results .. above 
            for Q in range(no_of_qualifiers):
                Qualifier_unpacked = xml_2_spread['value'][Q]

                Value = 1 if 'value' not in Qualifier_unpacked.keys() else Qualifier_unpacked["value"]
                temp = pd.DataFrame({"Q": [str(Value)]}, dtype=str)
                temp.columns = [Qualifier_unpacked["qualifier_id"]]
                Qualifier_Unpacked_Step1 = pd.concat([Qualifier_Unpacked_Step1, temp], axis=0, ignore_index=True)
            
            ## keep the maximum values in the dataframe (the only none NA values) return as a 
            ## dataframe for use 
            Qualifier_unpacked_df = pick_out_the_maximum_values(Qualifier_Unpacked_Step1)
        
            results = pd.concat([results, Qualifier_unpacked_df], axis=1)
        
        return results
    
    # Read in the XML File
    pbpParse = ET.parse(xml_filename)
    
    
  
    # Split the XML File
    all_event_nodes = []
    for event in pbpParse.findall('.//Game/Event'):
        event_attrs = event.attrib
        event_values = [child.attrib for child in list(event)]
        all_event_nodes.append({'attrs': event_attrs, 'value': event_values})
  
    # Convert all events and store in a dataframe
    events = pd.concat([convert_event_node_row(e) for e in all_event_nodes], ignore_index=True)
      
    
    # Add player names to events
    players = {}
    player_name = None
    for i, team in enumerate(pbpParse.findall('.//Team')):
        team_code = int(team.get('uID')[1:])
        players[f'team{i+1}_code'] = team_code
        players[f'playert{i+1}'] = [{'code': int(player.get('uID')[1:]), 'position': player.get('Position'), 'name': player.find('.//PersonName/First').text + ' ' + player.find('.//PersonName/Last').text} for player in team.findall('Player')]
    
    for idx, event in events.iterrows():
        team_code = event['team_id']
        j = 1 if team_code == str(players[f'team{1}_code']) else 2
        for player in players[f'playert{j}']:
            if player['code'] == int(event['player_id']):
                player_name = player['name']
                break
        events.at[idx, 'player_name'] = player_name

    # Convert strings to numerics
    #events['min'] = string_to_numeric(events['min'])
    # events['sec'] = string_to_numeric(events['sec'])
    # events['x'] = string_to_numeric(events['x'])
    # events['y'] = string_to_numeric(events['y'])
    # events['102'] = string_to_numeric(events['102'])
    # events['103'] = string_to_numeric(events['103'])
    # events['146'] = string_to_numeric(events['146'])
    # events['147'] = string_to_numeric(events['147'])
    # events['outcome'] = string_to_numeric(events['outcome'])
    events = ensure_and_convert_columns(events)
    return events 
#### funcion  


def cercania_porteria_lateral(filepath_f24,filepath_f70,filepath_f73):
    
    #"/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml"
    df_events,team_names=parse_f24(filepath_f24)
    goals,home_goals,away_goals=get_goals(filepath_f24)
    
    df_pass=df_events[df_events["type_id"]==1].copy()
    df_pass[["end_x", "end_y"]] = df_pass["qualifiers"].apply(extract_end_coordinates)
    df_pass["time_minutes"] = df_pass["min"] + df_pass["sec"] / 60
    df_pass=df_pass[["period_id","time_minutes","team_id","x","y","end_x","end_y"]]
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    home_team=team_names["home_team_name"].iloc[0]
    away_team=team_names["away_team_name"].iloc[0]
    df_home_pass = df_pass[df_pass["team_id"] == int(home_id)]
    df_away_pass = df_pass[df_pass["team_id"] == int(away_id)]

    df_home_pass["av_x"]=(df_home_pass["x"]+df_home_pass["end_x"])/2
    df_home_pass["av_y"]=(df_home_pass["y"]+df_home_pass["end_y"])/2

    df_away_pass["av_x"]=(df_away_pass["x"]+df_away_pass["end_x"])/2
    df_away_pass["av_y"]=(df_away_pass["y"]+df_away_pass["end_y"])/2

    df_home_pass=df_home_pass[["period_id","time_minutes","av_x","av_y"]]
    df_away_pass=df_away_pass[["period_id","time_minutes","av_x","av_y"]]

    df_home_pass["rolling_x"] = df_home_pass["av_x"].rolling(30).mean()
    df_home_pass["rolling_y"] = df_home_pass["av_y"].rolling(30).mean()

    df_home_pass=df_home_pass.dropna()

    df_home_x=df_home_pass[["time_minutes","rolling_x"]]
    df_home_x = (
        df_home_pass[["time_minutes", "rolling_x"]]
        .groupby("time_minutes", as_index=False)  # group by minute
        .last()                          # keep the last row for each minute
    )
    df_home_y=df_home_pass[["time_minutes","rolling_y"]]
    df_home_y = (
        df_home_pass[["time_minutes", "rolling_y"]]
        .groupby("time_minutes", as_index=False)  # group by minute
        .last()                          # keep the last row for each minute
    )

    df_away_pass["rolling_x"] = df_away_pass["av_x"].rolling(30).mean()
    df_away_pass["rolling_y"] = df_away_pass["av_y"].rolling(30).mean()
    df_away_pass=df_away_pass.dropna()
    df_away_x=df_away_pass[["time_minutes","rolling_x"]]
    df_away_y=df_away_pass[["time_minutes","rolling_y"]]
    minutes=np.arange(0, 91)

    df_plot1 = (
        pd.concat([
            df_home_pass.assign(team=home_team),
            df_away_pass.assign(team=away_team)
        ])
    )

    # Plot with seaborn
    plt.figure(figsize=(10, 5))
    sns.lineplot(
        data=df_plot1,
        x="time_minutes", y="rolling_x",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"}
    )
    ax = plt.gca()
    plt.axhline(y=50, color="black", linestyle="--", linewidth=1, label="Eje central")
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    max_time=df_plot1["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    plt.xlim(0, max_time+2)
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Cercanía a la portería Rival")

    plt.legend()
    sns.despine()
    plt.savefig("cercania_rival.png",dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    # Plot with seaborn
    plt.figure(figsize=(10, 5))
    sns.lineplot(
        data=df_plot1,
        x="time_minutes", y="rolling_y",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"}
    )
    ax = plt.gca()
    plt.axhline(y=50, color="black", linestyle="--", linewidth=1, label="Eje central")
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    max_time=df_plot1["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    plt.xlim(0, max_time+2)
    plt.xlabel("Tiempo (minutos)")
    plt.ylabel("Banda Izquierda vs Banda Derecha")

    plt.legend()
    sns.despine()
    y_max = df_plot1["rolling_y"].max()
    y_min = df_plot1["rolling_y"].min()

    plt.ylim(y_min-2,y_max+1)
    

    plt.text(
        x=10,  y=y_max+2,  
        s="Banda Izquierda",
        ha="center", va="bottom",
        fontsize=8, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="square,pad=0.5")
    )

    plt.text(
        x=10, y=y_min + (y_max - y_min) * 0.05,  
        s="Banda Derecha",
        ha="center", va="top",
        fontsize=8, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="black", boxstyle="square,pad=0.5")
    )
   
    plt.savefig("lateralidad.png",dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    df_events,team_names=parse_f24(filepath_f24)
    df_pass=df_events[df_events["type_id"]==1].copy()
    df_pass["time_minutes"] = df_pass["min"] + df_pass["sec"] / 60
    df_pass=df_pass[["period_id","time_minutes","team_id","x","y"]]
    df_pass = df_pass.sort_values(by=["time_minutes"]).reset_index(drop=True)
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    home_team=team_names["home_team_name"].iloc[0]
    away_team=team_names["away_team_name"].iloc[0]
    df_home_pass_count = df_pass[df_pass["team_id"] == int(home_id)]
    df_away_pass_count = df_pass[df_pass["team_id"] == int(away_id)]

    df_home_pass_count["cumulative"]=range(1,len(df_home_pass_count)+1)
    df_away_pass_count["cumulative"]=range(1,len(df_away_pass_count)+1)

    df_plot2 = (
        pd.concat([
            df_home_pass_count.assign(team=home_team),
            df_away_pass_count.assign(team=away_team)
        ])
    )

    df_diff = df_home_pass_count[["time_minutes", "cumulative"]].rename(columns={"cumulative": "home"})
    df_diff = df_diff.merge(
        df_away_pass_count[["time_minutes", "cumulative"]].rename(columns={"cumulative": "away"}),
        on="time_minutes",
        how="outer"
    )
    df_diff = df_diff.sort_values("time_minutes").reset_index(drop=True)

    # Forward-fill NaNs
    df_diff["home"] = df_diff["home"].ffill().fillna(0)
    df_diff["away"] = df_diff["away"].ffill().fillna(0)

    # Compute difference
    df_diff["diff_passes"] = df_diff["home"] - df_diff["away"]

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot2,
        x="time_minutes", y="cumulative",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"},
        ax=ax
    )
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    max_time=df_plot2["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Pases acumulados")
    ax.legend(loc="lower right")
    sns.despine()

    # === Inset plot ===
    # Define position [left, bottom, width, height] in figure-relative coords
    inset_ax = ax.inset_axes([0.10, 0.65, 0.3, 0.3])  


    sns.lineplot(
        data=df_diff,
        x="time_minutes", y="diff_passes",
        color="black", linewidth=1,
        ax=inset_ax
    )
    for _, row in goals.iterrows():
        inset_ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        inset_ax.text(row["time_minutes"], inset_ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")

    inset_ax.set_xlabel("tiempo (min)", fontsize=8)
    inset_ax.set_ylabel("Diferencia pases", fontsize=8)
    inset_ax.tick_params(axis='both', labelsize=8)

    plt.savefig("pases_acumulados.png", dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    list_defensive=[4,7,8,45]
    df_defensive=df_events[df_events["type_id"].isin(list_defensive)].copy()

    df_defensive["time_minutes"]=df_defensive["min"] + df_defensive["sec"] / 60

    df_home_def=df_defensive[df_defensive["team_id"] == int(home_id)]
    df_away_def=df_defensive[df_defensive["team_id"] == int(away_id)]

    df_home_def["cumulative"]=range(1,len(df_home_def)+1)
    df_away_def["cumulative"]=range(1,len(df_away_def)+1)
    df_plot1 = (
        pd.concat([
            df_home_def.assign(team=home_team),
            df_away_def.assign(team=away_team)
        ])
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot1,
        x="time_minutes", y="cumulative",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"},
        ax=ax
    )
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    max_time=df_plot1["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Acciones defensivas acumuladas")
    ax.legend(loc="lower right")
    sns.despine()
    df_diff = df_home_def[["time_minutes", "cumulative"]].rename(columns={"cumulative": "home"})
    df_diff = df_diff.merge(
        df_away_def[["time_minutes", "cumulative"]].rename(columns={"cumulative": "away"}),
        on="time_minutes",
        how="outer"
    )
    df_diff = df_diff.sort_values("time_minutes").reset_index(drop=True)

    # Forward-fill NaNs
    df_diff["home"] = df_diff["home"].ffill().fillna(0)
    df_diff["away"] = df_diff["away"].ffill().fillna(0)

    # Compute difference
    df_diff["diff_def"] = df_diff["home"] - df_diff["away"]
    # === Inset plot ===
    # Define position [left, bottom, width, height] in figure-relative coords
    inset_ax = ax.inset_axes([0.10, 0.65, 0.3, 0.3])  


    sns.lineplot(
        data=df_diff,
        x="time_minutes", y="diff_def",
        color="black", linewidth=1,
        ax=inset_ax
    )
    for _, row in goals.iterrows():
        inset_ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        inset_ax.text(row["time_minutes"], inset_ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")

    inset_ax.set_xlabel("tiempo (min)", fontsize=8)
    inset_ax.set_ylabel("Diferencia acciones defensivas", fontsize=8)
    inset_ax.tick_params(axis='both', labelsize=8)

        
    plt.savefig("acc_defensivas_acumuladas.png", dpi=300, bbox_inches='tight')
    #plt.show()

    df_home_def["rolling_x"] = df_home_def["x"].rolling(10).mean()
    df_away_def["rolling_x"] = df_away_def["x"].rolling(10).mean()

    df_plot2 = (
        pd.concat([
            df_home_def.assign(team=home_team),
            df_away_def.assign(team=away_team)
        ])
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot2,
        x="time_minutes", y="rolling_x",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"},
        ax=ax
    )
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    max_time=df_plot2["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Situación de la acción defensiva respecto a la portería rival")
    ax.axhline(y=50, color="gray", linestyle="--", linewidth=1, label="Eje central")
    ax.legend(loc="upper left")
    sns.despine()
    


    plt.savefig("altura_acc_defensivas.png", dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    df_pass,team_names=parse_f73_possesionchain(filepath_f73)

    df_pass["x_diff"]=df_pass.groupby("possession_id")["x"].diff().abs()

    df_pass["t_diff"] = (
        df_pass.groupby("possession_id")["time_minutes"]
               .transform(lambda x: x.iloc[-1] - x.iloc[0])
    )
    sums = (
        df_pass.groupby("possession_id")
        .agg({
            "x_diff": "sum",
            "time_minutes":"last",
            "t_diff":"first",
            "team_id": "first"  
        })
        .reset_index()
    )

    sums.rename(columns={"x_diff": "total_diff"}, inplace=True)

    sums["velocity"]=sums["total_diff"]/sums["t_diff"]
    sums["velocity"] = sums["total_diff"] / (sums["t_diff"] * 60)
    sums_home=sums[sums["team_id"]==int(home_id)]
    sums_away=sums[sums["team_id"]==int(away_id)]
    df_plot3 = (
        pd.concat([
            sums_home.assign(team=home_team),
            sums_away.assign(team=away_team)
        ])
    )

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot3,
        x="time_minutes", y="velocity",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"},
        ax=ax
    )
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    ax.axhline(y=sums_home["velocity"].mean(), color="red", linestyle="--", linewidth=1)
    ax.axhline(y=sums_away["velocity"].mean(), color="blue", linestyle="--", linewidth=1)
    ax.set_ylim(0,20)
    max_time=df_plot3["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Ritmo de juego (m/s)")

    ax.legend(loc="upper left")
    sns.despine()

    
    plt.savefig("ritmo_juego.png", dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    total_long = (
        df_pass.groupby("possession_id")
        .agg({
            "time_minutes": "last",
            "team_id":"first",
            "possession_id": "count"   
        })
        .rename(columns={"possession_id": "num_passes"})
        .reset_index()
    )

    total_long_home=total_long[total_long["team_id"]==int(home_id)]
    total_long_home["num_passes"]=total_long_home["num_passes"].rolling(10).mean()
    total_long_away=total_long[total_long["team_id"]==int(away_id)]
    total_long_away["num_passes"]=total_long_away["num_passes"].rolling(10).mean()
    df_plot4 = (
        pd.concat([
            total_long_home.assign(team=home_team),
            total_long_away.assign(team=away_team)
        ])
    )
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot4,
        x="time_minutes", y="num_passes",
        hue="team", linewidth=2,
        palette={home_team: "red", away_team: "blue"},
        ax=ax
    )
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    ax.axhline(y=total_long_home["num_passes"].mean(), color="red", linestyle="--", linewidth=1)
    ax.axhline(y=total_long_away["num_passes"].mean(), color="blue", linestyle="--", linewidth=1)
    ax.set_ylim(0,20)
    max_time=df_plot4["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Longitud de la secuencia (pases)")

    ax.legend(loc="upper left")
    sns.despine()

    plt.savefig("longitud_pases.png", dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    events=parse_f70_events(filepath_f70)
    shot_events = events[events['type_id'].isin(['13', '14', '15', '16'])]
    shot_events["team_id"]=shot_events["team_id"].astype(int)
    shot_events["time_minutes"]=shot_events["min"]+shot_events["sec"]/60
    shot_events["321"]=shot_events["321"].astype(float)

    shot_events=shot_events[["time_minutes","team_id","321"]]
    shot_events_home=shot_events[shot_events["team_id"]==int(home_id)]
    shot_events_away=shot_events[shot_events["team_id"]==int(away_id)]

    shot_events_home["cumulative"]=shot_events_home["321"].cumsum()
    shot_events_away["cumulative"]=shot_events_away["321"].cumsum()
    total_xg_home=shot_events_home["cumulative"].max()
    total_xg_away=shot_events_away["cumulative"].max()
    
    df_plot4 = (
        pd.concat([
            shot_events_home.assign(team=home_team),
            shot_events_away.assign(team=away_team)
        ])
    )
    df_plot4 = df_plot4.sort_values(['team','time_minutes'])
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(
        data=df_plot4,
        x="time_minutes", y="cumulative",
        hue="team", linewidth=1,
        palette={home_team: "red", away_team: "blue"},
        ax=ax,drawstyle='steps-pre'
    )
    teams = df_plot4['team'].unique()
    colors = {home_team: "red", away_team: "blue"}
    for _, row in goals.iterrows():
        ax.axvline(x=row["time_minutes"], color="gray", linestyle="--", alpha=0.7)
        ax.text(row["time_minutes"], ax.get_ylim()[1]*0.95, row["resultado"],
                rotation=90, verticalalignment='top', horizontalalignment='right', color="black")
    for team in teams:
        team_data = df_plot4[df_plot4['team'] == team].sort_values('time_minutes').reset_index(drop=True)
        
        # Loop over all points except the last one (since it has no "next" point)
        for i in range(len(team_data)):
            if i < len(team_data) - 1:
                
                y_value = team_data.loc[i + 1, 'cumulative']
            else:

                y_value = team_data.loc[i, 'cumulative']

            x_value = team_data.loc[i, 'time_minutes']

            ax.scatter(
                x_value, y_value,
                color=colors[team], edgecolor='black', s=30, zorder=5
                )

    max_time=df_plot4["time_minutes"].max()
    if pd.isna(max_time) or max_time == float('inf'):
        max_time = 90 
    ax.set_xlim(0, max_time+2)
    ax.set_xlabel("Tiempo (minutos)")
    ax.set_ylabel("Evolución de xG")

    home_handle = mlines.Line2D([], [], color="red", linewidth=2, label=f"{home_goals} - {home_team} (xG={total_xg_home:.2f})")
    away_handle = mlines.Line2D([], [], color="blue", linewidth=2, label=f"{away_goals} - {away_team} (xG={total_xg_away:.2f})")

    ax.legend(handles=[home_handle, away_handle], loc="upper left")
    sns.despine()

    plt.savefig("xG_evolution.png", dpi=300, bbox_inches='tight')
    #plt.show()
    plt.close()
    
    events=parse_f70_events(filepath_f70)
    shot_events = events[events['type_id'].isin(['13', '14', '15', '16'])]
    shot_events["type_id"]=shot_events["type_id"].astype(int)
    shot_events["321"]=shot_events["321"].astype(float)
    ####
    df_pass,team_names=parse_f73_possesionchain(filepath_f73)
    home_team=team_names["home_team_name"].iloc[0]
    away_team=team_names["away_team_name"].iloc[0]
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    ####

    mask = shot_events["team_id"] == (home_id)
    shot_events.loc[mask, "x"] = 100 - shot_events.loc[mask, "x"]
    shot_events.loc[mask, "y"] = 100 - shot_events.loc[mask, "y"]

    scaler = MinMaxScaler(feature_range=(100, 500))  # tamaño mínimo 50, máximo 300
    shot_events["321"] = scaler.fit_transform(shot_events[["321"]])

    df_miss=shot_events[shot_events["type_id"]==13]
    df_post=shot_events[shot_events["type_id"]==14]
    df_blocked=shot_events[shot_events["type_id"]==15]
    df_goals=shot_events[shot_events["type_id"]==16]



    pitch = Pitch(pitch_type="opta",pad_bottom=0.5, goal_type='box', goal_alpha=0.8)  
    fig, ax = pitch.draw(figsize=(12, 10))  

    pitch.scatter(df_miss.x, df_miss.y,  
                  s=df_miss["321"], c='red', edgecolors='black', marker='o', ax=ax, label="Fuera",alpha=0.6)
    pitch.scatter(df_post.x, df_post.y,  
                  s=df_post["321"], c='orange', edgecolors='black', marker='o', ax=ax, label="Palo",alpha=0.6)
    pitch.scatter(df_blocked.x, df_blocked.y,  
                  s=df_blocked["321"], c='yellow', edgecolors='black', marker='o', ax=ax, label="Bloqueado",alpha=0.6)
    pitch.scatter(df_goals.x, df_goals.y,  
                  s=df_goals["321"], c='green', edgecolors='black', marker='*', ax=ax, label="Gol",alpha=0.6)

    ax.legend(loc="upper right", fontsize=12)
    ax.text(x=25,y=90,s=f"{home_goals} - {home_team} (xG={total_xg_home:.2f})",size=18, color="black",
             va='center', ha='center')
    ax.text(x=75,y=90,s=f"{away_goals} - {away_team} (xG={total_xg_away:.2f})",size=18, color="black",
             va='center', ha='center')
    ax.legend(loc="lower right")

    output_path = f"ShotMap.png"

    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    #plt.show()
    events = parse_f70_events(filepath_f70)
    
    shot_events = events[events['type_id'].isin(['13', '14', '15', '16'])]
    shot_events["type_id"] = shot_events["type_id"].astype(int)
    shot_events["321"] = shot_events["321"].astype(float)
    scaler = MinMaxScaler(feature_range=(100, 500))
    shot_events["321"] = scaler.fit_transform(shot_events[["321"]])
    

    shot_events["end_location_x"] = 100
    shot_events["end_location_y"] = shot_events["102"].astype(float)
    shot_events["end_location_z"] = shot_events["103"].astype(float)

    shot_events['outcome_name'] = np.where(shot_events['type_id'] == 16, 'Goal', 'Miss')

    scaler = MinMaxScaler(feature_range=(100, 500))
    shot_events["321"] = scaler.fit_transform(shot_events[["321"]])

    df_shots = shot_events[['end_location_y', 'end_location_z', 'outcome_name', "321", "team_id"]].copy()
    df_shots["team_id"] = df_shots["team_id"].astype(int)

    # home_id = 13320
    # away_id = 11212
    #print("TYPE:",df_shots["team_id"].dtype)
    # print("ids:",df_shots["team_id"].unique())
    # print("HOME Y AWAY:",home_id,away_id)
    df_home = df_shots[df_shots["team_id"] == int(home_id)]
    df_away = df_shots[df_shots["team_id"] == int(away_id)]

    fig, axs = plt.subplots(2, 1,figsize=(8,8))  # 1 row, 2 columns

    for ax, df_team, team_name in zip(axs, [df_home, df_away], ["Home", "Away"]):
        goals = df_team[df_team["outcome_name"] == "Goal"]
        miss = df_team[df_team["outcome_name"] != "Goal"]

        ax.set_xlim(35, 65)
        ax.set_ylim(0, 90)

        # Goal coordinates
        goal_y = 0
        goal_height = 40
        goal_left = 44.2
        goal_right = 55.8
        img=mpimg.imread(f"{BASE_DIR}/forwards_analisis/goal.jpg")
        ax.imshow(
            img,
            extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
            aspect='auto',  # stretch to fit area
            zorder=0  # put it behind the rectangles
        )
        # Draw goal posts
        # ax.plot([goal_left, goal_left], [goal_y, goal_y + goal_height], color='black', linewidth=2)
        # ax.plot([goal_right, goal_right], [goal_y, goal_y + goal_height], color='black', linewidth=2)
        # ax.plot([goal_left, goal_right], [goal_y + goal_height, goal_y + goal_height], color='black', linewidth=2)

        # Scatter goals and misses
        ax.scatter(goals.end_location_y, goals.end_location_z,
                   s=goals["321"], c='red', edgecolors='black', marker='o', label="Goal", alpha=0.6)
        ax.scatter(miss.end_location_y, miss.end_location_z,
                   s=miss["321"], c='blue', edgecolors='black', marker='o', label="Miss", alpha=0.6)

        # Remove ticks and spines
        ax.set_xticks([])
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        if team_name=="Home":
            ax.set_title(f"{home_team} tiros a puerta frente a {away_team} \n\nGoles: {home_goals} \n\nxG:{total_xg_home:.2f}",loc="left")
        elif team_name=="Away":
            ax.set_title(f"{away_team} tiros a puerta frente a {home_team} \n\nGoles: {away_goals} \n\nxG:{total_xg_away:.2f}",loc="left")
        # ax.legend()

    output_path="xG_porteria.png"
    plt.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.tight_layout()
    plt.show()
    plt.close()
    
    all_output_paths=["cercania_rival.png","lateralidad.png","pases_acumulados.png","acc_defensivas_acumuladas.png",
                      "altura_acc_defensivas.png","ritmo_juego.png","longitud_pases.png","xG_evolution.png",
                      "ShotMap.png","xG_porteria.png"]
    return all_output_paths,total_xg_home,total_xg_away
    
    

def parse_f27(filepath_f27):
    
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
    
    return df_pases, team_analizing,home_team,away_team, season

def parse_f40(filepath_f40,team_analizing):
    
    if not os.path.exists(filepath_f40):
        print(f"Error: El archivo '{filepath_f40}' no existe.")
        return None , None

    tree = ET.parse(filepath_f40)
    root = tree.getroot()
    equipos = {team.get("uID"): team.find("Name").text for team in root.findall(".//Team")}
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
    
    return df_jugadores, equipos 

def parse_f24(file_path_24):
    if not os.path.exists(file_path_24):
        print(f"Error: El archivo '{file_path_24}' no existe.")
        return None, None
    
    tree = ET.parse(file_path_24)
    root = tree.getroot()
 
   
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
    return df_events,team_names


def Heatmap_one_team(team_analizing, file_path_40, file_path_24):
    
    URL = 'https://raw.githubusercontent.com/googlefonts/roboto/main/src/hinted/Roboto-Regular.ttf'
    URL2 = 'https://raw.githubusercontent.com/google/fonts/main/apache/robotoslab/RobotoSlab[wght].ttf'
    robotto_regular = FontManager(URL)
    robboto_bold = FontManager(URL2)
    _, equipos=parse_f40(file_path_40,team_analizing)
    df_events,team_names=parse_f24(file_path_24)
    
    df_equipos = pd.DataFrame(list(equipos.items()), columns=["team_id", "team_name"])
    df_equipos["team_id"] = df_equipos["team_id"].str.extract('(\\d+)').astype(int)
    df_equipos.set_index("team_id", inplace=True)
    
    tree = ET.parse(file_path_40)
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
        
    
   
    df_events_ = df_events[df_events["team_id"]==team_id][["x", "y"]]
    #print(df_events_.columns)
    if team_analizing==away_team:
       
        df_events_["x"]=100-df_events_["x"]
        df_events_["y"]=100-df_events_["y"]

    green_red_cmap = LinearSegmentedColormap.from_list("GreenRed", ['#00FF00', '#FF0000'], N=100)
    pitch = Pitch(pitch_type='opta', line_color='#000009', line_zorder=2)
    fig, axs = pitch.grid(figheight=10, title_height=0.08, endnote_space=0, title_space=0, axis=False, grid_height=0.82, endnote_height=0.03)
    
    pitch.kdeplot(df_events_.x, df_events_.y, ax=axs['pitch'], fill=True, levels=100, thresh=0, cut=4, cmap=green_red_cmap)
    if team_analizing==home_team:
        arrow = FancyArrowPatch(
            (0.4, 0.015),    
            (0.6, 0.015),   
            transform=axs['pitch'].transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=30,  
            linewidth=2
            )
        axs['pitch'].add_patch(arrow)
    elif team_analizing==away_team:

        arrow = FancyArrowPatch(
            (0.6, 0.015),    
            (0.4, 0.015),   
            transform=axs['pitch'].transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=30,  
            linewidth=2
            )
        axs['pitch'].add_patch(arrow)
   
    #axs['title'].text(0.5, 0.7, f"{team_analizing}'s Actions", color='#000009', va='center', ha='center', fontproperties=robotto_regular.prop, fontsize=30)
    #axs['title'].text(0.5, 0.25, f"{home_team} vs {away_team}", color='#000009', va='center', ha='center', fontproperties=robotto_regular.prop, fontsize=20)
    output_path = f"heatmap_{team_analizing}.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    plt.close(fig)
    return output_path

def passnetwork_oneteam(filepath_f27, filepath_f40,MIN_PASS):
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

    df_pases, team_analizing,home_team,away_team,season=parse_f27(filepath_f27)
    
    pitch = Pitch(
       pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,
       )
    #print(df_pases["x"])
    
    df_jugadores, equipos =parse_f40(filepath_f40,team_analizing)

    replace_dict = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")

    df_pases["player"] = df_pases["player"].str.translate(replace_dict)
    df_pases["receiver"] = df_pases["receiver"].str.translate(replace_dict)
    
    df_pases = pd.merge(df_pases, df_jugadores, left_on="player", right_on="player", how="left")
    df_pases = pd.merge(df_pases, df_jugadores, left_on="receiver", right_on="player", how="left")

    df_pases = df_pases.drop(["position_y", "position", "team_y", "player_y"], axis=1)

    df_pases = df_pases.rename(columns={"position_x": "position", "player_x": "player", "team_x": "team", "jersey_num_x": "jersey_player", "jersey_num_y": "jersey_receiver"})
    mask = df_pases["team"] == (away_team)
    df_pases.loc[mask, "x"] = 100 - df_pases.loc[mask, "x"]
    df_pases.loc[mask, "y"] = 100 - df_pases.loc[mask, "y"]
    
    subs = df_pases[df_pases["sub"] == True]
    subs_jerseynum = subs["jersey_player"].drop_duplicates()
    df_pases = df_pases[~df_pases["jersey_player"].isin(subs_jerseynum) & ~df_pases["jersey_receiver"].isin(subs_jerseynum)]
    
    #hasta aqui tengo un df que es 'player', 'position', 'x', 'y', 'receiver', 'pases', 'sub','entry_minute', 'team', 'jersey_player', 'jersey_receiver']
    #con solo los titulares

    pass_cols = ['jersey_player', 'jersey_receiver']
    #passes formation es basicamente todos los pases que se dan entre titulares
    passes_formation = df_pases.loc[(df_pases.team == team_analizing) &
                                      df_pases.jersey_receiver.notnull(), pass_cols].copy()
    #passes subs es pases dirigidos A subs, que luego se eliminan
    passes_subs = subs.loc[(subs.team == team_analizing) &
                                      subs.jersey_receiver.notnull(), pass_cols].copy()

    location_cols = ["jersey_player", "x", "y"]

    #location formation es donde esta cada jugador, x,y del campo
    location_formation = df_pases.loc[(df_pases.team == team_analizing), location_cols].copy()
    #average locs and count es el average de las location Y cuenta el número de pases hechos por cada jugador
    average_locs_and_count = (location_formation.groupby('jersey_player')
                              .agg({'x': ['mean'], 'y': ['mean', 'count']}))
    
    
    average_locs_and_count.columns = ['x', 'y', 'count']

    location_formation = location_formation.drop_duplicates()
    #location formation de donde esta cada jugador en el campo
    location_formation["jersey_player"] = location_formation["jersey_player"].astype(int)
    passes_formation['pos_max'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .max(axis='columns'))
    passes_formation['pos_min'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .min(axis='columns'))
    passes_formation["pos_min"]=passes_formation["pos_min"].astype(int)
    passes_formation["pos_max"]=passes_formation["pos_max"].astype(int)
    #passes_formation.to_excel("passes_formation.xlsx",index=False)
    passes_between = passes_formation.groupby(['pos_min',"pos_max"]).size().reset_index(name='pass_count')

    # add on the location of each player so we have the start and end positions of the lines
    passes_between = passes_between.merge(location_formation, left_on='pos_min', right_on="jersey_player")
    passes_between = passes_between.merge(location_formation, left_on='pos_max', right_on="jersey_player",
                                          suffixes=['', '_end'])
    
    player_location_df = (
        df_pases[["player", "x", "y", "pases"]]
        .groupby("player")
        .agg({
            "x": "mean",
            "y": "mean",
            "pases": "sum"
            })
        .reset_index()
        )
    
    
    players_passes_df=df_pases[["player","receiver","pases"]]
    
    players_passes_df = players_passes_df.merge(player_location_df[['player', 'x', 'y']], 
                                        left_on='player', right_on='player').\
                                            rename(columns={'x': 'passer_x', 
                                                            'y': 'passer_y'}
                                                   )

    players_passes_df = players_passes_df.merge(player_location_df[['player', 'x', 'y']], 
                                            left_on='receiver', right_on='player').\
                                                rename(columns={'x': 'recipient_x', 
                                                                'y': 'recipient_y', 
                                                                'player_x': 'player'}
                                                    ) 
    players_passes_df.drop("player_y",axis=1,inplace=True)
    player_location_df=player_location_df.rename(columns={"pases":"total"})
    players_passes_df=players_passes_df.rename(columns={"pases":"passes","receiver":"pass_recipient"})
    player_names=df_pases[["player","jersey_player"]].drop_duplicates().copy()
    player_names_dict = dict(zip(player_names["player"], player_names["player"]))

    players = pd.unique(players_passes_df[['player', 'pass_recipient']].values.ravel())


    players_loc=player_location_df[["player","x","y"]]
    players_passes_df=players_passes_df[players_passes_df["passes"]>MIN_PASS]
    
    #aqui creo el grafo
    g = ig.Graph(directed=True)
    
    #y aqui añado vertices, los nodos, cada jugador
    g.add_vertices(list(players))

    #aqui los links entre jugadores
    #defino
    edges=list(zip(players_passes_df["player"],players_passes_df["pass_recipient"]))
    
    #añado
    g.add_edges(edges)
    
    #aqui añado los pesos
    g.es["weight"]=players_passes_df["passes"].tolist()
    
    #añado las coordenadas de cada jugador
    coords={}
    for _,row in players_loc.iterrows():
        player=row["player"]
        coords.setdefault(player,[]).append((row["x"],row["y"]))
       
    layout=[coords[player] for player in players]
    
    layout = [coords[player][0] for player in g.vs['name']]

    
    node_fill = "#2F6DB3"
    node_edge = "#2F6DB3"

    edge_color = "#C4B5FD99"
    
    g.vs["color"] = node_fill
    g.vs["frame_color"] = node_edge
    g.vs["frame_width"] = 1.0
    g.es["color"] = edge_color
    
    g.vs["label_dist"]=0.5
    g.vs['label_angle'] = -math.pi/2  
    g.vs['label_size'] = 6    # bigger font size
    g.vs['label_color'] = 'black'
    g.es["arrow_size"]  = 1.4   # 0.8–1.4 usually looks good
    g.es["arrow_width"] = 1.0  
    #fig, ax = plt.subplots()
    
    #asignamos labels a cada vertice, con la label siendo el nombre
    g.vs['label'] = g.vs['name']
    g.es['weight'] = players_passes_df['passes'].tolist()
    max_edge_weight = max(g.es["weight"])
    weights = np.array(g.es['weight'])
    
    #normalizo prq sino no se nota tanto
    min_width, max_width = 1, 7
    scaled_widths = min_width + (weights - weights.min()) / (weights.max() - weights.min()) * (max_width - min_width)
    #controls width of lines
    g.es['width'] = scaled_widths.tolist()
    
    total_passes = players_passes_df.groupby('player')['passes'].sum()
    norm = mcolors.Normalize(vmin=min(total_passes), vmax=max(total_passes))
    cmap = cm.get_cmap('YlOrRd')  # or 'coolwarm', 'plasma', etc.
    

    # Map each player to a color
    #vertex_colors = [mcolors.to_hex(cmap(norm(total_passes.get(player, 0))))
    #                 for player in g.vs['name']]
    
    # Create a list of sizes matching the order of g.vs['name']
    sizes = [total_passes.get(player, 1) for player in g.vs['name']]  # default size 1 if missing

    # Optionally, scale sizes so they look good on plot, e.g.:
    min_size, max_size = 20, 80
    max_node_size=max(sizes)
    min_passes, max_passes = min(sizes), max(sizes)
    scaled_sizes = [
        min_size + (s - min_passes) / (max_passes - min_passes) * (max_size - min_size)
        if max_passes != min_passes else min_size
        for s in sizes
        ]

    g.vs["size"] = scaled_sizes
    radius_pts = (np.array(g.vs["size"]) / 2.0) + 1.2
    
    edge_pairs = np.array(g.get_edgelist(), dtype=int)  
    sources = edge_pairs[:, 0]
    targets = edge_pairs[:, 1]

    edge_curvature = 0.18
    sign = np.where(sources < targets, 1.0, -1.0)        # split A→B vs B→A
    curv = (edge_curvature * sign).tolist()
    ## lo ploteamos 
    
    fig,ax=pitch.draw()
    
    fig.patch.set_facecolor('white')
    pitch.draw(ax=ax) 
    edge_rgba = mcolors.to_rgba("#C4B5FD", 0.6)
    #ig.plot(g, layout=layout, target=ax)
    G = nx.DiGraph()
   
    for _, row in players_passes_df.iterrows():
        G.add_edge(row['player'], row['pass_recipient'], weight=row['passes'])
        
    pos = {row['player']:(row['x'], row['y']) for _, row in player_location_df.iterrows()}
    
    
    scaled_sizes_nx = [scaled_sizes[g.vs.find(name=node).index] for node in G.nodes()]
    min_size, max_size = 40, 400
    sizes_nx = [min_size + (s - min(scaled_sizes_nx)) / (max(scaled_sizes_nx) - min(scaled_sizes_nx)) * (max_size - min_size)
             for s in scaled_sizes_nx]
    
    
    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_fill,
        node_size=sizes_nx,
        ax=ax
        )
    nx.draw_networkx_labels(
        G, pos,
        labels={player: player for player in pos.keys()},
        font_size=8,   # smaller font
        font_color='black',
        ax=ax
        )
    for u, v, data in G.edges(data=True):
        x_start, y_start = pos[u]
        x_end, y_end = pos[v]
    
        # Check if the reverse edge exists
        if G.has_edge(v, u):
            rad = 0.2  # curve radius
        else:
            rad = 0.0  # straight line
    
        arrow = FancyArrowPatch(
            (x_start, y_start),
            (x_end, y_end),
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle='-|>',
            color=edge_color,
            lw=1 + 2*(data['weight']/max_edge_weight),
            alpha=0.6,
            mutation_scale=10 + 5*(data['weight']/max_edge_weight)
            )
        ax.add_patch(arrow)
    
    norm_teamname=team_analizing.replace(" ","_")


    import matplotlib.patches as mpatches
    color="#2F6DB3"
    circle = mpatches.Ellipse((5, -10), width=4, height=6 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    circle = mpatches.Ellipse((11, -10), width=5.5, height=8 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    
    circle = mpatches.Ellipse((19, -10), width=7.5, height=11 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    
    arrow = FancyArrowPatch(posA=(2,-18), posB=(25, -18), 
                        arrowstyle='->', color='black', 
                        mutation_scale=15, lw=2,clip_on=False)
    ax.add_patch(arrow)
    ax.text(11,-20,f"{MIN_PASS} passes        {max_node_size} passes",fontsize=8,va="top",ha="center",color="black")
    line_col="#C4B5FD99"
    ax.plot([40, 45], [-10, -6], color=line_col, linewidth=1, clip_on=False)
    ax.plot([45, 50], [-10, -6], color=line_col, linewidth=2, clip_on=False)
    ax.plot([50, 55], [-10, -6], color=line_col, linewidth=4, clip_on=False)
    if team_analizing==home_team:
        arrow = FancyArrowPatch(
            (0.7, 0.015),    
            (0.9, 0.015),   
            transform=ax.transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=15,  
            linewidth=1
            )
        ax.add_patch(arrow)
    elif team_analizing==away_team:

        arrow = FancyArrowPatch(
            (0.9, 0.015),    
            (0.7, 0.015),   
            transform=ax.transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=15,  
            linewidth=1
            )
        ax.add_patch(arrow)
    arrow = FancyArrowPatch(posA=(40,-18), posB=(60, -18), 
                        arrowstyle='->', color='black', 
                        mutation_scale=15, lw=2,clip_on=False)
    ax.add_patch(arrow)
    ax.text(50,-20,f"{MIN_PASS} passes           {max_edge_weight} passes",fontsize=8,va="top",ha="center",color="black")
    
    
    ax.text(100, 
            -5, 
            f"Minimum Passes: {MIN_PASS}",
            fontsize=10, 
            va='top',
            ha='right',
            color="white"
            )
    output_path=f"{norm_teamname}_passmap.png"
    plt.savefig(f"{norm_teamname}_passmap.png",dpi=300, bbox_inches='tight')
    plt.close(fig)

    return output_path    


#goals,home_goals,away_goals=get_goals("/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")
# Heatmap_one_team("away", "/Users/julieta/Desktop/data_madridcff/f40/f40-squad-102.xml", "/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")
# cercania_porteria_lateral("/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml","/Users/julieta/Desktop/data_madridcff/f70/f70-903-2025-2572345-expectedgoals.xml")
# passnetwork_oneteam("/Users/julieta/Desktop/data_madridcff/f27/pass_matrix_903_2025_g2572345_t13320.xml", "/Users/julieta/Desktop/data_madridcff/f40/f40-squad-102.xml",1)

def get_tabla1(filepath_f70, filepath_f24,filepath_f73):
    ##goles
    goals,home_goals,away_goals=get_goals(filepath_f24)
    home_goals_n=int(home_goals)
    away_goals_n=int(away_goals)
    #xG
    #print(type(home_goals))
    _,total_xg_home,total_xg_away=cercania_porteria_lateral(filepath_f24,filepath_f70,filepath_f73)
    ##pases (para tener home id y away id)
    df_events,team_names=parse_f24(filepath_f24)
    home_name=team_names["home_team_name"].iloc[0]
    away_name=team_names["away_team_name"].iloc[0]
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    #ocasiones
    events = parse_f70_events(filepath_f70)
    shot_events = events[events['type_id'].isin(['13', '14', '15', '16'])]
    shot_events["type_id"] = shot_events["type_id"].astype(int)
    home_shots=shot_events[shot_events["team_id"]==home_id]
    home_goals=home_shots[home_shots["type_id"]==16]
    away_shots=shot_events[shot_events["team_id"]==away_id]
    away_goals=away_shots[away_shots["type_id"]==16]

    total_home=len(home_shots)
    total_away=len(away_shots)
    #print(type(total_home))
    success_home=((home_goals_n)/total_home)*100
    success_away=((away_goals_n)/total_away)*100
    ocasiones_home=f"{total_home} <font size=10>({success_home:.1f}% de acierto)</font>"
    ocasiones_away=f"{total_away} <font size=10>({success_away:.1f}% de acierto)</font>"
    
    #### pases y tercios
    
    df_passes=df_events[(df_events["type_id"]==1)]
    home_passes=df_passes[df_passes["team_id"]==int(home_id)]
    away_passes=df_passes[df_passes["team_id"]==int(away_id)]
    completed_home=len(home_passes[home_passes["outcome"] == 1])
    completed_away=len(away_passes[away_passes["outcome"]==1])         
    success_home = (len(home_passes[home_passes["outcome"] == 1]) / len(home_passes))*100 
    success_away = (len(away_passes[away_passes["outcome"] == 1]) / len(away_passes))*100 
    home_passes_txt=f"{completed_home} <font size=10>({success_home:.2f}% de acierto)</font>"
    away_passes_txt=f"{completed_away} <font size=10>({success_away:.2f}% de acierto)</font>"
    z1_home=home_passes[home_passes["x"]<33.34]
    z1_home_ratio=(len(z1_home[z1_home["outcome"] == 1])/completed_home) *100
    z1_home_success=(len(z1_home[z1_home["outcome"] == 1]) / len(z1_home))*100 
    z1_home_text=f"{len(z1_home[z1_home['outcome'] == 1])} <font size=10>({z1_home_ratio:.0f}% del total - {z1_home_success:.0f}% de acierto)</font>"

    z2_home=home_passes[(home_passes["x"]>33.34) & (home_passes["x"]<66.67)]
    z2_home_ratio=(len(z2_home[z2_home["outcome"] == 1])/completed_home) *100
    z2_home_success=(len(z2_home[z2_home["outcome"] == 1]) / len(z2_home))*100 
    z2_home_text=f"{len(z2_home[z2_home['outcome'] == 1])} <font size=10>({z2_home_ratio:.0f}% del total - {z2_home_success:.0f}% de acierto)</font>"

    z3_home=home_passes[(home_passes["x"]>66.67)]
    z3_home_ratio=(len(z3_home[z3_home["outcome"] == 1])/completed_home) *100
    z3_home_success=(len(z3_home[z3_home["outcome"] == 1]) / len(z3_home))*100 
    z3_home_text=f"{len(z3_home[z3_home['outcome'] == 1])} <font size=10>({z3_home_ratio:.0f}% del total - {z3_home_success:.0f}% de acierto)</font>"

    z1_away=away_passes[away_passes["x"]<33.34]
    z1_away_ratio=(len(z1_away[z1_away["outcome"] == 1])/completed_away) *100
    z1_away_success=(len(z1_away[z1_away["outcome"] == 1]) / len(z1_away))*100 
    z1_away_text=f"{len(z1_away[z1_away['outcome'] == 1])} <font size=10>({z1_away_ratio:.0f}% del total - {z1_away_success:.0f}% de acierto)</font>"

    z2_away=away_passes[(away_passes["x"]>33.34) & (away_passes["x"]<66.67)]
    z2_away_ratio=(len(z2_away[z2_away["outcome"] == 1])/completed_away) *100
    z2_away_success=(len(z2_away[z2_away["outcome"] == 1]) / len(z2_away))*100 
    z2_away_text=f"{len(z2_away[z2_away['outcome'] == 1])} <font size=10>({z2_away_ratio:.0f}% del total - {z2_away_success:.0f}% de acierto)</font>"

    z3_away=away_passes[(away_passes["x"]>66.67)]
    z3_away_ratio=(len(z3_away[z3_away["outcome"] == 1])/completed_away) *100
    z3_away_success=(len(z3_away[z3_away["outcome"] == 1]) / len(z3_away))*100 
    z3_away_text=f"{len(z3_away[z3_away['outcome'] == 1])} <font size=10>({z3_away_ratio:.0f}% del total - {z3_away_success:.0f}% de acierto)</font>"
    
    list_defensive=[4,7,8,45]
    df_defensive=df_events[df_events["type_id"].isin(list_defensive)].copy()

    home_defensive = df_defensive[df_defensive["team_id"]==int(home_id)]
    away_defensive = df_defensive[df_defensive["team_id"]==int(away_id)]
    defensive_home = len(home_defensive)
    defensive_away = len(away_defensive)         

    z1_home = home_defensive[home_defensive["x"]<33.34]
    z1_home_ratio = (len(z1_home)/defensive_home) *100

    z1_home_def = f"{len(z1_home)} <font size=10>({z1_home_ratio:.0f}% del total)</font>"

    z2_home = home_defensive[(home_defensive["x"]>33.34) & (home_defensive["x"]<66.67)]
    z2_home_ratio = (len(z2_home)/defensive_home) *100

    z2_home_def = f"{len(z2_home)} <font size=10>({z2_home_ratio:.0f}% del total)</font>"
    
    z3_home = home_defensive[(home_defensive["x"]>66.67)]
    z3_home_ratio = (len(z3_home)/defensive_home) *100

    z3_home_def = f"{len(z3_home)} <font size=10>({z3_home_ratio:.0f}% del total)</font>"

    z1_away = away_defensive[away_defensive["x"]<33.34]
    z1_away_ratio = (len(z1_away)/defensive_away) *100
    z1_away_success = (len(z1_away) / len(z1_away))*100 
    z1_away_def = f"{len(z1_away)} <font size=10>({z1_away_ratio:.0f}% del total)</font>"

    z2_away = away_defensive[(away_defensive["x"]>33.34) & (away_defensive["x"]<66.67)]
    z2_away_ratio = (len(z2_away)/defensive_away) *100
    z2_away_def = f"{len(z2_away)} <font size=10>({z2_away_ratio:.0f}% del total)</font>"

    z3_away = away_defensive[(away_defensive["x"]>66.67)]
    z3_away_ratio = (len(z3_away)/defensive_away) *100
    z3_away_def = f"{len(z3_away)} <font size=10>({z3_away_ratio:.0f}% del total)</font>"
    
    
    df_tabla1=pd.DataFrame({
        "<b>Tipo de Evento</b>": ["Goles", "Goles esperados", "Ocasiones","Pases Completados","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>", "Acciones Defensivas","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>"],
        f"<b>{home_name}</b>": [home_goals_n, f"{total_xg_home:.2f}", ocasiones_home,home_passes_txt,z1_home_text,z2_home_text,z3_home_text,defensive_home,z1_home_def,z2_home_def,z3_home_def],
        f"<b>{away_name}</b>": [away_goals_n, f"{total_xg_away:.2f}", ocasiones_away,away_passes_txt,z1_away_text,z2_away_text,z3_away_text,defensive_away,z1_away_def,z2_away_def,z3_away_def]
        })
    
    
    
    
    return df_tabla1

#df=get_tabla1("/Users/julieta/Desktop/data_madridcff/f70/f70-903-2025-2572345-expectedgoals.xml", "/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")


def get_tabla2(filepath_f24):
    
    ##pases (para tener home id y away id)
    df_events,team_names=parse_f24(filepath_f24)
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    home_name=team_names["home_team_name"].iloc[0]
    away_name=team_names["away_team_name"].iloc[0]

    df_fouls=df_events[(df_events["type_id"]==4) & (df_events["outcome"]==0)].copy()

    home_fouls = df_fouls[df_fouls["team_id"]==int(home_id)]
    away_fouls = df_fouls[df_fouls["team_id"]==int(away_id)]
    fouls_home = len(home_fouls)
    fouls_away = len(away_fouls)         

    z1_home_fouls = home_fouls[home_fouls["x"]<33.34]
    z1_home_ratio_f = (len(z1_home_fouls)/fouls_home) *100
    z1_home_fouls = f"{len(z1_home_fouls)} <font size=10>({z1_home_ratio_f:.0f}% del total)</font>"

    z2_home_fouls = home_fouls[(home_fouls["x"]>33.34) & (home_fouls["x"]<66.67)]
    z2_home_ratio_f = (len(z2_home_fouls)/fouls_home) *100
    z2_home_fouls = f"{len(z2_home_fouls)} <font size=10>({z2_home_ratio_f:.0f}% del total)</font>"

    z3_home_fouls = home_fouls[(home_fouls["x"]>66.67)]
    z3_home_ratio_f = (len(z3_home_fouls)/fouls_home) *100
    z3_home_fouls = f"{len(z3_home_fouls)} <font size=10>({z3_home_ratio_f:.0f}% del total)</font>"

    z1_away_fouls = away_fouls[away_fouls["x"] < 33.34]
    z1_away_ratio_f = (len(z1_away_fouls) / fouls_away) * 100
    z1_away_fouls = f"{len(z1_away_fouls)} <font size=10>({z1_away_ratio_f:.0f}% del total)</font>"

    z2_away_fouls = away_fouls[(away_fouls["x"] > 33.34) & (away_fouls["x"] < 66.67)]
    z2_away_ratio_f = (len(z2_away_fouls) / fouls_away) * 100
    z2_away_fouls = f"{len(z2_away_fouls)} <font size=10>({z2_away_ratio_f:.0f}% del total)</font>"

    z3_away_fouls = away_fouls[(away_fouls["x"] > 66.67)]
    z3_away_ratio_f = (len(z3_away_fouls) / fouls_away) * 100
    z3_away_fouls = f"{len(z3_away_fouls)} <font size=10>({z3_away_ratio_f:.0f}% del total)</font>"

    df_dribbles_stopped=df_events[(df_events["type_id"]==3) & (df_events["outcome"]==0)].copy()
    df_dribbles=df_events[(df_events["type_id"]==3)].copy()

    home_total=len(df_dribbles[df_dribbles["team_id"]==int(away_id)])
    away_total=len(df_dribbles[df_dribbles["team_id"]==int(home_id)])

    home_stopped = df_dribbles_stopped[df_dribbles_stopped["team_id"]==int(away_id)]
    away_stopped = df_dribbles_stopped[df_dribbles_stopped["team_id"]==int(home_id)]
    stoped_home = len(home_stopped)
    stoped_away = len(away_stopped)         
    stopped_home=f"{stoped_home} <font size=10>({(stoped_home/home_total)*100:.0f}% impedidos)</font>"
    stopped_away=f"{stoped_away} <font size=10>({(stoped_away/away_total)*100:.0f}% impedidos)</font>"

    z1_home_stopped = home_stopped[home_stopped["x"] >66.67]
    z1_home_ratio_s = (len(z1_home_stopped) / stoped_home) * 100
    z1_home_stopped = f"{len(z1_home_stopped)} <font size=10>({z1_home_ratio_s:.0f}% del total)</font>"

    # Home zones
    z2_home_stopped = home_stopped[(home_stopped["x"] > 33.34) & (home_stopped["x"] < 66.67)]
    z2_home_ratio_s = (len(z2_home_stopped) / stoped_home) * 100
    z2_home_stopped = f"{len(z2_home_stopped)} <font size=10>({z2_home_ratio_s:.0f}% del total)</font>"

    z3_home_stopped = home_stopped[home_stopped["x"] <33.34]
    z3_home_ratio_s = (len(z3_home_stopped) / stoped_home) * 100
    z3_home_stopped = f"{len(z3_home_stopped)} <font size=10>({z3_home_ratio_s:.0f}% del total)</font>"

    # Away zones
    z1_away_stopped = away_stopped[away_stopped["x"] >66.67]
    z1_away_ratio_s = (len(z1_away_stopped) / stoped_away) * 100
    z1_away_stopped = f"{len(z1_away_stopped)} <font size=10>({z1_away_ratio_s:.0f}% del total)</font>"

    z2_away_stopped = away_stopped[(away_stopped["x"] > 33.34) & (away_stopped["x"] < 66.67)]
    z2_away_ratio_s = (len(z2_away_stopped) / stoped_away) * 100
    z2_away_stopped = f"{len(z2_away_stopped)} <font size=10>({z2_away_ratio_s:.0f}% del total)</font>"

    z3_away_stopped = away_stopped[away_stopped["x"]< 33.34]
    z3_away_ratio_s = (len(z3_away_stopped) / stoped_away) * 100
    z3_away_stopped = f"{len(z3_away_stopped)} <font size=10>({z3_away_ratio_s:.0f}% del total)</font>"

    
    df_tabla2=pd.DataFrame({
        "<b>Tipo de Evento</b>": ["PPDA:Pases del Rival/Acciones Defensivas ", "Faltas","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>","Regates Impedidos","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>"],
        f"<b>{home_name}</b>": [home_name, fouls_home, z1_home_fouls,z2_home_fouls,z3_home_fouls,stopped_home,z1_home_stopped,z2_home_stopped,z3_home_stopped],
        f"<b>{away_name}</b>": [away_name, fouls_away, z1_away_fouls,z2_away_fouls,z3_away_fouls,stopped_away,z1_away_stopped,z2_away_stopped,z3_away_stopped]
        })
    
    
    
    
    return df_tabla2

#df2= get_tabla2("/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")


def get_tabla3(filepath_f24):
    
    ##pases (para tener home id y away id)
    df_events,team_names=parse_f24(filepath_f24)
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    home_name=team_names["home_team_name"].iloc[0]
    away_name=team_names["away_team_name"].iloc[0]
    
    df_passes_cortados=df_events[(df_events["type_id"]==8)].copy()


    home_total=len(df_passes_cortados[df_passes_cortados["team_id"]==int(home_id)])
    away_total=len(df_passes_cortados[df_passes_cortados["team_id"]==int(away_id)])

    home_stopped = df_passes_cortados[df_passes_cortados["team_id"]==int(home_id)]
    away_stopped = df_passes_cortados[df_passes_cortados["team_id"]==int(away_id)]

    z1_home_stopped = len(home_stopped[home_stopped["x"] <33.34])
    z2_home_stopped = len(home_stopped[(home_stopped["x"] > 33.34) & (home_stopped["x"] < 66.67)])
    z3_home_stopped = len(home_stopped[home_stopped["x"] > 66.67])

    z1_away_stopped = len(away_stopped[away_stopped["x"] < 33.34])
    z2_away_stopped = len(away_stopped[(away_stopped["x"] > 33.34) & (away_stopped["x"] < 66.67)])
    z3_away_stopped = len(away_stopped[away_stopped["x"] > 66.67])

    df_entradas=df_events[(df_events["type_id"]==7)].copy()


    entradas_home=len(df_entradas[df_entradas["team_id"]==int(home_id)])
    entradas_away=len(df_entradas[df_entradas["team_id"]==int(away_id)])

    home_entradas = df_entradas[df_entradas["team_id"]==int(home_id)]
    away_entradas = df_entradas[df_entradas["team_id"]==int(away_id)]

    z1_home_entradas = len(home_entradas[home_entradas["x"] <33.34])
    z2_home_entradas = len(home_entradas[(home_entradas["x"] > 33.34) & (home_entradas["x"] < 66.67)])
    z3_home_entradas = len(home_entradas[home_entradas["x"] > 66.67])

    z1_away_entradas = len(away_entradas[away_entradas["x"] < 33.34])
    z2_away_entradas = len(away_entradas[(away_entradas["x"] > 33.34) & (away_entradas["x"] < 66.67)])
    z3_away_entradas = len(away_entradas[away_entradas["x"] > 66.67])

    
    df_tabla3=pd.DataFrame({
        "<b>Tipo de Evento</b>": ["Pases Cortados","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>","Entradas","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>"],
        f"<b>{home_name}</b>": [ home_total, z1_home_stopped,z2_home_stopped,z3_home_stopped,entradas_home,z1_home_entradas,z2_home_entradas,z3_home_entradas],
        f"<b>{away_name}</b>": [ away_total, z1_away_stopped,z2_away_stopped,z3_away_stopped,entradas_away,z1_away_entradas,z2_away_entradas,z3_away_entradas]
        })
    
    
    
    
    return df_tabla3

#df3= get_tabla3("/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")

def get_tabla4(filepath_f24):
    
    ##pases (para tener home id y away id)
    df_events,team_names=parse_f24(filepath_f24)
    home_id=team_names["home_team_id"].iloc[0]
    away_id=team_names["away_team_id"].iloc[0]
    home_name=team_names["home_team_name"].iloc[0]
    away_name=team_names["away_team_name"].iloc[0]
    #SON DESPEJES
    df_passes_cortados=df_events[(df_events["type_id"]==12)].copy()


    home_total=len(df_passes_cortados[df_passes_cortados["team_id"]==int(home_id)])
    away_total=len(df_passes_cortados[df_passes_cortados["team_id"]==int(away_id)])

    home_stopped = df_passes_cortados[df_passes_cortados["team_id"]==int(home_id)]
    away_stopped = df_passes_cortados[df_passes_cortados["team_id"]==int(away_id)]

    z1_home_stopped = len(home_stopped[home_stopped["x"] <33.34])
    z2_home_stopped = len(home_stopped[(home_stopped["x"] > 33.34) & (home_stopped["x"] < 66.67)])
    z3_home_stopped = len(home_stopped[home_stopped["x"] > 66.67])

    z1_away_stopped = len(away_stopped[away_stopped["x"] < 33.34])
    z2_away_stopped = len(away_stopped[(away_stopped["x"] > 33.34) & (away_stopped["x"] < 66.67)])
    z3_away_stopped = len(away_stopped[away_stopped["x"] > 66.67])
    #blocked passes
    df_entradas=df_events[(df_events["type_id"]==74)].copy()


    entradas_home=len(df_entradas[df_entradas["team_id"]==int(home_id)])
    entradas_away=len(df_entradas[df_entradas["team_id"]==int(away_id)])

    home_entradas = df_entradas[df_entradas["team_id"]==int(home_id)]
    away_entradas = df_entradas[df_entradas["team_id"]==int(away_id)]

    z1_home_entradas = len(home_entradas[home_entradas["x"] <33.34])
    z2_home_entradas = len(home_entradas[(home_entradas["x"] > 33.34) & (home_entradas["x"] < 66.67)])
    z3_home_entradas = len(home_entradas[home_entradas["x"] > 66.67])

    z1_away_entradas = len(away_entradas[away_entradas["x"] < 33.34])
    z2_away_entradas = len(away_entradas[(away_entradas["x"] > 33.34) & (away_entradas["x"] < 66.67)])
    z3_away_entradas = len(away_entradas[away_entradas["x"] > 66.67])

    
    df_tabla4=pd.DataFrame({
        "<b>Tipo de Evento</b>": ["Despejes","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>","Bloqueos de balón","<font size=13>Zona 1</font>", "<font size=13>Zona 2</font>", "<font size=13>Zona 3</font>"],
        f"<b>{home_name}</b>": [ home_total, z1_home_stopped,z2_home_stopped,z3_home_stopped,entradas_home,z1_home_entradas,z2_home_entradas,z3_home_entradas],
        f"<b>{away_name}</b>": [ away_total, z1_away_stopped,z2_away_stopped,z3_away_stopped,entradas_away,z1_away_entradas,z2_away_entradas,z3_away_entradas]
        })
    
    
    
    
    return df_tabla4

#df4= get_tabla4("/Users/julieta/Desktop/data_madridcff/f24/f24-903-2025-2572345-eventdetails.xml")

def passnetwork_oneteam_thirds(filepath_f27, filepath_f40,type_third,MIN_PASS=1):
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
       
       #df_pases["x"], df_pases["y"] = df_pases["y"], df_pases["x"]
       pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
       )
    elif type_third=="second":
        
        df_pases = df_pases[(df_pases["x"] >= 33.33) & (df_pases["x"] <= 66.66)].copy()
        pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
           )
        #df_pases["x"], df_pases["y"] = df_pases["y"], df_pases["x"]
    elif type_third=="third":
        df_pases = df_pases[(df_pases["x"] >= 66.67)].copy()
        pitch = VerticalPitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,axis=True, label=True, tick=True,
           )
       # df_pases["x"], df_pases["y"] = df_pases["y"], df_pases["x"]
    elif type_third=="all":
        df_pases = df_pases.copy()
        pitch = Pitch(
           pitch_type="opta", pitch_color="white", line_color="black", linewidth=1,
           )
    
    df_jugadores, equipos =parse_f40(filepath_f40,team_analizing)

    replace_dict = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")

    df_pases["player"] = df_pases["player"].str.translate(replace_dict)
    df_pases["receiver"] = df_pases["receiver"].str.translate(replace_dict)
    
    df_pases = pd.merge(df_pases, df_jugadores, left_on="player", right_on="player", how="left")
    df_pases = pd.merge(df_pases, df_jugadores, left_on="receiver", right_on="player", how="left")

    df_pases = df_pases.drop(["position_y", "position", "team_y", "player_y"], axis=1)

    df_pases = df_pases.rename(columns={"position_x": "position", "player_x": "player", "team_x": "team", "jersey_num_x": "jersey_player", "jersey_num_y": "jersey_receiver"})
    mask = df_pases["team"] == (away_team)
    df_pases.loc[mask, "x"] = 100 - df_pases.loc[mask, "x"]
    df_pases.loc[mask, "y"] = 100 - df_pases.loc[mask, "y"]
    
    subs = df_pases[df_pases["sub"] == True]
    subs_jerseynum = subs["jersey_player"].drop_duplicates()
    df_pases = df_pases[~df_pases["jersey_player"].isin(subs_jerseynum) & ~df_pases["jersey_receiver"].isin(subs_jerseynum)]
    
    #hasta aqui tengo un df que es 'player', 'position', 'x', 'y', 'receiver', 'pases', 'sub','entry_minute', 'team', 'jersey_player', 'jersey_receiver']
    #con solo los titulares

    pass_cols = ['jersey_player', 'jersey_receiver']
    #passes formation es basicamente todos los pases que se dan entre titulares
    passes_formation = df_pases.loc[(df_pases.team == team_analizing) &
                                      df_pases.jersey_receiver.notnull(), pass_cols].copy()
    #passes subs es pases dirigidos A subs, que luego se eliminan
    passes_subs = subs.loc[(subs.team == team_analizing) &
                                      subs.jersey_receiver.notnull(), pass_cols].copy()

    location_cols = ["jersey_player", "x", "y"]

    #location formation es donde esta cada jugador, x,y del campo
    location_formation = df_pases.loc[(df_pases.team == team_analizing), location_cols].copy()
    #average locs and count es el average de las location Y cuenta el número de pases hechos por cada jugador
    average_locs_and_count = (location_formation.groupby('jersey_player')
                              .agg({'x': ['mean'], 'y': ['mean', 'count']}))
    
    
    average_locs_and_count.columns = ['x', 'y', 'count']

    location_formation = location_formation.drop_duplicates()
    #location formation de donde esta cada jugador en el campo
    location_formation["jersey_player"] = location_formation["jersey_player"].astype(int)
    passes_formation['pos_max'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .max(axis='columns'))
    passes_formation['pos_min'] = (passes_formation[['jersey_player',
                                                    'jersey_receiver']]
                                   .min(axis='columns'))
    passes_formation["pos_min"]=passes_formation["pos_min"].astype(int)
    passes_formation["pos_max"]=passes_formation["pos_max"].astype(int)
    #passes_formation.to_excel("passes_formation.xlsx",index=False)
    passes_between = passes_formation.groupby(['pos_min',"pos_max"]).size().reset_index(name='pass_count')

    # add on the location of each player so we have the start and end positions of the lines
    passes_between = passes_between.merge(location_formation, left_on='pos_min', right_on="jersey_player")
    passes_between = passes_between.merge(location_formation, left_on='pos_max', right_on="jersey_player",
                                          suffixes=['', '_end'])
    
    player_location_df = (
        df_pases[["player", "x", "y", "pases"]]
        .groupby("player")
        .agg({
            "x": "mean",
            "y": "mean",
            "pases": "sum"
            })
        .reset_index()
        )
    
    
    players_passes_df=df_pases[["player","receiver","pases"]]
    
    players_passes_df = players_passes_df.merge(player_location_df[['player', 'x', 'y']], 
                                        left_on='player', right_on='player').\
                                            rename(columns={'x': 'passer_x', 
                                                            'y': 'passer_y'}
                                                   )

    players_passes_df = players_passes_df.merge(player_location_df[['player', 'x', 'y']], 
                                            left_on='receiver', right_on='player').\
                                                rename(columns={'x': 'recipient_x', 
                                                                'y': 'recipient_y', 
                                                                'player_x': 'player'}
                                                    ) 
    players_passes_df.drop("player_y",axis=1,inplace=True)
    player_location_df=player_location_df.rename(columns={"pases":"total"})
    players_passes_df=players_passes_df.rename(columns={"pases":"passes","receiver":"pass_recipient"})
    player_names=df_pases[["player","jersey_player"]].drop_duplicates().copy()
    player_names_dict = dict(zip(player_names["player"], player_names["player"]))

    players = pd.unique(players_passes_df[['player', 'pass_recipient']].values.ravel())


    players_loc=player_location_df[["player","x","y"]]
    players_passes_df=players_passes_df[players_passes_df["passes"]>MIN_PASS]
    
    #aqui creo el grafo
    g = ig.Graph(directed=True)
    
    #y aqui añado vertices, los nodos, cada jugador
    g.add_vertices(list(players))

    #aqui los links entre jugadores
    #defino
    edges=list(zip(players_passes_df["player"],players_passes_df["pass_recipient"]))
    
    #añado
    g.add_edges(edges)
    
    #aqui añado los pesos
    g.es["weight"]=players_passes_df["passes"].tolist()
    
    #añado las coordenadas de cada jugador
    coords={}
    for _,row in players_loc.iterrows():
        player=row["player"]
        coords.setdefault(player,[]).append((row["x"],row["y"]))
       
    layout=[coords[player] for player in players]
    
    layout = [coords[player][0] for player in g.vs['name']]

    
    node_fill = "#2F6DB3"
    node_edge = "#2F6DB3"

    edge_color = "#C4B5FD99"
    
    g.vs["color"] = node_fill
    g.vs["frame_color"] = node_edge
    g.vs["frame_width"] = 1.0
    g.es["color"] = edge_color
    
    g.vs["label_dist"]=0.5
    g.vs['label_angle'] = -math.pi/2  
    g.vs['label_size'] = 6    # bigger font size
    g.vs['label_color'] = 'black'
    g.es["arrow_size"]  = 1.4   # 0.8–1.4 usually looks good
    g.es["arrow_width"] = 1.0  
    #fig, ax = plt.subplots()
    
    #asignamos labels a cada vertice, con la label siendo el nombre
    g.vs['label'] = g.vs['name']
    g.es['weight'] = players_passes_df['passes'].tolist()
    max_edge_weight = max(g.es["weight"])
    weights = np.array(g.es['weight'])
    
    #normalizo prq sino no se nota tanto
    min_width, max_width = 1, 7
    scaled_widths = min_width + (weights - weights.min()) / (weights.max() - weights.min()) * (max_width - min_width)
    #controls width of lines
    g.es['width'] = scaled_widths.tolist()
    
    total_passes = players_passes_df.groupby('player')['passes'].sum()
    norm = mcolors.Normalize(vmin=min(total_passes), vmax=max(total_passes))
    cmap = cm.get_cmap('YlOrRd')  # or 'coolwarm', 'plasma', etc.
    

    # Map each player to a color
    #vertex_colors = [mcolors.to_hex(cmap(norm(total_passes.get(player, 0))))
    #                 for player in g.vs['name']]
    
    # Create a list of sizes matching the order of g.vs['name']
    sizes = [total_passes.get(player, 1) for player in g.vs['name']]  # default size 1 if missing

    # Optionally, scale sizes so they look good on plot, e.g.:
    min_size, max_size = 20, 80
    max_node_size=max(sizes)
    min_passes, max_passes = min(sizes), max(sizes)
    scaled_sizes = [
        min_size + (s - min_passes) / (max_passes - min_passes) * (max_size - min_size)
        if max_passes != min_passes else min_size
        for s in sizes
        ]

    g.vs["size"] = scaled_sizes
    radius_pts = (np.array(g.vs["size"]) / 2.0) + 1.2
    
    edge_pairs = np.array(g.get_edgelist(), dtype=int)  
    sources = edge_pairs[:, 0]
    targets = edge_pairs[:, 1]

    edge_curvature = 0.18
    sign = np.where(sources < targets, 1.0, -1.0)        # split A→B vs B→A
    curv = (edge_curvature * sign).tolist()
    ## lo ploteamos 
    
    fig,ax=pitch.draw()
    
    fig.patch.set_facecolor('white')
    pitch.draw(ax=ax) 
    edge_rgba = mcolors.to_rgba("#C4B5FD", 0.6)
    #ig.plot(g, layout=layout, target=ax)
    G = nx.DiGraph()
   
    for _, row in players_passes_df.iterrows():
        G.add_edge(row['player'], row['pass_recipient'], weight=row['passes'])
        
    pos = {row['player']:(row['x'], row['y']) for _, row in player_location_df.iterrows()}
    
    
    scaled_sizes_nx = [scaled_sizes[g.vs.find(name=node).index] for node in G.nodes()]
    min_size, max_size = 40, 400
    sizes_nx = [min_size + (s - min(scaled_sizes_nx)) / (max(scaled_sizes_nx) - min(scaled_sizes_nx)) * (max_size - min_size)
             for s in scaled_sizes_nx]
    
    
    nx.draw_networkx_nodes(
        G, pos,
        node_color=node_fill,
        node_size=sizes_nx,
        ax=ax
        )
    nx.draw_networkx_labels(
        G, pos,
        labels={player: player for player in pos.keys()},
        font_size=8,   # smaller font
        font_color='black',
        ax=ax
        )
    for u, v, data in G.edges(data=True):
        x_start, y_start = pos[u]
        x_end, y_end = pos[v]
    
        # Check if the reverse edge exists
        if G.has_edge(v, u):
            rad = 0.2  # curve radius
        else:
            rad = 0.0  # straight line
    
        arrow = FancyArrowPatch(
            (x_start, y_start),
            (x_end, y_end),
            connectionstyle=f"arc3,rad={rad}",
            arrowstyle='-|>',
            color=edge_color,
            lw=1 + 2*(data['weight']/max_edge_weight),
            alpha=0.6,
            mutation_scale=10 + 5*(data['weight']/max_edge_weight)
            )
        ax.add_patch(arrow)
    
    norm_teamname=team_analizing.replace(" ","_")


    import matplotlib.patches as mpatches
    color="#2F6DB3"
    circle = mpatches.Ellipse((5, -10), width=4, height=6 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    circle = mpatches.Ellipse((11, -10), width=5.5, height=8 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    
    circle = mpatches.Ellipse((19, -10), width=7.5, height=11 * ax.get_data_ratio(), 
                          color=color, clip_on=False)
    ax.add_patch(circle)
    
    arrow = FancyArrowPatch(posA=(2,-18), posB=(25, -18), 
                        arrowstyle='->', color='black', 
                        mutation_scale=15, lw=2,clip_on=False)
    ax.add_patch(arrow)
    ax.text(11,-20,f"{MIN_PASS} passes        {max_node_size} passes",fontsize=8,va="top",ha="center",color="black")
    line_col="#C4B5FD99"
    ax.plot([40, 45], [-10, -6], color=line_col, linewidth=1, clip_on=False)
    ax.plot([45, 50], [-10, -6], color=line_col, linewidth=2, clip_on=False)
    ax.plot([50, 55], [-10, -6], color=line_col, linewidth=4, clip_on=False)
    if team_analizing==home_team:
        arrow = FancyArrowPatch(
            (0.7, 0.015),    
            (0.9, 0.015),   
            transform=ax.transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=15,  
            linewidth=1
            )
        ax.add_patch(arrow)
    elif team_analizing==away_team:

        arrow = FancyArrowPatch(
            (0.9, 0.015),    
            (0.7, 0.015),   
            transform=ax.transAxes,   
            arrowstyle='simple', 
            color='black',
            mutation_scale=15,  
            linewidth=1
            )
        ax.add_patch(arrow)
    arrow = FancyArrowPatch(posA=(40,-18), posB=(60, -18), 
                        arrowstyle='->', color='black', 
                        mutation_scale=15, lw=2,clip_on=False)
    ax.add_patch(arrow)
    ax.text(50,-20,f"{MIN_PASS} passes           {max_edge_weight} passes",fontsize=8,va="top",ha="center",color="black")
    
    
    ax.text(100, 
            -5, 
            f"Minimum Passes: {MIN_PASS}",
            fontsize=10, 
            va='top',
            ha='right',
            color="white"
            )
    
    
    #fig,ax=pitch.draw()
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
    
    fig.patch.set_facecolor('white')
    #pitch.draw(ax=ax) 
    edge_rgba = mcolors.to_rgba("#C4B5FD", 0.6)
    ig.plot(g, layout=layout, target=ax)
    
    norm_teamname=team_analizing.replace(" ","_")


    output_path = f"passnetwork_{team_analizing}_{type_third}.png"
    fig.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.show()
    return fig, output_path     
    
#cercania_porteria_lateral("/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f24/f24-903-2025-2572323-eventdetails.xml","/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f70/f70-903-2025-2572323-expectedgoals.xml","/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f73/f73-903-2025-2572323-possessions.xml")
#passnetwork_oneteam_thirds("/Users/julieta/Desktop/data_madridcff/f27/pass_matrix_903_2025_g2572345_t13320.xml", "/Users/julieta/Desktop/data_madridcff/f40/f40-squad-102.xml","all")
#passnetwork_oneteam("/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f27/pass_matrix_903_2025_g2572323_t13323.xml", "/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f40/F40-squad-903.xml",1)
