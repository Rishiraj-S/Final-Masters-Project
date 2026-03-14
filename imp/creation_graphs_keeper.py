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
#specific_keeper_id=460040
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
import warnings
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated",
    category=FutureWarning
)

def generate_graphs_gk(specific_keeper_id):
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


    player_relations=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/player_relations.xlsx")
    match_relations=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/match_relations.xlsx")

    goalkeepers=player_relations[player_relations["position"]=="Goalkeeper"].copy()
    teams_db= match_relations[["team1_name", "team1"]].drop_duplicates()

    goalkeepers=pd.merge(goalkeepers,teams_db,left_on="team",right_on="team1_name",how="left")

    goalkeepers_id=goalkeepers["player_id"].unique().tolist()

    output_file = f"{BASE_DIR}/goalkeepers_analisis/keepers_global_stats.xlsx"

    # Read each sheet into a DataFrame
    all_countsdf = pd.read_excel(output_file, sheet_name='Counts')
    all_xgs_df = pd.read_excel(output_file, sheet_name='xG')
    all_xGOT_df = pd.read_excel(output_file, sheet_name='xGOT')
    all_goals_df = pd.read_excel(output_file, sheet_name='Goals')

    df_goalkeepers=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/df_goalkeepers.xlsx")
    num_goalkeepers=len(df_goalkeepers["playerref"].unique())
    ######




    specific_keeper_name=goalkeepers[goalkeepers["player_id"]==specific_keeper_id]["player"].iloc[0]
    #st.title(f"{specific_keeper_name}")
    specific_keeper_team_id=goalkeepers[goalkeepers["player_id"]==specific_keeper_id]["team1"].iloc[0]
    specific_keeper_team_name=goalkeepers[goalkeepers["player_id"]==specific_keeper_id]["team1_name"].iloc[0]

    #df_matches_keeper=matches_relations[]


    goal_matches=df_goalkeepers[df_goalkeepers["playerref"]==specific_keeper_id]
    specific_keeper_matches_teams=goal_matches[["game_id","team","year"]]


    final_total_keeper_stats=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/final_total_keeper_stats.xlsx")

    all_counts=[]
    all_xgs=[]
    all_xgots=[]
    all_goals=[]
    all_shots=[]
    df_miss = pd.DataFrame()
    df_goal = pd.DataFrame()
    unique_matches = specific_keeper_matches_teams["game_id"].nunique()

    for match, year,team in zip(specific_keeper_matches_teams["game_id"].tolist(),specific_keeper_matches_teams["year"].tolist(),specific_keeper_matches_teams["team"].tolist()):
        df=utils_teams.parse_f70_events(f"{BASE_DIR}/datos_opta/903/{year}/f70/f70-903-{year}-{match}-expectedgoals.xml")
        cols = ['id','event_id','type_id','period_id','min','sec','player_id','team_id','outcome',
                'x','y','timestamp','timestamp_utc','last_modified',"321","322","102","103",'player_name']
        #print(df.columns)
        df = df[cols].copy()
        df["team_id"] = df["team_id"].astype(int)
        
        df=df[df["team_id"]!=team]
       
        
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

    all_countsdf_keeper= pd.concat(all_counts, axis=1).T
    all_xgs_df_keeper=pd.concat(all_xgs,axis=1).T
    all_xGOT_df_keeper=pd.concat(all_xgots,axis=1).T
    all_goals_df_keeper=pd.concat(all_goals,axis=1).T

    ### % de tiros a cada zona GLOBAL
    overall_counts = all_countsdf.sum(axis=0)
    all_shots=int(overall_counts.sum())
    overall_counts=(overall_counts/all_shots)*100
    goal_zones=overall_counts.drop("out", errors="ignore")
    out_count = out_shots_total = overall_counts['out']

    # defino cosas genericas para todas las gráficas
    y_edges = [45.2, 48.2, 51.8, 54.8]
    z_edges = [0, 12.66, 25.33, 38]  
    x_edges=y_edges

    # Goal coordinates
    goal_y = 0
    goal_height = 38.1
    goal_left = 45.1
    goal_right = 54.9

    img=mpimg.imread(f"{BASE_DIR}/goalkeepers_analisis/goal.jpg")


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

    sns.scatterplot(data=final_total_keeper_stats,x="total_goals",y="total_xGOT",s=300,facecolors="none",edgecolor="black",ax=ax)
    for i, row in final_total_keeper_stats.iterrows():
        plt.text(row['total_goals'], row['total_xGOT'], row['player'], fontsize=12, alpha=0.8,zorder=2)
    plt.xlabel("Goles encajados")
    plt.ylabel("xGOT total")
    
    #plt.savefig("Scatter_goles_xGOT_global.png")
    plt.close(fig)
    
    ##########
    
    keepers_stats_mean=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/keepers_stats.xlsx")
    numeric_cols = ["mean_shots", "mean_xG", "mean_xGOT", "mean_goals"]
    zone_means = keepers_stats_mean.groupby("zone_index_text")[numeric_cols].mean().reset_index()



    keepers_stats_mean=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/keepers_stats_means.xlsx")
    numeric_cols = ["mean_shots", "mean_xG", "mean_xGOT", "mean_goals"]
    zone_means = keepers_stats_mean.groupby("zone_index_text")[numeric_cols].mean().reset_index()
    zone_means=zone_means[zone_means["zone_index_text"]!="out"]


    keepers_stats_total=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/keepers_stats_totals.xlsx")
    numeric_cols = ["total_shots", "total_xG", "total_xGOT", "total_goals"]
    zone_totals = keepers_stats_total.groupby("zone_index_text")[numeric_cols].mean().reset_index()
    zone_totals["perc_goals"]=(zone_totals['total_goals'] / zone_totals['total_goals'].sum()) * 100
    zone_totals["perc_shots"]=(zone_totals['total_shots'] / zone_totals['total_shots'].sum()) * 100
    zone_totals["goles-xgot"]=zone_totals["total_goals"]-zone_totals["total_xGOT"]
    zone_totals["efectivity"]=(zone_totals['total_goals'] / zone_totals['total_shots']) * 100
    zone_totals=zone_totals[zone_totals["zone_index_text"]!="out"]
    
    

    ### % de tiros a cada zona GLOBAL
    overall_counts_keeper = all_countsdf_keeper.sum(axis=0)
    all_shots_keeper=int(overall_counts_keeper.sum())
    shots_num_keeper=overall_counts_keeper.copy()
    shots_num_keeper=shots_num_keeper.drop("out", errors="ignore")
    
    overall_counts_keeper=(overall_counts_keeper/all_shots_keeper)*100
    goal_zones_keeper=overall_counts_keeper.drop("out", errors="ignore")
    out_count_keeper= overall_counts_keeper['out']
    overall_xgot_keeper = all_xGOT_df_keeper.sum(axis=0)

    xgot_zones_keeper=overall_xgot_keeper.drop("out", errors="ignore")
    
    ############ FIGURA 20 (pero en realidad 11)
    overall_goals_keeper = all_goals_df_keeper.sum(axis=0)
    all_goals_keeper=int(overall_goals_keeper.sum())
    #overall_counts=(overall_counts/all_shots)*100
    goal_scored_zones_keeper=overall_goals_keeper.drop("out", errors="ignore")
    
    
    counts=(goal_scored_zones_keeper-xgot_zones_keeper).tolist()
   

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
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
    plt.savefig(f"goles_xGOT_{specific_keeper_name}.png")
    plt.close(fig)
    
    ########## FIGURA 21 (en realidad 12)
    
    
    counts = ((goal_scored_zones_keeper / shots_num_keeper)* 100).tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
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
    plt.savefig(f"efectividad_tiros_{specific_keeper_name}.png")
    plt.close(fig)
    
    
    ############### FIGURA 11 

    counts=goal_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    ax.text((goal_left + goal_right)/2, goal_y + goal_height + 5,
            f"Fuera: {out_count_keeper:.2f}%", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de tiros a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("% de tiros en cada zona durante 2 temporadas")
    plt.savefig(f"porcentaje_tiros_{specific_keeper_name}.png")
    plt.close(fig)


    ######## FIGURA 12

    ### GOLES EN CADA ZONA 
    overall_goals_keeper = all_goals_df_keeper.sum(axis=0)
    all_goals_keeper=int(overall_goals_keeper.sum())
    #overall_counts=(overall_counts/all_shots)*100
    goal_scored_zones_keeper=overall_goals_keeper.drop("out", errors="ignore")

    counts=goal_scored_zones_keeper.tolist()

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
        
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
        
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"Número de goles en a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("Número de goles cada zona durante 2 temporadas")
    plt.savefig(f"goles_zona_{specific_keeper_name}.png")
    plt.close(fig)


    ############### FIGURA 13

    ### % de GOLES EN CADA ZONA 
    overall_goals_keeper = all_goals_df_keeper.sum(axis=0)
    all_goals_keeper=int(overall_goals_keeper.sum())
    overall_goals_keeper=(overall_goals_keeper/all_goals_keeper)*100
    goal_scored_zones_keeper=overall_goals_keeper.drop("out", errors="ignore")

    counts=goal_scored_zones_keeper.tolist()

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
        
        if count < target:
            bgcolor = 'green' # VERDE ES MEJOR QUE LA MEDIA (MENOS XG Y ASI)
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"% de goles en a cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    #st.title("% de goles en cada zona durante 2 temporadas")
    plt.savefig(f"porcentaje_goles_zona_{specific_keeper_name}.png")
    plt.close(fig)


    ########## FIGURA 14

    ### XG A CADA ZONA sumatorio de toda la temporada UNA PORTERA
    overall_xg_keeper = all_xgs_df_keeper.sum(axis=0)

    xg_zones_keeper=overall_xg_keeper.drop("out", errors="ignore")

    counts=xg_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG de toda la temporada para cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    #st.title("xG en cada zona durante 2 temporadas")
    #plt.savefig(f"xG_zona_total_{specific_keeper_name}.png")
    plt.close(fig)


    ######### FIGURA 15

    ## XG PROMEDIO GLOBAL de cada zona
    mean_xg_keeper = all_xgs_df_keeper.mean(axis=0)

    xg_mean_zones_keeper=mean_xg_keeper.drop("out", errors="ignore")

    counts=xg_mean_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG medio para cada zona por partido, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    #st.title("xG por partido en cada zona")
    #plt.savefig(f"xG_porpartido_{specific_keeper_name}.png")
    plt.close(fig)


    ######## FIGURA 16
    ####### xG por tiro en cada zona

    xg_por_tiro_keeper = all_xgs_df_keeper / all_countsdf_keeper
    xg_por_tiro_keeper = xg_por_tiro_keeper.fillna(0)

    mean_xg_shot_keeper = xg_por_tiro_keeper.mean(axis=0)

    xg_shot_zones_keeper=mean_xg_shot_keeper.drop("out", errors="ignore")

    counts=xg_shot_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xG por tiro para cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("xG por tiro en cada zona")
    #plt.savefig(f"xG_portiro_{specific_keeper_name}.png")
    plt.close(fig)


    ######### FIGURA 17

    ####### xGOT
    

    counts=xgot_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT de toda la temporada para cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    #st.title("xGOT en cada zona para 2 temporadas")
    #plt.savefig(f"xGOT_total_{specific_keeper_name}.png")
    plt.close(fig)


    ########## FIGURA 18

    ## XG PROMEDIO GLOBAL de cada zona
    mean_xgot_keeper = all_xGOT_df_keeper.mean(axis=0)

    xgot_mean_zones_keeper=mean_xgot_keeper.drop("out", errors="ignore")

    counts=xgot_mean_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT medio para cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    #st.title("xGOT por partido en cada zona")
    #plt.savefig(f"xGOT_partido_{specific_keeper_name}.png")
    plt.close(fig)


    ########## FIGURA 19

    ####### xG por tiro en cada zona

    xgot_por_tiro_keeper = all_xGOT_df_keeper / all_countsdf_keeper
    xgot_por_tiro_keeper = xgot_por_tiro_keeper.fillna(0)

    mean_xgot_shot_keeper = xgot_por_tiro_keeper.mean(axis=0)

    xgot_shot_zones_keeper=mean_xgot_shot_keeper.drop("out", errors="ignore")

    counts=xgot_shot_zones_keeper.tolist()

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
        if count < target:
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
        ax.scatter(row["end_y"], row["end_z"], c='green', s=row["xGOT_scaled"], alpha=0.7, marker='o')
    for i,row in df_goal.iterrows():
        ax.scatter(row["end_y"], row["end_z"], c='red', s=row["xGOT_scaled"], alpha=0.7, marker='o')
       
    # ax.text((goal_left + goal_right)/2, goal_y + goal_height + 20,
    #         f"xGOT por tiro para cada zona, {specific_keeper_name}", ha='center', va='bottom', fontsize=12, color='black', fontweight='bold')

    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    
    #st.title("xGOT por tiro en cada zona")
    #plt.savefig(f"xGOT_portiro_{specific_keeper_name}.png")

    plt.close(fig)
    
    output_paths=[f"porcentaje_tiros_{specific_keeper_name}.png",f"goles_xGOT_{specific_keeper_name}.png",
                  f"goles_zona_{specific_keeper_name}.png",f"efectividad_tiros_{specific_keeper_name}.png"]
    return output_paths,all_goals_keeper,unique_matches,specific_keeper_name
#graficas_path,all_goals_keeper,unique_matches=generate_graphs_gk(186022)