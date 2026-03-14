#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  4 12:50:59 2025

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
BASE_DIR="/Users/julieta/Desktop/APP_Generic_Femeni"

def get_last_5_matches(team_id,CHAMPIONSHIP,YEAR):
    team_id=int(team_id)

    xml_f42=f"{BASE_DIR}/datos_opta/{CHAMPIONSHIP}/{YEAR}/f42/f42-{CHAMPIONSHIP}-{YEAR}-results.xml"
    tree=ET.parse(xml_f42)

    root=tree.getroot()
    matches_data=[]
    for match_data in root.findall(".//MatchData"):
        match_id=match_data.get("uID")
        match_id_int = int(match_id[1:])
        home_team=match_data.find(".//TeamData[@Side='Home']")
        home_team_id=home_team.attrib.get("TeamRef")
        home_team_id_int=int(home_team_id[1:])
        final_score_home=int(home_team.attrib.get("Score"))
        
        away_team=match_data.find(".//TeamData[@Side='Away']")
        away_team_id=away_team.attrib.get("TeamRef")
        away_team_id_int=int(away_team_id[1:])
        final_score_away=int(away_team.attrib.get("Score"))
        
        match_row = {
            "match_id": match_id_int,
            "home_team":home_team_id_int,
            "home_final": final_score_home,
            "away_team":away_team_id_int,
            "away_final":final_score_away
        }
        matches_data.append(match_row)
    matches_data_df=pd.DataFrame(matches_data)
    #print(matches_data_df)

    if len(matches_data_df)<5:
        last_5_txt = pd.read_csv(f"{BASE_DIR}/datos_opta/Last5/last5matches.txt", sep='\t')
        last_5=last_5_txt["Last5"].values.tolist()
        
    else:
        matches_data_df=matches_data_df[(matches_data_df["home_team"]==team_id) | (matches_data_df["away_team"]==team_id)].copy()

        last_matches = matches_data_df.tail(5).reset_index(drop=True)
    
    last_5_match_id=last_matches["match_id"].tolist()
    return last_5_match_id

def parse_f24_corners(file_path_24):
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
    df_events["has_qualifier_6"] = df_events["qualifiers"].apply(
        lambda q: any(int(qual.get("qualifier_id", -1)) == 6 for qual in q) if q else False
        )
    return df_events,team_names

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


def get_image_corner(team_id_analizing,year):
    all_corners=[]
    last_5_matches=get_last_5_matches(team_id_analizing,903,year)
    for match_id in last_5_matches:
        
        df_events,team_names=parse_f24_corners(f"/Users/julieta/Desktop/APP_Generic_Femeni/datos_opta/903/{year}/f24/f24-903-{year}-{match_id}-eventdetails.xml")

        home_team=team_names["home_team_name"][0]
        home_id=int(team_names["home_team_id"][0])
        away_team=team_names["away_team_name"][0]
        away_id=int(team_names["away_team_id"][0])

        if home_id==team_id_analizing:
            team_name=home_team
        
        elif away_id==team_id_analizing:
            team_name=away_team
        
        df_corners=df_events[df_events["has_qualifier_6"]==True]
        df_corners=df_corners[df_corners["team_id"]==team_id_analizing]
        if df_corners.empty:
            print("No hay corners")
            return None

        df_corners[["end_x", "end_y"]] = df_corners["qualifiers"].apply(extract_end_coordinates)
        df_corners["player_recipient"] = None
        all_corners.append(df_corners)
    if all_corners:
        df_corners = pd.concat(all_corners, ignore_index=True)
    else:
        df_corners = pd.DataFrame()  
        

    for i,row in df_corners.iterrows():
        event_id=row["event_id"]
        idx = df_events.index[df_events['event_id'] == event_id].tolist()
        
        if idx:
            idx=idx[0]
            if idx+1<len(df_events):
                next_row = df_events.iloc[idx + 1]
                
                if next_row["team_id"]==team_id_analizing:
                    df_corners.loc[i, "player_recipient"] = next_row["player_id"]

    # habría que sacar la relation entre player id, jersey number y player name

    player_relations=pd.read_excel(f"/Users/julieta/Desktop/APP_Generic_Femeni/datos_opta/players_relations_{year}.xlsx")
    player_relations=player_relations[(player_relations["team"]==team_name)]
    player_relations=player_relations[["player","player_id","jersey_num"]]

    df_corners=pd.merge(df_corners,player_relations,on="player_id",how="left")
    df_corners=df_corners.rename(columns={"player":"taker","jersey_num":"jersey_taker"})

    df_corners["player_recipient"] = pd.to_numeric(df_corners["player_recipient"], errors="coerce").astype("Int64")

    df_corners=pd.merge(df_corners,player_relations,left_on="player_recipient",right_on="player_id",how="left")
    df_corners=df_corners.rename(columns={"player":"receiver","jersey_num":"jersey_receiver"})


    

    def pitch_zones(df):
        
        x_edges=[50,83,100]
        y_edges=[0,21.1,50,78.9,100]
        
        df["x_zone"]=pd.cut(df["end_x"],bins=x_edges,labels=[0,1],include_lowest=True)
        df["y_zone"]=pd.cut(df["end_y"],bins=y_edges,labels=[0,1,2,3],include_lowest=True)
        
        
        df["x_zone"] = df["x_zone"].cat.add_categories([-1]).fillna(-1)
        df["y_zone"] = df["y_zone"].cat.add_categories([-1]).fillna(-1)
        
        df["zone_index"] = df.apply(
                lambda row: -1 if row["x_zone"] == -1 or row["y_zone"] == -1 
                else int(row["y_zone"]) * 2 + int(row["x_zone"]),
                axis=1
                )
        return df

    df_corners=pitch_zones(df_corners)
    
    df_right_corners=df_corners[df_corners["y"]<50].copy()
    
    df_left_corners=df_corners[df_corners["y"]>50].copy()
    
    ####### PRIMERO RIGHT
    succ_corners_right=df_right_corners[df_corners["outcome"]==1]
    fail_corners_right=df_right_corners[df_corners["outcome"]==0]



    takers_right = (
        df_right_corners.groupby(["jersey_taker", "taker"])
        .size()  # count how many times each pair appears
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)  # sort by count descending
        .assign(
            combined=lambda x: x["jersey_taker"].astype(str) + " - " + x["taker"] + " (" + x["count"].astype(str) + ")"
            )["combined"]
        .tolist()
        )

    text_takers_right = "\n".join(takers_right)

    recipients_right = (
        df_right_corners.dropna(subset=["jersey_receiver", "receiver"])
        .groupby(["jersey_receiver", "receiver"])
        .size()
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)
        .assign(combined=lambda x: x["jersey_receiver"].astype(str) + " - " + x["receiver"] + " (" + x["count"].astype(str) + ")")
        ["combined"]
        .tolist()
    )

    text_receivers_right = "\n".join(recipients_right)
    
    df_corners_zones_right = (df_right_corners.groupby("zone_index").size()
        .reindex(range(8), fill_value=0)  
        .reset_index(name="count")
    )

    df_corners_zones_right["count"]=(df_corners_zones_right["count"]/df_corners_zones_right["count"].sum())*100

    pitch = Pitch(pitch_type='opta', pitch_color='#FFFFFF', line_color='black',half=True)
    fig, ax = pitch.draw(figsize=(20, 12), constrained_layout=True, tight_layout=False)
    fig.set_facecolor('#FFFFFF')
    counts=df_corners_zones_right["count"]
    x_edges=[50,83,100]
    y_edges=[0,21.1,50,78.9,100]
    for zone_index, count in enumerate(counts):
        row = (zone_index // 2)  # bottom to top
        col = (zone_index % 2)   # left to right

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = y_edges[row]
        y1 = y_edges[row+1]
        

        
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        if zone_index in [0,2,4,6]:
            x_text=0.60 * (x0 + x1)
            
        if count!=0:
            
            ax.text(x_text, y_text, f"{count:.2f} %", ha='right', va='center', fontsize=14, color='black', fontweight='bold')


    # Plot the completed passes
    pitch.lines(succ_corners_right.x, succ_corners_right.y,
                 succ_corners_right.end_x, succ_corners_right.end_y, lw=2, color='#ad993c', ax=ax, label='Córner conectado')

    # Plot the other passes
    pitch.lines(fail_corners_right.x, fail_corners_right.y,
                 fail_corners_right.end_x, fail_corners_right.end_y, lw=2,
                 color='#ba4f45', ax=ax, label='Córner no conectado')

    for i,row in succ_corners_right.iterrows():
        ax.scatter(row.end_x,row.end_y,s=700,color="blue",alpha=0.3)
        if pd.notna(row["jersey_receiver"]):
            ax.text(row.end_x,  row.end_y,     row["jersey_receiver"],
                    fontsize=12,color="black",ha="center", va="center")
    for i,row in fail_corners_right.iterrows():
        ax.scatter(row.end_x,row.end_y,s=400,color="red",alpha=0.3,marker="X")

    ax.text(51,95,"Jugadoras sacadoras",fontsize=16,color="black",va="top",ha="left")
    ax.text(51,90,text_takers_right,fontsize=16,color="black",va="top",ha="left")

    ax.text(51,50,"Jugadoras conectadas",fontsize=16,color="black",va="top",ha="left")
    ax.text(51,45,text_receivers_right,fontsize=16,color="black",va="top",ha="left")
    # Set up the legend
    ax.legend(facecolor='#FFFFFF', handlelength=5, edgecolor='None', fontsize=12, loc='upper left')

    # Set the title
    ax_title = ax.set_title(f'Corners {team_name}', fontsize=30)
    plt.savefig(f"Corners_{team_name}_5_partidos_derecha.png",bbox_inches="tight")
    plt.close(fig)
    
    ####### SEGUNDO LEFT
    
    succ_corners_left=df_left_corners[df_corners["outcome"]==1]
    fail_corners_left=df_left_corners[df_corners["outcome"]==0]



    takers_left = (
        df_left_corners.groupby(["jersey_taker", "taker"])
        .size()  # count how many times each pair appears
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)  # sort by count descending
        .assign(
            combined=lambda x: x["jersey_taker"].astype(str) + " - " + x["taker"] + " (" + x["count"].astype(str) + ")"
            )["combined"]
        .tolist()
        )

    text_takers_left = "\n".join(takers_left)

    recipients_left = (
        df_left_corners.dropna(subset=["jersey_receiver", "receiver"])
        .groupby(["jersey_receiver", "receiver"])
        .size()
        .reset_index(name="count")
        .sort_values(by="count", ascending=False)
        .assign(combined=lambda x: x["jersey_receiver"].astype(str) + " - " + x["receiver"] + " (" + x["count"].astype(str) + ")")
        ["combined"]
        .tolist()
    )

    text_receivers_left = "\n".join(recipients_left)
    
    df_corners_zones_left = (df_left_corners.groupby("zone_index").size()
        .reindex(range(8), fill_value=0)  
        .reset_index(name="count")
    )

    df_corners_zones_left["count"]=(df_corners_zones_left["count"]/df_corners_zones_left["count"].sum())*100

    pitch = Pitch(pitch_type='opta', pitch_color='#FFFFFF', line_color='black',half=True)
    fig, ax = pitch.draw(figsize=(20, 12), constrained_layout=True, tight_layout=False)
    fig.set_facecolor('#FFFFFF')
    
    counts=df_corners_zones_left["count"]
    x_edges=[50,83,100]
    y_edges=[0,21.1,50,78.9,100]
    for zone_index, count in enumerate(counts):
        row = (zone_index // 2)  # bottom to top
        col = (zone_index % 2)   # left to right

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = y_edges[row]
        y1 = y_edges[row+1]
        

        
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        if zone_index in [0,2,4,6]:
            x_text=0.60 * (x0 + x1)
        if count!=0:
            ax.text(x_text, y_text, f"{count:.2f} %", ha='right', va='center', fontsize=14, color='black', fontweight='bold')


    # Plot the completed passes
    pitch.lines(succ_corners_left.x, succ_corners_left.y,
                 succ_corners_left.end_x, succ_corners_left.end_y, lw=2, color='#ad993c', ax=ax, label='Córner conectado')

    # Plot the other passes
    pitch.lines(fail_corners_left.x, fail_corners_left.y,
                 fail_corners_left.end_x, fail_corners_left.end_y, lw=2,
                 color='#ba4f45', ax=ax, label='Córner no conectado')

    for i,row in succ_corners_left.iterrows():
        
        ax.scatter(row.end_x,row.end_y,s=700,color="blue",alpha=0.3)
        if pd.notna(row["jersey_receiver"]):
            ax.text(row.end_x,  row.end_y,     row["jersey_receiver"],
                    fontsize=12,color="black",ha="center", va="center")
    for i,row in fail_corners_left.iterrows():
        ax.scatter(row.end_x,row.end_y,s=400,color="red",alpha=0.3,marker="X")

    ax.text(51,95,"Jugadoras sacadoras",fontsize=16,color="black",va="top",ha="left")
    ax.text(51,90,text_takers_left,fontsize=16,color="black",va="top",ha="left")

    ax.text(51,50,"Jugadoras conectadas",fontsize=16,color="black",va="top",ha="left")
    ax.text(51,45,text_receivers_left,fontsize=16,color="black",va="top",ha="left")
    # Set up the legend
    ax.legend(facecolor='#FFFFFF', handlelength=5, edgecolor='None', fontsize=12, loc='upper left')

    # Set the title
    ax_title = ax.set_title(f'Corners {team_name}', fontsize=30)
    plt.savefig(f"Corners_{team_name}_5_partidos_izquierda.png",bbox_inches="tight")
    plt.close(fig)
    
get_image_corner(13322,2024)
