#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov  5 14:47:40 2025

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
from mplsoccer import Pitch,VerticalPitch
BASE_DIR="/Users/julieta/Desktop/APP_Generic_Femeni"
player_relations=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/player_relations.xlsx")
match_relations=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/match_relations.xlsx")

goalkeepers=player_relations[player_relations["position"]=="Goalkeeper"].copy()
teams_db= match_relations[["team1_name", "team1"]].drop_duplicates()

goalkeepers=pd.merge(goalkeepers,teams_db,left_on="team",right_on="team1_name",how="left")

goalkeepers_id=goalkeepers["player_id"].unique().tolist()
df_goalkeepers=pd.read_excel(f"{BASE_DIR}/goalkeepers_analisis/df_goalkeepers.xlsx")

def safe_concat(dfs, name): 
    if dfs:  # Only concatenate if the list is not empty
        return pd.concat(dfs, axis=1).T
    else:
        print(f"⚠️ No data available for {name}, creating empty DataFrame.")
        return pd.DataFrame()
    
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
for specific_keeper_id in goalkeepers_id:
    goal_matches=df_goalkeepers[df_goalkeepers["playerref"]==specific_keeper_id]
    specific_keeper_matches_teams=goal_matches[["game_id","team","year"]]
    
    all_counts=[]
    all_xgs=[]
    all_xgots=[]
    all_goals=[]
    all_shots=[]
    df_miss = pd.DataFrame()
    df_goal = pd.DataFrame()
    temporadas_jugadas=specific_keeper_matches_teams["year"].nunique()
    for match, year,team in zip(specific_keeper_matches_teams["game_id"].tolist(),specific_keeper_matches_teams["year"].tolist(),specific_keeper_matches_teams["team"].tolist()):
        df=utils_teams.parse_f70_events(f"{BASE_DIR}/datos_opta/903/{year}/f70/f70-903-{year}-{match}-expectedgoals.xml")
        cols = ['id','event_id','type_id','period_id','min','sec','player_id','team_id','outcome',
                'x','y','timestamp','timestamp_utc','last_modified',"321","322","102","103",'player_name']
        #print(df.columns)
        existing_cols = [c for c in cols if c in df.columns]

        if existing_cols:
           df = df[cols].copy()
        else:
            print("Warning: None of the expected columns exist. Returning empty DataFrame.")
            df = pd.DataFrame(columns=cols)
        df["team_id"] = df["team_id"].astype(int)
        
        df=df[df["team_id"]!=team]
       
        
        df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]]=df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]].astype(float)

        df=df.rename(columns={"321":"expected_goals","322":"expected_GOT","102":"end_y","103":"end_z"})
        df["expected_GOT"]=df["expected_GOT"].fillna(0)
        df["expected_goals"]=df["expected_goals"].fillna(0)
        df["end_z"]=df["end_z"].fillna(0)
        df["end_y"]=df["end_y"].fillna(0)
        df["year"]=year
        
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

        output_file1 = f"miss_goal_keeper_{specific_keeper_id}.xlsx"

        # Save all DataFrames to different sheets
        with pd.ExcelWriter(output_file1, engine='openpyxl') as writer:
            df_miss.to_excel(writer, sheet_name='miss', index=False)
            df_goal.to_excel(writer, sheet_name='goal', index=False)

    
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
        #output_file = f"stats_keeper_{specific_keeper_id}_{year}.xlsx"
        

        # Save all DataFrames to different sheets
        all_counts = [s for s in all_counts if s is not None and not s.empty]
        all_xgs = [s for s in all_xgs if s is not None and not s.empty]
        all_xgots = [s for s in all_xgots if s is not None and not s.empty]
        all_goals = [s for s in all_goals if s is not None and not s.empty]

        # Convert lists of Series into DataFrames
        counts_to_save = pd.DataFrame(all_counts).fillna(0)
        xgs_to_save = pd.DataFrame(all_xgs).fillna(0)
        xgots_to_save = pd.DataFrame(all_xgots).fillna(0)
        goals_to_save = pd.DataFrame(all_goals).fillna(0)


        
        # with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        #     counts_to_save.to_excel(writer, sheet_name='Counts', index=False)
        #     xgs_to_save.to_excel(writer, sheet_name='xG', index=False)
        #     xgots_to_save.to_excel(writer, sheet_name='xGOT', index=False)
        #     goals_to_save.to_excel(writer, sheet_name='Goals', index=False)

        
        all_countsdf_keeper = safe_concat(all_counts, "Counts")
        all_xgs_df_keeper = safe_concat(all_xgs, "xG")
        all_xGOT_df_keeper = safe_concat(all_xgots, "xGOT")
        all_goals_df_keeper = safe_concat(all_goals, "Goals")
    
        
    def add_year(df):
                if "year" not in df.columns:
                    df["year"] = [int(str(idx).split("-")[0]) if isinstance(idx, str) and "-" in str(idx) else None for idx in df.index]
                return df

    all_countsdf_keeper = add_year(all_countsdf_keeper)
    all_xgs_df_keeper = add_year(all_xgs_df_keeper)
    all_xGOT_df_keeper = add_year(all_xGOT_df_keeper)
    all_goals_df_keeper = add_year(all_goals_df_keeper)

    mean_counts = all_countsdf_keeper.groupby("year").mean(numeric_only=True).reset_index()
    mean_xg = all_xgs_df_keeper.groupby("year").mean(numeric_only=True).reset_index()
    mean_xgot = all_xGOT_df_keeper.groupby("year").mean(numeric_only=True).reset_index()
    mean_goals = all_goals_df_keeper.groupby("year").mean(numeric_only=True).reset_index()
    
    all_countsdf_keeper = all_countsdf_keeper.drop(columns=["year"], errors="ignore")
    all_xgs_df_keeper = all_xgs_df_keeper.drop(columns=["year"], errors="ignore")
    all_xGOT_df_keeper = all_xGOT_df_keeper.drop(columns=["year"], errors="ignore")
    all_goals_df_keeper = all_goals_df_keeper.drop(columns=["year"], errors="ignore")

    # Save global Excel (all seasons + means)
    output_file = f"stats_keeper_{specific_keeper_id}.xlsx"
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        all_countsdf_keeper.to_excel(writer, sheet_name='Counts', index=False)
        all_xgs_df_keeper.to_excel(writer, sheet_name='xG', index=False)
        all_xGOT_df_keeper.to_excel(writer, sheet_name='xGOT', index=False)
        all_goals_df_keeper.to_excel(writer, sheet_name='Goals', index=False)
        mean_counts.to_excel(writer, sheet_name='Counts_Mean_by_Season', index=False)
        mean_xg.to_excel(writer, sheet_name='xG_Mean_by_Season', index=False)
        mean_xgot.to_excel(writer, sheet_name='xGOT_Mean_by_Season', index=False)
        mean_goals.to_excel(writer, sheet_name='Goals_Mean_by_Season', index=False)
    
    



#     # Apply safe concatenation to each list
# all_countsdf_keeper = safe_concat(all_counts, "Counts")
# all_xgs_df_keeper = safe_concat(all_xgs, "xG")
# all_xGOT_df_keeper = safe_concat(all_xgots, "xGOT")
# all_goals_df_keeper = safe_concat(all_goals, "Goals")

# output_file = f"stats_keeper_{specific_keeper_id}.xlsx"

# # Save all DataFrames to different sheets
# with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
#     all_countsdf_keeper.to_excel(writer, sheet_name='Counts', index=False)
#     all_xgs_df_keeper.to_excel(writer, sheet_name='xG', index=False)
#     all_xGOT_df_keeper.to_excel(writer, sheet_name='xGOT', index=False)
#     all_goals_df_keeper.to_excel(writer, sheet_name='Goals', index=False)
        
# SAVE PER YEAR
for specific_keeper_id in goalkeepers_id:
    goal_matches=df_goalkeepers[df_goalkeepers["playerref"]==specific_keeper_id]
    specific_keeper_matches_teams=goal_matches[["game_id","team","year"]]
    
    
    df_miss = pd.DataFrame()
    df_goal = pd.DataFrame()
    
    temporadas_jugadas=specific_keeper_matches_teams["year"].nunique()
    for year in specific_keeper_matches_teams["year"].unique():
        all_counts = []
        all_xgs = []
        all_xgots = []
        all_goals = []
        all_shots = []
        for match,team in zip(specific_keeper_matches_teams["game_id"].tolist(),specific_keeper_matches_teams["team"].tolist()):
            
            df=utils_teams.parse_f70_events(f"{BASE_DIR}/datos_opta/903/{year}/f70/f70-903-{year}-{match}-expectedgoals.xml")
            cols = ['id','event_id','type_id','period_id','min','sec','player_id','team_id','outcome',
                    'x','y','timestamp','timestamp_utc','last_modified',"321","322","102","103",'player_name']
            #print(df.columns)
            existing_cols = [c for c in cols if c in df.columns]

            if existing_cols:
               df = df[cols].copy()
            else:
                print("Warning: None of the expected columns exist. Returning empty DataFrame.")
                df = pd.DataFrame(columns=cols)
            df["team_id"] = df["team_id"].astype(int)
            
            df=df[df["team_id"]!=team]
           
            
            df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]]=df[["event_id","team_id","type_id","period_id","min","sec","outcome","321","322","102","103"]].astype(float)

            df=df.rename(columns={"321":"expected_goals","322":"expected_GOT","102":"end_y","103":"end_z"})
            df["expected_GOT"]=df["expected_GOT"].fillna(0)
            df["expected_goals"]=df["expected_goals"].fillna(0)
            df["end_z"]=df["end_z"].fillna(0)
            df["end_y"]=df["end_y"].fillna(0)
            df["year"]=year
            
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

            # output_file1 = f"miss_goal_keeper_{specific_keeper_id}.xlsx"

            # # Save all DataFrames to different sheets
            # with pd.ExcelWriter(output_file1, engine='openpyxl') as writer:
            #     df_miss.to_excel(writer, sheet_name='miss', index=False)
            #     df_goal.to_excel(writer, sheet_name='goal', index=False)

        
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
    
        output_file = f"stats_keeper_{specific_keeper_id}_{year}.xlsx"
        

        # Save all DataFrames to different sheets
        all_counts = [s for s in all_counts if s is not None and not s.empty]
        all_xgs = [s for s in all_xgs if s is not None and not s.empty]
        all_xgots = [s for s in all_xgots if s is not None and not s.empty]
        all_goals = [s for s in all_goals if s is not None and not s.empty]

        # Convert lists of Series into DataFrames
        counts_to_save = pd.DataFrame(all_counts).fillna(0)
        xgs_to_save = pd.DataFrame(all_xgs).fillna(0)
        xgots_to_save = pd.DataFrame(all_xgots).fillna(0)
        goals_to_save = pd.DataFrame(all_goals).fillna(0)


        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            counts_to_save.to_excel(writer, sheet_name='Counts', index=False)
            xgs_to_save.to_excel(writer, sheet_name='xG', index=False)
            xgots_to_save.to_excel(writer, sheet_name='xGOT', index=False)
            goals_to_save.to_excel(writer, sheet_name='Goals', index=False)

        
        all_countsdf_keeper = safe_concat(all_counts, "Counts")
        all_xgs_df_keeper = safe_concat(all_xgs, "xG")
        all_xGOT_df_keeper = safe_concat(all_xgots, "xGOT")
        all_goals_df_keeper = safe_concat(all_goals, "Goals")