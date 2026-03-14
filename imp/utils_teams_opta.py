#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 21 14:18:32 2025

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
from pathlib import Path

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
    game_id=game.attrib["id"]
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
    df_events["game_id"] = float(game_id)
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


    events = ensure_and_convert_columns(events)
    return events 

def parse_f72_xg(xml_path):
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    root=ET.fromstring(xml_content)
    team_name=root.attrib.get("team_name")
    
    players_info=[]
    
    for player in root.findall(".//SeasonPlayer"):
        name=player.attrib.get("Name")
        position = player.attrib.get("Position")  # Get player position
        
        
        expected_goals=0
        expected_goals_conceded=0
        for stat in player.findall("Stat"):
           # print(stat)
            if stat.attrib.get("Type")=="expected_goals":
                expected_goals=float(stat.text)
            elif stat.attrib.get("Type") == "expected_goals_conceded" and position == "Goalkeeper":
                expected_goals_conceded = float(stat.text)
        
        players_info.append({
            "player_name": name,
            "team": team_name,
            "expected_goals": expected_goals,
            "expected_goals_conceded": expected_goals_conceded

            })
    players_df=pd.DataFrame(players_info)
    return players_df

def parse_f72_xgot(xml_path):
    with open(xml_path, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    root=ET.fromstring(xml_content)
    team_name=root.attrib.get("team_name")
    
    players_info=[]
    
    for player in root.findall(".//SeasonPlayer"):
        name=player.attrib.get("Name")
        position = player.attrib.get("Position")  # Get player position
        
        
        expected_goals=0
        expected_goals_conceded=0
        expected_got = 0.0
        expected_got_np = 0.0

        for stat in player.findall("Stat"):
           # print(stat)
            if stat.attrib.get("Type")=="expected_goals":
                expected_goals=float(stat.text)
            elif stat.attrib.get("Type")=="expected_goalsontarget":
                expected_got=float(stat.text)
            elif stat.attrib.get("Type")=="expected_goalsontarget_nonpenalty":
                expected_got_np=float(stat.text)
            elif stat.attrib.get("Type") == "expected_goals_conceded" and position == "Goalkeeper":
                expected_goals_conceded = float(stat.text)
        
        players_info.append({
            "player_name": name,
            "team": team_name,
            "expected_goals": expected_goals,
            "expected_goals_conceded": expected_goals_conceded,
            "expected_got":expected_got,
            "expected_got_nonpenalti":expected_got_np

            })
    players_df=pd.DataFrame(players_info)
    return players_df

def get_xG_xGA_allteams(folder_f72):
    
    folder_path=Path(folder_f72)
    all_dfs = []

    for file in folder_path.glob("*.xml"):
        df = parse_f72_xg(file)  
        all_dfs.append(df)


    combined_df = pd.concat(all_dfs, ignore_index=True)
    team_summary = combined_df.groupby("team").agg({
    "expected_goals": ["sum", "mean"],
    "expected_goals_conceded": ["sum", "mean"]
    }).reset_index()
    team_summary.columns = ['_'.join(col).strip() if col[1] else col[0] for col in team_summary.columns.values]

    team_summary = team_summary.rename(columns={
        "expected_goals_mean": "expected_goals",
        "expected_goals_conceded_mean": "expected_goals_conceded"
        })
    
    team_summary["xg_difference"]=team_summary["expected_goals"]-team_summary["expected_goals_conceded"]
    
    return team_summary
    
def f_30_getshots(filepath_f30):
    with open(filepath_f30, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    root=ET.fromstring(xml_content)
    team_name=root.attrib.get("name")
    
    team_shots=[]
    
    for team in root.findall(".//Team"):
        team_name = team.attrib.get("name")
        shots=0
        shots_conceded=0 
        for stat in team.findall("Stat"):
            if stat.attrib.get("name") == "Total Shots":
                shots=float(stat.text)
            elif stat.attrib.get("name") == "Total Shots Conceded":
                shots_conceded = float(stat.text)
        
        team_shots.append({
            "team":team_name,
            "Shots":shots,
            "Shots Conceded":shots_conceded})
    team_df=pd.DataFrame(team_shots)
    return team_df

def get_shots_shotsA_allteams(folder_f30):
    
    folder_path=Path(folder_f30)
    all_dfs = []

    for file in folder_path.glob("*.xml"):
        df = f_30_getshots(file)  
        all_dfs.append(df)


    combined_df = pd.concat(all_dfs, ignore_index=True)
    
    return combined_df

import logging
logger = logging.getLogger()


def parse_teams_from_f30(folder_path, championship):
  """
  Parsea archivos XML de una carpeta, extrayendo datos de equipos y jugadores.

  Args:
      folder_path (str or Path): Ruta a la carpeta con archivos .xml

  Returns:
      tuple: (equipos_data, jugadores_data)
          - equipos_data: lista de diccionarios con stats por equipo
          - jugadores_data: lista de diccionarios con stats por jugador
  """
  folder_path = Path(folder_path)
  equipos_data = []
  

  for file in folder_path.glob("*.xml"):
      try:
          tree = ET.parse(file)
          root = tree.getroot()
      except ET.ParseError as e:
          logger.warning(f"Error al parsear {file.name}: {e}")
          continue

      competition_id = root.get("competition_id")
      if str(competition_id) != str(championship):
          continue

      league = root.get("competition_name")
      #logger.info(f"Processing file: {file.name} for league: {league}")

      for team in root.findall(".//Team"):
          team_id = team.get("id")
          team_name = team.get("name")

          # Stats del equipo
          stats_equipo = {}
          for stat in team.findall("Stat"):
              name = stat.get("name")
              value = stat.text
              try:
                  stats_equipo[name] = round(float(value), 2)
              except (TypeError, ValueError):
                  stats_equipo[name] = np.nan

          equipo_row = {
              "team_id": team_id,
              "team_name": team_name,
              "source_file": file.name,
              **stats_equipo
          }
          equipos_data.append(equipo_row)
    
  df_equipos=pd.DataFrame(equipos_data)

  return df_equipos, league

def parse_f73_possesionchain2(filepath_f73):
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
    df_events[['id', 'event_id', 'type_id', 'period_id', 'min', 'sec', 'team_id','outcome', 'x', 'y','player_id','keypass', 'sequence_id', 'possession_id']]=df_events[['id','event_id', 'type_id', 'period_id', 'min', 'sec', 'team_id','outcome', 'x', 'y',"player_id",'keypass', 'sequence_id', 'possession_id']].astype(float)
    df_events["time_minutes"] = df_events["min"] + df_events["sec"] / 60  
    df_events[["timestamp", "timestamp_utc"]] = df_events[["timestamp", "timestamp_utc"]].apply(pd.to_datetime)
    teams = pd.concat([
    team_names[['home_team_id', 'home_team_name']].rename(columns={'home_team_id': 'team_id', 'home_team_name': 'team_name'}),
    team_names[['away_team_id', 'away_team_name']].rename(columns={'away_team_id': 'team_id', 'away_team_name': 'team_name'})
    ]).drop_duplicates()
    teams["team_id"]=teams["team_id"].astype(float)
    
    df_events = df_events.merge(teams, on="team_id", how="left")
    
    
    
    team1, team2 = df_events.team_name.unique()
    
    df_events = df_events.copy()
    df_events["possession_id"] = df_events["possession_id"].replace("", np.nan)
    
    # Shift column up and down
    above = df_events["possession_id"].shift(1)
    below = df_events["possession_id"].shift(-1)

    # Fill NaN if above and below are equal
    mask = df_events["possession_id"].isna() & (above == below)
    df_events.loc[mask, "possession_id"] = above[mask]
    
    return df_events,team_names


#### en util
def get_all_matches(team_name,df_matches):
    
    mask = (df_matches["team1_name"] == team_name) | (df_matches["team2_name"] == team_name)
    return df_matches.loc[mask, "matchcode"].tolist()
#####

def get_PPDA(team_analizing,list_matches,year,filepath_f73):
    
    base_layer=filepath_f73
    all_matches = []
    
    for match_id in list_matches:
        filepath=f"{base_layer}/f73-903-{year}-{match_id}-possessions.xml"
        
        df_pass,team_names=parse_f73_possesionchain2(filepath)

        last_events = df_pass.groupby('possession_id').tail(1)

        # Find possession_ids that end in type_id == 4
        valid_possessions = last_events.loc[last_events['type_id'].isin([4,7,8,45,74,12]), 'possession_id']

        # Keep only those possessions
        
        df_pass = df_pass[df_pass['possession_id'].isin(valid_possessions)]

        df_pass = (
            df_pass.groupby("possession_id")
                   .agg(team_name=("team_name", "first"), length=("team_name", "size"))
                   .reset_index()
        )
        df_avg_length = df_pass.groupby("team_name")["length"].mean().reset_index().rename(columns={"length": "PPDA del Rival"})
        df_avg_length["PPDA"] = df_avg_length["PPDA del Rival"].iloc[::-1].values
        all_matches.append(df_avg_length)
    df_all_matches = pd.concat(all_matches, ignore_index=True)
    
    df_all_matches=df_all_matches.groupby("team_name").mean()
    team_PPDA=df_all_matches.loc[team_analizing,"PPDA"]
    others_PPDA = df_all_matches.drop(team_analizing)["PPDA"].mean()
    df_summary = pd.DataFrame({
        "team_name": [team_analizing],
        "PPDA": [team_PPDA],
        "PPDA del Rival": [others_PPDA]
        })
    
    return df_summary 

def get_all_PPDA(folder_f73,matches_filepath,team_names,year):
    
    matches_df=pd.read_excel(matches_filepath)
    all_summaries=[]
    for team in team_names:
        df_all_matches=get_all_matches(team,matches_df)
        df_summary=get_PPDA(team,df_all_matches,year,folder_f73)
        all_summaries.append(df_summary)
    df_all_summaries = pd.concat(all_summaries, ignore_index=True)
    
    return df_all_summaries

def parse_f70_xg(xml_filepath,team_analizing):
    with open(xml_filepath, 'r', encoding='utf-8') as f:
        xml_content = f.read()
    root = ET.fromstring(xml_content)
    
    # Get team names and IDs
    game = root.find(".//Game")
    game_id=game.attrib["id"]
    home_team_ref = int(game.attrib["home_team_id"])
    away_team_ref = int(game.attrib["away_team_id"])
    team_name_map = {
        home_team_ref: game.attrib["home_team_name"],
        away_team_ref: game.attrib["away_team_name"]
    }
    
    data = []

    
    for team_data in root.findall(".//TeamData"):
        
        team_ref = int(team_data.attrib.get("TeamRef")[1:])

        for player in team_data.findall(".//MatchPlayer"):
            player_id = player.attrib.get("PlayerRef")
            shirt_number = player.attrib.get("ShirtNumber")
            position = player.attrib.get("Position")
            
            # Collect stats
            stats = {stat.attrib['Type']: stat.text for stat in player.findall("Stat")}
            
           
            row = {
                "PlayerRef": player_id,
                "ShirtNumber": shirt_number,
                "Position": position,
                "TeamRef": team_ref,
                "TeamName": team_name_map[team_ref],
                "GameID":int(game_id)
            }
            row.update(stats)
            data.append(row)
    
    
    df = pd.DataFrame(data)
    

    df["expected_goals_conceded"] = df["expected_goals_conceded"].astype(float)

    df.loc[df["Position"] == "Goalkeeper", "expected_goals_conceded"] = \
    df.loc[df["Position"] == "Goalkeeper", "expected_goals_conceded"].fillna(0)
    df.loc[df["Position"] != "Goalkeeper", "expected_goals_conceded"] = 0
    df["expected_goals"] = df["expected_goals"].fillna(0).astype(float)
    

    match_summary = df.groupby(["TeamRef", "TeamName","GameID"]).agg({
        "expected_goals": "sum",
        "expected_goals_conceded": "sum"
    }).reset_index()
    match_summary["vs."]=match_summary["TeamName"].iloc[::-1].values
    match_summary=match_summary[match_summary["vs."]!=team_analizing]
    return match_summary

def count_zones(df):
    first_third = (df["x"] < 33.33).sum()
    last_third = (df["x"] > 66.66).sum()
    return pd.Series({"primer_tercio": first_third, "ultimo_tercio": last_third})

def of_def_duels(df):
    offensive = (df["first_qualifier_id"]==286).sum()
    defensive = (df["first_qualifier_id"]==285).sum()
    return pd.Series({"duelos_ofensivos": offensive, "duelos_defensivos": defensive})

