#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 30 11:43:43 2025

@author: julieta
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from scipy.stats import percentileofscore
import os
import xml.etree.ElementTree as ET
import re
from lxml import etree 
import xmltodict
import utils_teams
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from sklearn.preprocessing import MinMaxScaler
#specific_forward_id=164900
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
#BASE_DIR="/Users/julieta/Desktop/APP_Generic_Femeni"
import warnings
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
    category=FutureWarning
)

def zones_goal(df):
    y_edges = [45.2, 48.2, 51.8, 54.8]
    z_edges = [0, 12.66, 25.33, 38]  

    # Create y_zone and z_zone bins
    df["y_zone"] = pd.cut(df["end_y"], bins=y_edges, labels=[0,1,2], include_lowest=True)
    df["z_zone"] = pd.cut(df["end_z"], bins=z_edges, labels=[0,1,2], include_lowest=True)

    df["y_zone"] = df["y_zone"].cat.add_categories([-1]).fillna(-1)
    df["z_zone"] = df["z_zone"].cat.add_categories([-1]).fillna(-1)

    
    df["zone_index"] = df.apply(lambda row: -1 if row["y_zone"]==-1 or row["z_zone"]==-1 
                                else row["z_zone"]*3 + row["y_zone"], axis=1)

    return df

def generate_graphs_forward(specific_forward_id):
    


    player_relations=pd.read_excel(f"{BASE_DIR}/forwards_analisis/player_relations.xlsx")
    match_relations=pd.read_excel(f"{BASE_DIR}/forwards_analisis/match_relations.xlsx")

    forwards=player_relations[player_relations["position"]=="Forward"].copy()
    teams_db= match_relations[["team1_name", "team1"]].drop_duplicates()

    forwards=pd.merge(forwards,teams_db,left_on="team",right_on="team1_name",how="left")

    forwards_id=forwards["player_id"].unique().tolist()

    output_file = f"{BASE_DIR}/forwards_analisis/forwards_global_stats.xlsx"

    # Read each sheet into a DataFrame
    all_countsdf = pd.read_excel(output_file, sheet_name='Counts')
    all_xgs_df = pd.read_excel(output_file, sheet_name='xG')
    all_xGOT_df = pd.read_excel(output_file, sheet_name='xGOT')
    all_goals_df = pd.read_excel(output_file, sheet_name='Goals')

    df_forwards=pd.read_excel(f"{BASE_DIR}/forwards_analisis/df_forwards.xlsx")
    num_forwards=len(df_forwards["playerref"].unique())
    ######




    specific_forward_name=forwards[forwards["player_id"]==specific_forward_id]["player"].iloc[0]
    #st.title(f"{specific_keeper_name}")
    specific_forward_team_id=forwards[forwards["player_id"]==specific_forward_id]["team1"].iloc[0]
    specific_forward_team_name=forwards[forwards["player_id"]==specific_forward_id]["team1_name"].iloc[0]

    goal_matches=df_forwards[df_forwards["playerref"]==specific_forward_id]
    specific_forward_matches_teams=goal_matches[["game_id","team","year"]]


    final_total_forwards_stats=pd.read_excel(f"{BASE_DIR}/forwards_analisis/final_total_forwards_stats.xlsx")

    all_counts=[]
    all_xgs=[]
    all_xgots=[]
    all_goals=[]
    all_shots=[]
    df_miss = pd.DataFrame()
    df_goal = pd.DataFrame()
    unique_matches = specific_forward_matches_teams["game_id"].nunique()

    for match, year,team in zip(specific_forward_matches_teams["game_id"].tolist(),specific_forward_matches_teams["year"].tolist(),specific_forward_matches_teams["team"].tolist()):
        df=utils_teams.parse_f70_events(f"{BASE_DIR}/datos_opta/903/{year}/f70/f70-903-{year}-{match}-expectedgoals.xml")
        cols = ['id','event_id','type_id','period_id','min','sec','player_id','team_id','outcome',
                'x','y','timestamp','timestamp_utc','last_modified',"321","322","102","103",'player_name']
        #print(df.columns)
        existing_cols = [c for c in cols if c in df.columns]

        if existing_cols:
           df = df[cols].copy()
        else:
            #print("Warning: None of the expected columns exist. Returning empty DataFrame.")
            df = pd.DataFrame(columns=cols)
        df["team_id"] = df["team_id"].astype(int)
        df["player_id"] = df["player_id"].astype(int)
        df=df[df["team_id"]==team]
        
        df=df[df["player_id"]==specific_forward_id]
       
        
        df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]]=df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]].astype(float)

        df=df.rename(columns={"321":"expected_goals","322":"expected_GOT","102":"end_y","103":"end_z"})
        df["expected_GOT"]=df["expected_GOT"].fillna(0)
        df["expected_goals"]=df["expected_goals"].fillna(0)
        df["end_z"]=df["end_z"].fillna(0)
        df["end_y"]=df["end_y"].fillna(0)
        
        from sklearn.preprocessing import MinMaxScaler

        scaler = MinMaxScaler(feature_range=(25, 100))

       
        df_miss_match = df[df["type_id"] != 16].copy()

        if not df_miss_match.empty:
            # Only fill NaN with 0 if you really want
            df_miss_match['expected_GOT'] = df_miss_match['expected_GOT'].fillna(0)
        
            # Only scale if there is at least one non-NaN
            non_nan_mask = df_miss_match['expected_GOT'].notna()
            if non_nan_mask.any():
                df_miss_match.loc[non_nan_mask, 'xGOT_scaled'] = scaler.fit_transform(
                    df_miss_match.loc[non_nan_mask, ['expected_GOT']]
                    )
            else:
                df_miss_match['xGOT_scaled'] = pd.NA
        else:
            df_miss_match['xGOT_scaled'] = pd.NA

        
        df_goal_match = df[df["type_id"] == 16].copy()

        if not df_goal_match.empty:
            df_goal_match['expected_GOT'] = df_goal_match['expected_GOT'].fillna(0)
            non_nan_mask = df_goal_match['expected_GOT'].notna()
            if non_nan_mask.any():
                df_goal_match.loc[non_nan_mask, 'xGOT_scaled'] = scaler.fit_transform(
                    df_goal_match.loc[non_nan_mask, ['expected_GOT']]
                    )
            else:
                df_goal_match['xGOT_scaled'] = pd.NA
        else:
            df_goal_match['xGOT_scaled'] = pd.NA

       
        df_miss = pd.concat([df_miss, df_miss_match], ignore_index=True)
        df_goal = pd.concat([df_goal, df_goal_match], ignore_index=True)

        
        df=zones_goal(df)
        df=df.drop(["y_zone","z_zone"],axis=1)

        zone_mapping={0:"low right",1:"low center",2:"low left",
                      3:"middle right",4:"middle center",5:"middle left",
                      6:"top right",7:"top center",8:"top left",
                      -1:"out"}

        df["zone_index_text"]=df["zone_index"].map(zone_mapping)



        count_zones=df.groupby("zone_index_text").size()
        all_zones = list(zone_mapping.values())
        count_zones = count_zones.reindex(all_zones, fill_value=0)
        count_zones.name = match 

        #goal_zones=count_zones.drop("out", errors="ignore")
        out_count = df[df["zone_index"] == -1].shape[0]  # count of shots outside goal

        all_counts.append(count_zones)
        
        
        xG_zones = df.groupby("zone_index_text")["expected_goals"].sum()
        xG_zones=xG_zones.drop("out", errors="ignore")
        
        xG_zones = xG_zones.reindex(all_zones, fill_value=0)
        xG_zones.name = match 
        all_xgs.append(xG_zones)
        
        xGOT_zones = df.groupby("zone_index_text")["expected_GOT"].sum()
        xGOT_zones=xGOT_zones.drop("out", errors="ignore")
        
        xGOT_zones = xGOT_zones.reindex(all_zones, fill_value=0)
        xGOT_zones.name = match 
        all_xgots.append(xGOT_zones)
        df_goals=df[df["type_id"]==16]
        
        goal_zones=df_goals.groupby("zone_index_text").size()
        all_zones = list(zone_mapping.values())
        goal_zones = goal_zones.reindex(all_zones, fill_value=0)
        goal_zones.name = match 
        all_goals.append(goal_zones)

    all_countsdf_forward= pd.concat(all_counts, axis=1).T
    all_xgs_df_forward=pd.concat(all_xgs,axis=1).T
    all_xGOT_df_forward=pd.concat(all_xgots,axis=1).T
    all_goals_df_forward=pd.concat(all_goals,axis=1).T

    ### % de tiros a cada zona GLOBAL
    overall_counts = all_countsdf.sum(axis=0)
    all_shots=int(overall_counts.sum())
    overall_counts=(overall_counts/all_shots)*100
    goal_zones=overall_counts.drop("out", errors="ignore")
    out_count = out_shots_total = overall_counts['out']

    # defino cosas genericas para todas las gráficas
    
    
    
    y_edges = [45.2, 48.2, 51.8, 54.8]
    z_edges = [0, 12.66, 25.33, 38]  

    # Goal coordinates
    goal_y = 0
    goal_height = 38.1
    goal_left = 45.1
    goal_right = 54.9

    img=mpimg.imread(f"{BASE_DIR}/forwards_analisis/goal.jpg")


    #### FIGURA 1 NÚMERO DE TIROS POR ZONA GLOBAL DE LAS 2 TEMPS
    counts=goal_zones.tolist()
    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    x_edges=y_edges
    
    #x_edges = np.linspace(goal_left, goal_right, 4)
    #y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}%", ha='center', va='center', fontsize=12, color='black', fontweight='bold')


    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 5,
            f"Fuera: {out_count:.2f}%", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')
    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"% de tiros a cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("Tiros_puerta_global.png")
    plt.close(fig)



    ######## FIGURA 2

    ### GOLES EN CADA ZONA 
    overall_goals = all_goals_df.sum(axis=0)
    all_goals=int(overall_goals.sum())
    #overall_counts=(overall_counts/all_shots)*100
    goal_scored_zones=overall_goals.drop("out", errors="ignore")
    goal_scored_zones_num=goal_scored_zones.copy()

    counts=goal_scored_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
     
    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"Número de goles en a cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("Goles_global.png")
    plt.close(fig)


    ####### FIGURA 3

    ### % de GOLES EN CADA ZONA 
    overall_goals = all_goals_df.sum(axis=0)
    all_goals=int(overall_goals.sum())
    overall_goals=(overall_goals/all_goals)*100
    goal_scored_zones=overall_goals.drop("out", errors="ignore")
    goal_scored_zones_perc=goal_scored_zones.copy()

    counts=goal_scored_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}%", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"% de goles en a cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("porcentaje_goles_global.png")
    plt.close(fig)


    ######### FIGURA 4

    ### XG A CADA ZONA GLOBAL sumatorio total
    overall_xg = all_xgs_df.sum(axis=0)


    xg_zones=overall_xg.drop("out", errors="ignore")

    counts=xg_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))


    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )


    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
     
    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xG de toda la temporada para cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("xg_global.png")
    plt.close(fig)


    ########### FIGURA 5

    ## XG PROMEDIO GLOBAL de cada zona
    mean_xg = all_xgs_df.mean(axis=0)

    xg_mean_zones=mean_xg.drop("out", errors="ignore")


    counts=xg_mean_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xG medio para cada zona por partido", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("xG_medio_global.png")
    plt.close(fig)


    ########## FIGURA 6

    ####### xG por tiro en cada zona

    xg_por_tiro = all_xgs_df / all_countsdf
    xg_por_tiro = xg_por_tiro.fillna(0)

    mean_xg_shot = xg_por_tiro.mean(axis=0)

    xg_shot_zones=mean_xg_shot.drop("out", errors="ignore")

    counts=xg_shot_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xG por tiro para cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("XG_por_tiro_global.png")
    plt.close(fig)


    ########### FIGURA 7

    ####### xGOT
    overall_xgot = all_xGOT_df.sum(axis=0)

    xgot_zones=overall_xgot.drop("out", errors="ignore")
     
    counts=xgot_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xGOT de toda la temporada para cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("xGOT_global.png")
    plt.close(fig)


    ########### FIGURA 8

    ## XGOT PROMEDIO GLOBAL de cada zona
    mean_xgot = all_xGOT_df.mean(axis=0)

    xgot_mean_zones=mean_xgot.drop("out", errors="ignore")

    counts=xgot_mean_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xGOT medio para cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #plt.savefig("xGOT_medio_global.png")
    plt.close(fig)


    ############ FIGURA 9

    xgot_por_tiro = all_xGOT_df / all_countsdf
    xgot_por_tiro = xgot_por_tiro.fillna(0)

    mean_xgot_shot = xgot_por_tiro.mean(axis=0)

    xgot_shot_zones=mean_xgot_shot.drop("out", errors="ignore")


    counts=xgot_shot_zones.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 70)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        #bgcolor = 'blue' if count > 3 else 'red'
        ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')

    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
            f"xGOT por tiro para cada zona", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

   #plt.savefig("xGOT_tiro_global.png")
    plt.close(fig)



    ############## FIGURA 10 - scatter goles vs xGOT

    fig,ax=plt.subplots(figsize=(16, 8))
    import seaborn as sns

    sns.scatterplot(data=final_total_forwards_stats,x="total_goals",y="total_xGOT",s=300,facecolors="none",edgecolor="black",ax=ax)
    for i, row in final_total_forwards_stats.iterrows():
        plt.text(row['total_goals'], row['total_xGOT'], row['player'], fontsize=12, alpha=0.8,zorder=2)
    plt.xlabel("Goles marcados")
    plt.ylabel("xGOT total")

    #plt.savefig("Scatter_goles_xGOT_global.png")
    plt.close(fig)

    ##########



    forwards_stats_mean=pd.read_excel(f"{BASE_DIR}/forwards_analisis/forwards_stats_means.xlsx")
    numeric_cols = ["mean_shots", "mean_xG", "mean_xGOT", "mean_goals"]
    zone_means = forwards_stats_mean.groupby("zone_index_text")[numeric_cols].mean().reset_index()
    zone_means=zone_means[zone_means["zone_index_text"]!="out"]


    forwards_stats_total=pd.read_excel(f"{BASE_DIR}/forwards_analisis/forwards_stats_totals.xlsx")
    numeric_cols = ["total_shots", "total_xG", "total_xGOT", "total_goals"]
    zone_totals = forwards_stats_total.groupby("zone_index_text")[numeric_cols].mean().reset_index()
    zone_totals["perc_goals"]=(zone_totals['total_goals'] / zone_totals['total_goals'].sum()) * 100
    
    zone_totals["perc_shots"]=(zone_totals['total_shots'] / zone_totals['total_shots'].sum()) * 100
    zone_totals["goles-xgot"]=zone_totals["total_goals"]-zone_totals["total_xGOT"]
    zone_totals["efectivity"]=(zone_totals['total_goals'] / zone_totals['total_shots']) * 100
    zone_totals=zone_totals[zone_totals["zone_index_text"]!="out"]
    
    
    zone_totals = zone_totals.fillna(0)


    ### % de tiros a cada zona GLOBAL
    overall_counts_forward = all_countsdf_forward.sum(axis=0)
    all_shots_forward=int(overall_counts_forward.sum())
    shots_num_forward=overall_counts_forward.copy()
    shots_num_forward=shots_num_forward.drop("out", errors="ignore")

    overall_counts_forward=(overall_counts_forward/all_shots_forward)*100
    goal_zones_forward=overall_counts_forward.drop("out", errors="ignore")
    out_count_forward= overall_counts_forward['out']
    overall_xgot_forward = all_xGOT_df_forward.sum(axis=0)

    xgot_zones_forward=overall_xgot_forward.drop("out", errors="ignore")

    ############ FIGURA 20 (pero en realidad 11)
    overall_goals_forward = all_goals_df_forward.sum(axis=0)
    all_goals_forward=int(overall_goals_forward.sum())
    #overall_counts=(overall_counts/all_shots)*100
    goal_scored_zones_forward=overall_goals_forward.drop("out", errors="ignore")


    counts=(goal_scored_zones_forward-xgot_zones_forward).tolist()


    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["goles-xgot"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="blue"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)
        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 5,
    #         f"Fuera: {out_count_keeper:.2f}%", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de tiros a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("Goles - xGOT en cada zona durante 2 temporadas")
    plt.savefig(f"goles_xGOT_{specific_forward_name}.png")
    plt.close(fig)

    ########## FIGURA 21 (en realidad 12)


    counts = ((goal_scored_zones_forward / shots_num_forward)* 100).fillna(0).tolist()
    
    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["efectivity"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="blue"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)
        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f} %", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 5,
    #         f"Fuera: {out_count_keeper:.2f}%", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de tiros a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("Efectividad por zona durante 2 temporadas (% de tiros que acaban en gol)")
    plt.savefig(f"efectividad_tiros_{specific_forward_name}.png")
    plt.close(fig)


    ############### FIGURA 11 

    counts=goal_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["perc_shots"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="blue"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)
        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}%", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 5,
            f"Fuera: {out_count_forward:.2f}%", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de tiros a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("% de tiros en cada zona durante 2 temporadas")
    plt.savefig(f"porcentaje_tiros_{specific_forward_name}.png")
    plt.close(fig)


    ######## FIGURA 12

    ### GOLES EN CADA ZONA 
    overall_goals_forward = all_goals_df_forward.sum(axis=0)
    all_goals_forward=int(overall_goals_forward.sum())
    #overall_counts=(overall_counts/all_shots)*100
    goal_scored_zones_forward=overall_goals_forward.drop("out", errors="ignore")

    counts=goal_scored_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["total_goals"].iloc[zone_index]
        
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"Número de goles en a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("Número de goles cada zona durante 2 temporadas")
    plt.savefig(f"goles_zona_{specific_forward_name}.png")
    plt.close(fig)


    ############### FIGURA 13

    ### % de GOLES EN CADA ZONA 
    overall_goals_forward = all_goals_df_forward.sum(axis=0)
    all_goals_forward=int(overall_goals_forward.sum())
    overall_goals_forward=(overall_goals_forward/all_goals_forward)*100
    goal_scored_zones_forward=overall_goals_forward.drop("out", errors="ignore")

    counts=goal_scored_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )

    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["perc_goals"].iloc[zone_index]
        
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MÁS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)
        #print(f"ZONE: {zone_index}, COUNT: {count}, TARGET: {target}, COLOR: {bgcolor}")
        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}%", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de goles en a cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #st.title("% de goles en cada zona durante 2 temporadas")
    #plt.savefig(f"porcentaje_goles_zona_{specific_forward_name}.png")
    plt.close(fig)


    ########## FIGURA 14

    ### XG A CADA ZONA sumatorio de toda la temporada UNA PORTERA
    overall_xg_forward = all_xgs_df_forward.sum(axis=0)

    xg_zones_forward=overall_xg_forward.drop("out", errors="ignore")

    counts=xg_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["total_xG"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG de toda la temporada para cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #st.title("xG en cada zona durante 2 temporadas")
    #plt.savefig(f"xG_zona_total_{specific_forward_name}.png")
    plt.close(fig)


    ######### FIGURA 15

    ## XG PROMEDIO GLOBAL de cada zona
    mean_xg_forward = all_xgs_df_forward.mean(axis=0)

    xg_mean_zones_forward=mean_xg_forward.drop("out", errors="ignore")

    counts=xg_mean_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_means["mean_xG"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG medio para cada zona por partido, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #st.title("xG por partido en cada zona")
    #plt.savefig(f"xG_porpartido_{specific_forward_name}.png")
    plt.close(fig)


    ######## FIGURA 16
    ####### xG por tiro en cada zona

    xg_por_tiro_forward = all_xgs_df_forward / all_countsdf_forward
    xg_por_tiro_forward = xg_por_tiro_forward.fillna(0)

    mean_xg_shot_forward = xg_por_tiro_forward.mean(axis=0)

    xg_shot_zones_forward=mean_xg_shot_forward.drop("out", errors="ignore")

    counts=xg_shot_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = xg_shot_zones.iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG por tiro para cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("xG por tiro en cada zona")
    #plt.savefig(f"xG_portiro_{specific_forward_name}.png")
    plt.close(fig)


    ######### FIGURA 17

    ####### xGOT


    counts=xgot_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_totals["total_xGOT"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT de toda la temporada para cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("xGOT en cada zona para 2 temporadas")
    #plt.savefig(f"xGOT_total_{specific_forward_name}.png")
    plt.close(fig)


    ########## FIGURA 18

    ## XG PROMEDIO GLOBAL de cada zona
    mean_xgot_forward = all_xGOT_df_forward.mean(axis=0)

    xgot_mean_zones_forward=mean_xgot_forward.drop("out", errors="ignore")

    counts=xgot_mean_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]

        target = zone_means["mean_xGOT"].iloc[zone_index]
        if count > target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red' # ROJO ES MÁS QUE LA MEDIA (MÁS XG Y ASI)

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT medio para cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #st.title("xGOT por partido en cada zona")
    #plt.savefig(f"xGOT_partido_{specific_forward_name}.png")
    plt.close(fig)


    ########## FIGURA 19

    ####### xG por tiro en cada zona

    xgot_por_tiro_forward = all_xGOT_df_forward / all_countsdf_forward
    xgot_por_tiro_forward = xgot_por_tiro_forward.fillna(0)

    mean_xgot_shot_forward = xgot_por_tiro_forward.mean(axis=0)

    xgot_shot_zones_forward=mean_xgot_shot_forward.drop("out", errors="ignore")

    counts=xgot_shot_zones_forward.tolist()

    fig, ax = plt.subplots(figsize=(8, 4))

    ax.set_xlim(40, 60)
    ax.set_ylim(0, 60)

    ax.imshow(
        img,
        extent=[goal_left-0.3, goal_right+0.3, goal_y, goal_y + goal_height+2.3],  # position & scale
        aspect='auto',  # stretch to fit area
        zorder=0  # put it behind the rectangles
    )
    # Grid edges
    # x_edges = np.linspace(goal_left, goal_right, 4)
    # y_edges = np.linspace(goal_y, goal_y + goal_height, 4)


    # Draw rectangles
    for zone_index, count in enumerate(counts):
        row = (zone_index // 3)  # top to bottom
        col = (zone_index % 3)   # right to left

        x0 = x_edges[col]
        x1 = x_edges[col+1]
        y0 = z_edges[row]
        y1 = z_edges[row+1]
        target = xgot_shot_zones.iloc[zone_index]
        if count > target:
            bgcolor = 'green'
        elif count == target:
            bgcolor="gray"
        else:
            bgcolor = 'red'

        # Draw rectangle behind text
        ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.1)
        
        #bgcolor = 'blue' if count > 3 else 'red'
        #ax.fill_betweenx([y0, y1], x0, x1, color="blue", alpha=0.3)

        # Text in center
        x_text = (x0 + x1) / 2
        y_text = (y0 + y1) / 2
        ax.text(x_text, y_text, f"{count:.2f}", ha='center', va='center', fontsize=12, color='black', fontweight='bold')
    for i,row in df_miss.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT por tiro para cada zona, {specific_forward_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #st.title("xGOT por tiro en cada zona")
    #plt.savefig(f"xGOT_portiro_{specific_forward_name}.png")

    plt.close(fig)
    
    output_paths=[f"porcentaje_tiros_{specific_forward_name}.png",f"goles_xGOT_{specific_forward_name}.png",
                  f"goles_zona_{specific_forward_name}.png",f"efectividad_tiros_{specific_forward_name}.png"]
    
    
    
    return output_paths,all_goals_forward,unique_matches,specific_forward_name
#output_paths,all_goals_forward,unique_matches,specific_forward_name=generate_graphs_forward(164900)
#graficas_path,all_goals_keeper,unique_matches=generate_graphs_gk(186022)