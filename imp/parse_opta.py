#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Oct 17 12:48:07 2025

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
from datetime import datetime, date

BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
def calculate_age(born):
    born = datetime.strptime(born, "%Y-%m-%d").date()
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))

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
            player_id=player.get("uID")
            player_id=player_id[1:]
            player_id=int(player_id)
            jersey_stat = player.find('.//Stat[@Type="jersey_num"]')
            birth_date=player.find('.//Stat[@Type="birth_date"]').text
            
            if birth_date!="Unknown":
                age=calculate_age(birth_date)
            else:
                age="Sin especificar"
                
            
                
            weight=player.find('.//Stat[@Type="weight"]').text
            height=player.find('.//Stat[@Type="height"]').text
            preferred_foot_element=player.find('.//Stat[@Type="preferred_foot"]')
            preferred_foot = preferred_foot_element.text if preferred_foot_element is not None else "Sin especificar"
            jersey_number = jersey_stat.text if jersey_stat is not None else None  # Manejar si no existe
            
            first_nationality_element=player.find('.//Stat[@Type="first_nationality"]')
            first_nationality = first_nationality_element.text if first_nationality_element is not None else "Sin especificar"
            # Añadir los datos a la lista, incluyendo el equipo
            jugadores_data.append({
                "player": player_name,
                "player_id":player_id,
                "position": position,
                "team": team_name,
                "birthdate":birth_date,
                "age":age,
                "weight":weight,
                "height":height,
                "prefered_foot":preferred_foot,
                "first_nationality":first_nationality,
                "jersey_num": jersey_number
            })

    # Crear un DataFrame con los datos extraídos
    df_jugadores = pd.DataFrame(jugadores_data)

    #df_jugadores = df_jugadores[df_jugadores["team"] == team_analizing]
    # antes de juntar los dos dataframes voy a quitar todas las tildes prq a veces no coinciden
    replace_dict = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")
    df_jugadores["player"] = df_jugadores["player"].str.translate(replace_dict)
    
    return df_jugadores, equipos 

#df_jugadores, equipos = parse_f40("/Users/julieta/Desktop/data_2526/2025/f40/f40-squad-102.xml","Atlético de Madrid Femenino")






import logging
logger = logging.getLogger()

def parse_teams_and_players_from_f30(folder_path, championship,year):
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
  jugadores_data = []
  pattern = f"seasonstats-{championship}-{year}-*.xml"


  for file in folder_path.glob(pattern):
      
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
          team_name = team.get("short")

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

          # Jugadores del equipo
          for player in team.findall("Player"):
              player_id = player.get("player_id")
              first_name = player.get("first_name") or ""
              last_name = player.get("last_name") or ""
              #player_name = f"{first_name} {last_name}".strip()
              player_name = player.get("known_name") or f"{first_name} {last_name}".strip()
              position = player.get("position")

              stats_jugador = {}
              for stat in player.findall("Stat"):
                  name = stat.get("name")
                  value = stat.text
                  try:
                      stats_jugador[name] = round(float(value), 2)
                  except (TypeError, ValueError):
                      stats_jugador[name] = np.nan

              jugador_row = {
                  "team_id": team_id,
                  "team_name": team_name,
                  "player_id": player_id,
                  "player_name": player_name,
                  "first_name": first_name,
                  "last_name": last_name,
                  "position": position,
                  "source_file": file.name,
                  **stats_jugador
              }
              jugadores_data.append(jugador_row)

  return equipos_data, jugadores_data, league


# def parse_teams_and_players_from_f30(folder_path, championship):
#   """
#   Parsea archivos XML de una carpeta, extrayendo datos de equipos y jugadores.

#   Args:
#       folder_path (str or Path): Ruta a la carpeta con archivos .xml

#   Returns:
#       tuple: (equipos_data, jugadores_data)
#           - equipos_data: lista de diccionarios con stats por equipo
#           - jugadores_data: lista de diccionarios con stats por jugador
#   """
#   folder_path = Path(folder_path)
#   equipos_data = []
#   jugadores_data = []

#   for file in folder_path.glob("*.xml"):
#       try:
#           tree = ET.parse(file)
#           root = tree.getroot()
#       except ET.ParseError as e:
#           logger.warning(f"Error al parsear {file.name}: {e}")
#           continue

#       competition_id = root.get("competition_id")
#       if str(competition_id) != str(championship):
#           continue

#       league = root.get("competition_name")
      
#       #logger.info(f"Processing file: {file.name} for league: {league}")

#       for team in root.findall(".//Team"):
#           team_id = team.get("id")
#           team_name = team.get("short")

#           # Stats del equipo
#           stats_equipo = {}
#           for stat in team.findall("Stat"):
#               name = stat.get("name")
#               value = stat.text
#               try:
#                   stats_equipo[name] = round(float(value), 2)
#               except (TypeError, ValueError):
#                   stats_equipo[name] = np.nan

#           equipo_row = {
#               "team_id": team_id,
#               "team_name": team_name,
#               "source_file": file.name,
#               **stats_equipo
#           }
#           equipos_data.append(equipo_row)

#           # Jugadores del equipo
#           for player in team.findall("Player"):
#               player_id = player.get("player_id")
#               first_name = player.get("first_name") or ""
#               last_name = player.get("last_name") or ""
#               #player_name = f"{first_name} {last_name}".strip()
#               player_name = player.get("known_name") or f"{first_name} {last_name}".strip()
#               position = player.get("position")

#               stats_jugador = {}
#               for stat in player.findall("Stat"):
#                   name = stat.get("name")
#                   value = stat.text
#                   try:
#                       stats_jugador[name] = round(float(value), 2)
#                   except (TypeError, ValueError):
#                       stats_jugador[name] = np.nan

#               jugador_row = {
#                   "team_id": team_id,
#                   "team_name": team_name,
#                   "player_id": player_id,
#                   "player_name": player_name,
#                   "first_name": first_name,
#                   "last_name": last_name,
#                   "position": position,
#                   "source_file": file.name,
#                   **stats_jugador
#               }
#               jugadores_data.append(jugador_row)

#   return equipos_data, jugadores_data, league


def get_data_opta(folder_pathf30,year):
    #"/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f30"
    folder_pathf30=f"{folder_pathf30}/{year}/f30"
    
    equipos_data, jugadores_data, league=parse_teams_and_players_from_f30(folder_pathf30, 903,year)
    df_teams = pd.DataFrame(equipos_data)
    df_players = pd.DataFrame(jugadores_data)

    df_players["player_id"]=df_players["player_id"].astype(int)

    df_players_full=pd.merge(df_players,df_jugadores,left_on="player_id",right_on="player_id",how="left")

    # df_players_unique = df_players_full.drop_duplicates(subset='player_id_x', keep='first')

    #df_players_unique = df_players_unique.drop(columns=[col for col in df_players_unique.columns if col.endswith('_y')])
    df_players_full.rename(columns=lambda col: col[:-2] if col.endswith('_x') else col, inplace=True)
    df_players_full.drop_duplicates(subset='player_id', keep='first', inplace=True)
    df_players_full.to_excel(f"LigaF_opta_{year}.xlsx",index=False)
    filename=f"{BASE_DIR}/data/LigaF_opta_{year}.xlsx"
    return filename



#get_data_opta("/Users/julieta/Desktop/data_2526",2025)