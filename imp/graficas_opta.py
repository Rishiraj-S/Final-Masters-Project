#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Oct 21 14:20:51 2025

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
from sklearn.preprocessing import MinMaxScaler
import utils_teams
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas

BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
#print(BASE_DIR)

pd.options.mode.chained_assignment = None  # Oculta SettingWithCopyWarning
team_analizing="Barcelona Femenino"
CHAMPIONSHIP=903
year=2024
folder_f72=f"{BASE_DIR}/data_femeni/raw/f72"
folder_f30=f"{BASE_DIR}/data_femeni/raw/f30"
folder_f70=f"{BASE_DIR}/data_femeni/raw/f70"
folder_f73=f"{BASE_DIR}/data_femeni/raw/f73"
filepath_matchrelations=f"{BASE_DIR}/data_femeni/matches_relations.xlsx"


########## esto luego se mete dentro de una función
def graficas_opta(team_analizing):
    team_names = ['Atlético de Madrid Femenino', 'Barcelona Femenino',
                  'Deportivo de La Coruña Femenino', 'Eibar Femenino',
                  'Espanyol Femenino', 'Granada Femenino', 'Levante Femenino',
                  'Real Madrid Femenino', 'Sevilla Femenino', 'UD Tenerife Femenino',
                  'Valencia Femenino','Madrid CF Femenino',"Real Betis Féminas","Levante Badalona Femenino",
                  "Athletic Club Femenino","Real Sociedad Femenino"]


    team_summary=utils_teams.get_xG_xGA_allteams(folder_f72)

    shots_df=utils_teams.get_shots_shotsA_allteams(folder_f30)

    combined_df=pd.merge(team_summary,shots_df,on="team",how="left")

    combined_df["xG_shot"]=combined_df["expected_goals"]/combined_df["Shots"]
    combined_df["xG_shot_A"]=combined_df["expected_goals_conceded"]/combined_df["Shots Conceded"]
    equipos_df, league=utils_teams.parse_teams_from_f30(folder_f30, CHAMPIONSHIP)

    equipos_df["% de duelos aereos ganados"]=(equipos_df["Aerial Duels won"]/equipos_df["Aerial Duels"])*100

    combined_df=pd.merge(equipos_df,combined_df,left_on="team_name",right_on="team",how="left")

    combined_df["% de acierto de pases"]=(combined_df["Total Successful Passes ( Excl Crosses & Corners ) "]/combined_df["Total Passes"])*100

    combined_df["Centros totales"]=combined_df["Successful Crosses open play"]+combined_df["Unsuccessful Crosses open play"]

    matches_df=pd.read_excel(filepath_matchrelations)
    df_all_matches=utils_teams.get_all_matches(team_analizing,matches_df)

    df_all_summaries=utils_teams.get_all_PPDA(folder_f73,filepath_matchrelations,team_names,2024)    
    
    all_matches_all=matches_df["matchcode"].tolist()
    ###############
    all_events_all=[]
    for match_id in all_matches_all:
        df_events,_=utils_teams.parse_f24(f"/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f24/f24-903-{year}-{match_id}-eventdetails.xml")
        all_events_all.append(df_events)
    all_events_all_teams = pd.concat(all_events_all, ignore_index=True)
    all_duels=[]
    for team in team_names:
        #print("TEAM NAME:",team)
        duelos_team_all=all_events_all_teams[(all_events_all_teams["type_id"].isin([3,4,7,44,45,54,69])) & (all_events_all_teams["team_name"]==team) & (all_events_all_teams["first_qualifier_id"].isin([285,286]))]
    

        duels_by_match_allteams = duelos_team_all.groupby("game_id").apply(utils_teams.of_def_duels).reset_index()
        duels_by_match_allteams["team_name"]=team
        duels_team=duels_by_match_allteams.groupby("team_name").sum(numeric_only=True)
        duels_team["team_name"]=team
        duels_team=duels_team[["team_name","duelos_ofensivos","duelos_defensivos"]]
        
        all_duels.append(duels_team)
    all_duels_df=pd.concat(all_duels,ignore_index=True)
    
    
    ################## duelos defensivos vs duelos ofennsivos

    all_duels_df=pd.merge(all_duels_df,combined_df[["Games Played","team_name"]],on="team_name",how="left")
    all_duels_df["duelos_ofensivos"]=all_duels_df["duelos_ofensivos"]/all_duels_df["Games Played"]
    all_duels_df["duelos_defensivos"]=all_duels_df["duelos_defensivos"]/all_duels_df["Games Played"]

    fig5,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=all_duels_df,x="duelos_defensivos",y="duelos_ofensivos",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in all_duels_df.iterrows():
        plt.text(row['duelos_defensivos'], row['duelos_ofensivos'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(all_duels_df["duelos_defensivos"])-1,max(all_duels_df["duelos_defensivos"]+1))
    plt.ylim(min(all_duels_df["duelos_ofensivos"])-1,max(all_duels_df["duelos_ofensivos"]+1))
    plt.xlabel("Duelos Defensivos",fontsize=14,fontweight="bold")
    plt.ylabel("Duelos Ofensivos",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path5="Scatter_duelos_teams.png"
    fig5.savefig(output_path5,dpi=300,bbox_inches="tight")
    plt.close(fig5)
    
    ##############

   

    ######## xG-xGA ranking
    xG_for=combined_df[["team_name","xg_difference","expected_goals","expected_goals_conceded"]]
    xG_for=xG_for.sort_values(by="xg_difference",ascending=False)

    fig1, ax = plt.subplots(figsize=(14, 10))
    plt.bar(xG_for["team_name"],xG_for["xg_difference"],color="blue",edgecolor="black")
    plt.ylim(min(0,min(xG_for["xg_difference"])-0.05),max(xG_for["xg_difference"])+0.05)
    plt.ylabel("xG-xGa",fontsize=16,fontweight='bold')
    plt.xticks(rotation=45, ha='right',fontweight='bold',fontsize=18)
    ax.axhline(0, color='black', linewidth=1.3)
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    output_path1="xG_xGa_allteams.png"
    fig1.savefig(output_path1, dpi=300, bbox_inches='tight')
    plt.close(fig1)

    ##### xG vs xGA
    fig2,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=xG_for,x="expected_goals_conceded",y="expected_goals",s=300,facecolors="none",edgecolor="black",ax=ax)
    for i, row in xG_for.iterrows():
        plt.text(row['expected_goals_conceded'], row['expected_goals'], row['team_name'], fontsize=12, alpha=0.8,zorder=2)
    min_val = min(xG_for["expected_goals_conceded"].min(), xG_for["expected_goals"].min())
    max_val = max(xG_for["expected_goals_conceded"].max(), xG_for["expected_goals"].max())
    ax.plot([min_val, max_val], [min_val, max_val], ls='--', c='gray', label="1:1 line")
    plt.xlim(min(xG_for["expected_goals_conceded"])-0.1,max(xG_for["expected_goals_conceded"]+0.1))
    plt.ylim(min(xG_for["expected_goals"])-0.1,max(xG_for["expected_goals"]+0.1))
    plt.xlabel("Goles esperados en contra (xGa)",fontsize=14,fontweight="bold")
    plt.ylabel("Goles esperados (xG)",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path2="Scatter_xG_xGa_teams.png"
    fig2.savefig(output_path2,dpi=300,bbox_inches="tight")
    plt.close(fig2)

    ########### scatter plot tiros (xG por tiro)

    Goles_por_tiro=combined_df[["team_name","expected_goals_sum","expected_goals_conceded_sum"
                                ,"Shots","Shots Conceded"]]

    Goles_por_tiro["xGa_por_tiro"]=Goles_por_tiro["expected_goals_conceded_sum"]/Goles_por_tiro["Shots Conceded"]
    Goles_por_tiro["xG_por_tiro"]=Goles_por_tiro["expected_goals_sum"]/Goles_por_tiro["Shots"]

    fig3,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Goles_por_tiro,x="xGa_por_tiro",y="xG_por_tiro",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Goles_por_tiro.iterrows():
        plt.text(row['xGa_por_tiro'], row['xG_por_tiro'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    min_val = min(Goles_por_tiro["xGa_por_tiro"].min(), Goles_por_tiro["xG_por_tiro"].min())
    max_val = max(Goles_por_tiro["xGa_por_tiro"].max(), Goles_por_tiro["xG_por_tiro"].max())
    ax.plot([min_val, max_val], [min_val, max_val], ls='--', c='gray', label="1:1 line")
    plt.xlim(min(Goles_por_tiro["xGa_por_tiro"])-0.005,max(Goles_por_tiro["xGa_por_tiro"])+0.005)
    plt.ylim(min(Goles_por_tiro["xG_por_tiro"])-0.005,max(Goles_por_tiro["xG_por_tiro"])+0.005)
    plt.xlabel("Goles esperados por tiro rival",fontsize=14,fontweight="bold")
    plt.ylabel("Goles esperados por tiro",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path3="Scatter_xG_xGa_por_tiros_teams.png"
    fig3.savefig(output_path3,dpi=300,bbox_inches="tight")
    plt.close(fig3)

    ########## METRICAS DEFENSIVAS ####################

    #### faltaría fig4 que es recuperaciones 1º tercio vs 3º tercio (sería con parse f24 de TODOS los partidos)
    #### llevaría un rato computacionalmente supongo

    Duelos_aereos=combined_df[["team_name","Aerial Duels","% de duelos aereos ganados","Games Played"]]
    Duelos_aereos["Aerial Duels"]=Duelos_aereos["Aerial Duels"]/Duelos_aereos["Games Played"]

    fig6,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Duelos_aereos,x="Aerial Duels",y="% de duelos aereos ganados",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Duelos_aereos.iterrows():
        plt.text(row['Aerial Duels'], row['% de duelos aereos ganados'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.axhline(Duelos_aereos['% de duelos aereos ganados'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_duelos_ganados = Duelos_aereos['% de duelos aereos ganados'].mean()
    plt.xlim(min(Duelos_aereos["Aerial Duels"])-1,max(Duelos_aereos["Aerial Duels"]+1))
    plt.ylim(min(Duelos_aereos["% de duelos aereos ganados"])-1,max(Duelos_aereos["% de duelos aereos ganados"]+1))
    plt.text(
        Duelos_aereos['Aerial Duels'].max()+1,  # x-coordinate (left of plot)
        mean_duelos_ganados + 0.2,             # y-coordinate slightly above the line
        f"{mean_duelos_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    plt.xlabel("Duelos aéreos",fontsize=14,fontweight="bold")
    plt.ylabel("% Duelos aéreos ganados",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path6="Scatter_duelos_aereos_teams.png"
    fig6.savefig(output_path6,dpi=300,bbox_inches="tight")
    plt.close(fig6)


    ############ Despejes vs Interceptaciones
    Despejes=combined_df[["team_name","Games Played","Interceptions","Total Clearances"]]
    Despejes["interceptaciones"]=Despejes["Interceptions"]/Despejes["Games Played"]
    Despejes["despejes"]=Despejes["Total Clearances"]/Despejes["Games Played"]

    fig7,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Despejes,x="interceptaciones",y="despejes",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Despejes.iterrows():
        plt.text(row['interceptaciones'], row['despejes'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(Despejes["interceptaciones"])-1,max(Despejes["interceptaciones"]+1))
    plt.ylim(min(Despejes["despejes"])-1,max(Despejes["despejes"]+1))
    plt.xlabel("Interceptaciones",fontsize=14,fontweight="bold")
    plt.ylabel("Despejes",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path7="Scatter_despejes_teams.png"
    fig7.savefig(output_path7,dpi=300,bbox_inches="tight")
    plt.close(fig7)

    ############ PPDA bar graph


    PPDA=df_all_summaries[["team_name","PPDA"]]
    PPDA=PPDA.sort_values(by="PPDA",ascending=False)

    fig8, ax = plt.subplots(figsize=(14, 10))
    plt.bar(PPDA["team_name"],PPDA["PPDA"],color="blue",edgecolor="black")
    plt.ylabel("PPDA",fontsize=16,fontweight='bold')
    plt.xticks(rotation=45, ha='right',fontweight='bold',fontsize=18)
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    output_path8="PPDA_allteams.png"
    fig8.savefig(output_path8, dpi=300, bbox_inches='tight')
    plt.close(fig8)

    ############## PPDA scatter
    PPDA_full=df_all_summaries[["team_name","PPDA","PPDA del Rival"]]

    fig9,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=PPDA_full,x="PPDA del Rival",y="PPDA",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in PPDA_full.iterrows():
        plt.text(row['PPDA del Rival'], row['PPDA'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    min_val = min(PPDA_full["PPDA del Rival"].min(), PPDA_full["PPDA"].min())
    max_val = max(PPDA_full["PPDA del Rival"].max(), PPDA_full["PPDA"].max())
    ax.plot([0, max_val], [0, max_val], ls='--', c='gray', label="1:1 line")
    plt.xlim(min(PPDA_full["PPDA del Rival"])-0.5,max(PPDA_full["PPDA del Rival"]+0.5))
    plt.ylim(min(PPDA_full["PPDA"])-0.5,max(PPDA_full["PPDA"]+0.5))
    plt.xlabel("PPDA del rival",fontsize=14,fontweight="bold")
    plt.ylabel("PPDA",fontsize=14,fontweight="bold")
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path9="Scatter_PPDA_teams.png"
    fig9.savefig(output_path9,dpi=300,bbox_inches="tight")
    plt.close(fig9)

    ############# tarjetas amarillas y rojas
    tarjetas=combined_df[["team_name","Games Played","Yellow Cards","Total Red Cards"]]

    tarjetas["Amarillas"]=(tarjetas["Yellow Cards"]).fillna(0)
    tarjetas["Rojas"]=(tarjetas["Total Red Cards"]).fillna(0)

    #tarjetas["Amarillas"]=(tarjetas["Yellow Cards"]/tarjetas["Games Played"]).fillna(0)
    #tarjetas["Rojas"]=(tarjetas["Total Red Cards"]/tarjetas["Games Played"]).fillna(0)


    tarjetas["Totales"]=tarjetas["Amarillas"]+tarjetas["Rojas"]
    tarjetas = tarjetas.sort_values("Totales", ascending=False)
    fig10,ax=plt.subplots(figsize=(14,10))
    plt.bar(tarjetas["team_name"],tarjetas["Rojas"],color="#C70000",edgecolor="black")
    plt.bar(tarjetas["team_name"],tarjetas["Amarillas"],bottom=tarjetas["Rojas"],color="#FFE000",edgecolor="black")
    plt.ylabel("Promedio de tarjetas",fontsize=16,fontweight='bold')
    plt.xticks(rotation=45, ha='right',fontweight='bold',fontsize=18)
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    output_path10="Tarjetas_allteams.png"
    fig10.savefig(output_path10, dpi=300, bbox_inches='tight')
    plt.close(fig10)


    ################# METRICAS DE ATAQUE ####################

    # fig 11, contraataque vs ataque posicional no puedo hacerlo

    ################ Pases totales vs % de acierto
    Pases=combined_df[["team_name","Total Passes","Passing Accuracy","Games Played"]]
    Pases["pases"]=Pases["Total Passes"]/Pases["Games Played"]

    fig12,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Pases,x="pases",y="Passing Accuracy",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Pases.iterrows():
        plt.text(row['pases'], row['Passing Accuracy'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(Pases["pases"])-1.5,max(Pases["pases"]+1.5))
    plt.ylim(min(Pases["Passing Accuracy"])-1.5,max(Pases["Passing Accuracy"]+1.5))
    plt.xlabel("Pases totales",fontsize=14,fontweight="bold")
    plt.ylabel("% de acierto en el pase",fontsize=14,fontweight="bold")
    plt.axhline(Pases['Passing Accuracy'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_duelos_ganados =Pases['Passing Accuracy'].mean()

    plt.text(
        Pases['pases'].max(),  # x-coordinate (left of plot)
        mean_duelos_ganados + 0.5,             # y-coordinate slightly above the line
        f"{mean_duelos_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path12="Scatter_pases_teams.png"
    fig12.savefig(output_path12,dpi=300,bbox_inches="tight")
    plt.close(fig12)


    ####### pases último tercio vs pases en profundidad por ahora no lo tengo

    ############# Centros totales vs centros preciosos
    Centros=combined_df[["Centros totales","Crossing Accuracy","team_name","Games Played"]]
    Centros["centros"]=Centros["Centros totales"]/Centros["Games Played"]


    fig14,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Centros,x="centros",y="Crossing Accuracy",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Centros.iterrows():
        plt.text(row['centros'], row['Crossing Accuracy'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(Centros["centros"])-1,max(Centros["centros"]+1))
    plt.ylim(min(Centros["Crossing Accuracy"])-1,max(Centros["Crossing Accuracy"]+1))
    plt.xlabel("Centros totales",fontsize=14,fontweight="bold")
    plt.ylabel("% de acierto en los centros",fontsize=14,fontweight="bold")
    plt.axhline(Centros['Crossing Accuracy'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_centros_ganados =Centros['Crossing Accuracy'].mean()

    plt.text(
        Centros['centros'].max(),  # x-coordinate (left of plot)
        mean_centros_ganados + 0.2,             # y-coordinate slightly above the line
        f"{mean_centros_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path14="Scatter_centros_teams.png"
    fig14.savefig(output_path14,dpi=300,bbox_inches="tight")
    plt.close(fig14)


    #################### ACCIONES A BALON PARADO ####################

    #   NO SEGURA SI ESTA BIEN
    ABP=combined_df[["team_name","Games Played","Attempts from Set Pieces",
                     'Corners Taken (incl short corners)', "Penalties Taken",
                     "Goal Kicks",'Throw Ins to Own Player','Throw Ins to Opposition Player']]
    ABP["total_set_pieces"]=(
        combined_df['Corners Taken (incl short corners)'] 
    )

    ABP["abp"]=ABP["total_set_pieces"]/ABP["Games Played"]
    ABP["abp_precision"]=(ABP["Attempts from Set Pieces"]/ABP["total_set_pieces"])*100

    fig15,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=ABP,x="abp",y="abp_precision",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in ABP.iterrows():
        plt.text(row['abp'], row['abp_precision'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(ABP["abp"])-0.5,max(ABP["abp"]+0.5))
    plt.ylim(min(ABP["abp_precision"])-0.5,max(ABP["abp_precision"]+0.5))
    plt.xlabel("Acciones a balón parado totales",fontsize=14,fontweight="bold")
    plt.ylabel("% de acciones a balón parado con remate",fontsize=14,fontweight="bold")
    plt.axhline(ABP['abp_precision'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_abp_ganados =ABP['abp_precision'].mean()

    plt.text(
        ABP['abp'].max(),  # x-coordinate (left of plot)
        mean_abp_ganados + 0.2,             # y-coordinate slightly above the line
        f"{mean_abp_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path15="Scatter_abp_teams.png"
    fig15.savefig(output_path15,dpi=300,bbox_inches="tight")
    plt.close(fig15)


     ############# corners totales vs rematados
    Corners=combined_df[["team_name","Games Played","Corners Taken (incl short corners)","Successful Corners into Box"]]
    Corners["corners"]=Corners["Corners Taken (incl short corners)"]/Corners["Games Played"]
    Corners["corners_precision"]=(Corners["Successful Corners into Box"]/Corners["Corners Taken (incl short corners)"])*100

    fig16,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Corners,x="corners",y="corners_precision",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Corners.iterrows():
        plt.text(row['corners'], row['corners_precision'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(Corners["corners"])-0.2,max(Corners["corners"]+0.2))
    plt.ylim(min(Corners["corners_precision"])-0.3,max(Corners["corners_precision"]+0.3))
    plt.xlabel("Córneres totales",fontsize=14,fontweight="bold")
    plt.ylabel("% de córneres rematados",fontsize=14,fontweight="bold")
    plt.axhline(Corners['corners_precision'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_corners_ganados =Corners['corners_precision'].mean()

    plt.text(
        Corners['corners'].max(),  # x-coordinate (left of plot)
        mean_corners_ganados + 0.2,             # y-coordinate slightly above the line
        f"{mean_corners_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path16="Scatter_corners_teams.png"
    fig16.savefig(output_path16,dpi=300,bbox_inches="tight")
    plt.close(fig16)

    ############### penaltis vs % de penaltis marcados

    Penaltis=combined_df[["team_name","Games Played","Penalties Taken","Penalty Goals"]]
    Penaltis["penaltis"]=Penaltis["Penalties Taken"]
    Penaltis["penaltis_aciertos"]=(Penaltis["Penalty Goals"]/Penaltis["Penalties Taken"])*100

    fig18,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Penaltis,x="penaltis",y="penaltis_aciertos",s=200,facecolors="none",edgecolor="black",ax=ax)
    for i, row in Penaltis.iterrows():
        plt.text(row['penaltis'], row['penaltis_aciertos'], row['team_name'], fontsize=10, alpha=0.8,zorder=2)
    plt.xlim(min(Penaltis["penaltis"])-0.1,max(Penaltis["penaltis"]+0.1))
    plt.ylim(min(Penaltis["penaltis_aciertos"])-0.7,max(Penaltis["penaltis_aciertos"]+0.7))
    plt.xlabel("Penaltis totales",fontsize=14,fontweight="bold")
    plt.ylabel("% de penaltis marcados",fontsize=14,fontweight="bold")
    plt.axhline(Penaltis['penaltis_aciertos'].mean(), color='red', linestyle='--', linewidth=2,zorder=1)
    mean_penaltis_ganados =Penaltis['penaltis_aciertos'].mean()

    plt.text(
        Penaltis['penaltis'].max(),  # x-coordinate (left of plot)
        mean_penaltis_ganados+0.4,             # y-coordinate slightly above the line
        f"{mean_penaltis_ganados:.2f} %",   # formatted text
        color='red',
        fontsize=10,
        fontweight='bold'
    )
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path18="Scatter_penaltis_teams.png"
    fig18.savefig(output_path18,dpi=300,bbox_inches="tight")
    plt.close(fig18)

    ######### parte del equipo particular
    matches_team=matches_df[matches_df["matchcode"].isin(df_all_matches)]

    def match_result(row):
        if row['team1_name'] == team_analizing:
            if row['team1_score'] > row['team2_score']:
                return "Win"
            elif row['team1_score'] < row['team2_score']:
                return "Lose"
            else:
                return "Draw"
        elif row['team2_name'] == team_analizing:
            if row['team2_score'] > row['team1_score']:
                return "Win"
            elif row['team2_score'] < row['team1_score']:
                return "Lose"
            else:
                return "Draw"
        else:
            return None 
    matches_team["result"]=matches_team.apply(match_result,axis=1)
    def match_home_away(row):
        if row["team1_name"]==team_analizing:
            return "Home"
        elif row["team2_name"]==team_analizing:
            return "Away"
        else:
            return None
    matches_team["place"]=matches_team.apply(match_home_away,axis=1)


    all_matches_data = [] 
    for match_id in df_all_matches:
        events_match=utils_teams.parse_f70_xg(f"{folder_f70}/f70-903-{year}-{match_id}-expectedgoals.xml",team_analizing)
        all_matches_data.append(events_match)
        
    df_all_matches_summary = pd.concat(all_matches_data, ignore_index=True)

    matches_team=pd.merge(matches_team,df_all_matches_summary,left_on="matchcode",right_on="GameID",how="left")

    all_events=[]
    for match_id in df_all_matches:
        df_events,team_names=utils_teams.parse_f24(f"{BASE_DIR}/data_femeni/raw/f24/f24-903-{year}-{match_id}-eventdetails.xml")
        all_events.append(df_events)
    all_events_df = pd.concat(all_events, ignore_index=True)
    all_events_df["type_id"]=all_events_df["type_id"].astype(int)
    recoveries=all_events_df[(all_events_df["type_id"]==49) & (all_events_df["team_name"]==team_analizing)]


    # Filter recoveries
    recoveries = all_events_df[all_events_df["type_id"] == 49]

    # Group by match and apply the function
    recoveries_by_match = recoveries.groupby("game_id").apply(utils_teams.count_zones).reset_index()

    matches_team=pd.merge(matches_team,recoveries_by_match,left_on="matchcode",right_on="game_id",how="left")

    duelos_team=all_events_df[(all_events_df["type_id"].isin([3,4,7,44,45,54,69])) & (all_events_df["team_name"]==team_analizing) & (all_events_df["first_qualifier_id"].isin([285,286]))]


    duels_by_match = duelos_team.groupby("game_id").apply(utils_teams.of_def_duels).reset_index()
    matches_team=pd.merge(matches_team,duels_by_match,left_on="matchcode",right_on="game_id",how="left")

    results_palette={
        "Win":"green",
        "Draw":"blue",
        "Lose":"red"
        }
    place_palette={
        "Home":"D",
        "Away":"o"
        }

    Orense_xG=matches_team[["expected_goals","vs.","expected_goals_conceded","result","place"]]

    fig19,ax=plt.subplots(figsize=(12,6))
    sns.scatterplot(data=Orense_xG,x="expected_goals_conceded",y="expected_goals",s=200,hue="result",style="place",
                    edgecolor="black",palette=results_palette,markers=place_palette,ax=ax)
    for i, row in Orense_xG.iterrows():
        opponent=row["vs."]
        plt.text(row["expected_goals_conceded"],row["expected_goals"],f"vs {opponent}")
    max_val = max(Orense_xG["expected_goals_conceded"].max(), Orense_xG["expected_goals"].max())
    ax.plot([0, max_val], [0, max_val], ls='--', c='gray', label="1:1 line")
    plt.xlim(min(Orense_xG["expected_goals_conceded"])-0.2,max(Orense_xG["expected_goals_conceded"]+0.2))
    plt.ylim(min(Orense_xG["expected_goals"])-0.2,max(Orense_xG["expected_goals"]+0.2))
    plt.xlabel("Goles esperados en contra (xGa)",fontsize=14,fontweight="bold")
    plt.ylabel("Goles esperados (xG)",fontsize=14,fontweight="bold")
    ax.legend_.remove()
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path19=f"Scatter_xG_{team_analizing}.png"
    fig19.savefig(output_path19,dpi=300,bbox_inches="tight")
    plt.close(fig19)

    Orense_rec=matches_team[["vs.","ultimo_tercio","primer_tercio","result","place"]]
    fig21,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Orense_rec,x="primer_tercio",y="ultimo_tercio",s=200,hue="result",style="place",
                    edgecolor="black",palette=results_palette,markers=place_palette,ax=ax)
    for i, row in Orense_rec.iterrows():
        opponent=row["vs."]
        plt.text(row["primer_tercio"],row["ultimo_tercio"],f"vs {opponent}")
    plt.xlim(min(Orense_rec["primer_tercio"])-0.5,max(Orense_rec["primer_tercio"]+0.5))
    plt.ylim(min(Orense_rec["ultimo_tercio"])-0.5,max(Orense_rec["ultimo_tercio"]+0.5))
    plt.xlabel("Balones recuperados en el primer tercio",fontsize=14,fontweight="bold")
    plt.ylabel("Balones recuperados en el último tercio",fontsize=14,fontweight="bold")
    ax.legend_.remove()
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path21=f"Scatter_recuperados_{team_analizing}.png"
    fig21.savefig(output_path21,dpi=300,bbox_inches="tight")
    plt.close(fig21)

    Orense_duelos=matches_team[["duelos_ofensivos","duelos_defensivos","vs.","result","place"]]
    fig22,ax=plt.subplots(figsize=(16,8))
    sns.scatterplot(data=Orense_duelos,x="duelos_defensivos",y="duelos_ofensivos",s=200,hue="result",style="place",
                    edgecolor="black",palette=results_palette,markers=place_palette,ax=ax)
    for i, row in Orense_duelos.iterrows():
        opponent=row["vs."]
        plt.text(row["duelos_defensivos"],row["duelos_ofensivos"],f"vs {opponent}")
    max_val = max(Orense_duelos["duelos_defensivos"].max(), Orense_duelos["duelos_ofensivos"].max())
    ax.plot([45, max_val], [40, max_val], ls='--', c='gray', label="1:1 line")
    plt.xlim(min(Orense_duelos["duelos_defensivos"])-1,max(Orense_duelos["duelos_defensivos"]+1))
    plt.ylim(min(Orense_duelos["duelos_ofensivos"])-1.5,max(Orense_duelos["duelos_ofensivos"]+1.5))
    plt.xlabel("Duelos defensivos",fontsize=14,fontweight="bold")
    plt.ylabel("Duelos ofensivos",fontsize=14,fontweight="bold")
    ax.legend_.remove()
    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(True, linestyle='--', alpha=0.5)
    output_path22=f"Scatter_duelos_{team_analizing}.png"
    fig22.savefig(output_path22,dpi=300,bbox_inches="tight")
    plt.close(fig22)
    output_paths = [
        output_path1, output_path2, output_path3,output_path5,
        output_path6, output_path7, output_path8, output_path9, output_path10,
        output_path12, output_path14, output_path15,
        output_path16, output_path18, output_path19,
        output_path21, output_path22
        ]
    return output_paths
    
#output_paths=graficas_opta("Real Sociedad Femenino")

def count_9_zones(df):
    
    x_edges = [0, 33.33, 66.66, 100]
    y_edges = [0, 33.33, 66.66, 100]

    # zone_labels = [
    #     "bottom_right", "bottom_center", "bottom_left",
    #     "middle_right", "middle_center", "middle_left",
    #     "top_left", "top_center", "top_right"
    # ]
    zone_labels = [
        0, 1, 2,
        3,4,5,
        6, 7, 8
    ]
    
   
    df['x_zone'] = pd.cut(df['x'], bins=x_edges, labels=[0, 1, 2], include_lowest=True)
    df['y_zone'] = pd.cut(df['y'], bins=y_edges, labels=[0, 1, 2], include_lowest=True)
    
    
    df['zone_index'] = df['y_zone'].astype(int) * 3 + df['x_zone'].astype(int)
    
    
    counts = df['zone_index'].value_counts().sort_index()
    
    
    counts.index = [zone_labels[i] for i in counts.index]
    
    
    return counts.reindex(zone_labels, fill_value=0)

def generate_images_events(team_analizing):
     matches_df=pd.read_excel(filepath_matchrelations)
     #### TODDO LO DE TODOS LOS EQUIPOS
     matches_all_teams=matches_df["matchcode"].tolist()
     all_events_allteams=[]
     for match_id in matches_all_teams:
         df_events,team_names=utils_teams.parse_f24(f"{BASE_DIR}/data_femeni/raw/f24/f24-903-{year}-{match_id}-eventdetails.xml")
         all_events_allteams.append(df_events)
     all_events_ALLTEAMS_df = pd.concat(all_events_allteams, ignore_index=True)
     all_events_ALLTEAMS_df["type_id"]=all_events_ALLTEAMS_df["type_id"].astype(int)

     #toddos los recoveries
     all_recoveries_df=all_events_ALLTEAMS_df[all_events_ALLTEAMS_df["type_id"]==49]
     all_recoveries_df=count_9_zones(all_recoveries_df).reset_index()
     all_recoveries_teams=int(all_recoveries_df["count"].sum())
     all_recoveries_df["count"]=(all_recoveries_df["count"]/all_recoveries_teams)*100

     #todas las faltas
     all_fouls_df=all_events_ALLTEAMS_df[(all_events_ALLTEAMS_df["type_id"]==4) &(all_events_ALLTEAMS_df["outcome"]==0) ]
     all_fouls_df=count_9_zones(all_fouls_df).reset_index()
     all_fouls_teams=int(all_fouls_df["count"].sum())
     all_fouls_df["count"]=(all_fouls_df["count"]/all_fouls_teams)*100

     #todas las perdidas
     all_loss_df=all_events_ALLTEAMS_df[(all_events_ALLTEAMS_df["type_id"]==50)]
     all_loss_df=count_9_zones(all_loss_df).reset_index()
     all_loss_teams=int(all_loss_df["count"].sum())
     all_loss_df["count"]=(all_loss_df["count"]/all_loss_teams)*100

     #todos los regates
     all_dribbles_df=all_events_ALLTEAMS_df[(all_events_ALLTEAMS_df["type_id"]==3)]

     all_dribbles_df=count_9_zones(all_dribbles_df).reset_index()

     all_dribbles_teams=int(all_dribbles_df["count"].sum())
     all_dribbles_df["count"]=(all_dribbles_df["count"]/all_dribbles_teams)*100


     ######
     df_all_matches=utils_teams.get_all_matches(team_analizing,matches_df)

     all_events=[]
     for match_id in df_all_matches:
         df_events,team_names=utils_teams.parse_f24(f"{BASE_DIR}/data_femeni/raw/f24/f24-903-{year}-{match_id}-eventdetails.xml")
         all_events.append(df_events)
     all_events_df = pd.concat(all_events, ignore_index=True)
     all_events_df["type_id"]=all_events_df["type_id"].astype(int)
     all_events_df=all_events_df[all_events_df["team_name"]==team_analizing]


     ###### RECOVERIES CAMPOGRAMA DE RECUPERACIONES
     df_recoveries=all_events_df[all_events_df["type_id"]==49]


     df_recoveries=count_9_zones(df_recoveries).reset_index()
     all_recoveries=int(df_recoveries["count"].sum())
     df_recoveries["count"]=(df_recoveries["count"]/all_recoveries)*100
     counts=df_recoveries["count"].tolist()

     from mplsoccer import Pitch
     x_centers = [16.66, 50, 83.33]
     y_centers = [83.33, 50, 16.66]

     # Calculate coordinates of the dividing lines (midpoints between centers)
     x_lines = [(x_centers[i] + x_centers[i+1]) / 2 for i in range(2)]  # vertical delimiters
     y_lines = [(y_centers[i] + y_centers[i+1]) / 2 for i in range(2)]  # horizontal delimiters

     # Coordinates for text placement
     zone_coords = {}
     for zone_index in range(9):
         row = zone_index // 3
         col = zone_index % 3
         row = 2 - row  # vertical flip
         x = x_centers[col]
         y = y_centers[row]
         zone_coords[zone_index] = (x, y)

     # Example counts
     pitch = Pitch(pitch_type='opta', pitch_color='green', line_color='white')
     fig1, ax = pitch.draw(figsize=(8, 6))

     # Determine zone boundaries for rectangles
     x_boundaries = [0] + x_lines + [100]
     y_boundaries = [0] + y_lines + [100]

     # Plot zones with background color
     for zone_index, count in enumerate(counts):
         row = zone_index // 3
         col = zone_index % 3
         row = 2 - row  # vertical flip

         x0 = x_boundaries[col]
         x1 = x_boundaries[col + 1]
         y0 = y_boundaries[row]
         y1 = y_boundaries[row + 1]

         # Compare with target
         target = all_recoveries_df.loc[zone_index, 'count']
         if count > target:
             bgcolor = 'blue'
         else:
             bgcolor = 'red'

         # Draw rectangle behind text
         ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.3)

         # Draw text
         x, y = zone_coords[zone_index]
         ax.text(x, y, f"{count:.1f}%", ha='center', va='center', fontsize=30,
                 color='white', fontweight='bold')

     # Add vertical delimiting lines
     for x in x_lines:
         ax.axvline(x=x, color='white', linestyle='--', linewidth=2)

     # Add horizontal delimiting lines
     for y in y_lines:
         ax.axhline(y=y, color='white', linestyle='--', linewidth=2)

     output_path1=f"Campograma_recuperaciones_{team_analizing}.png"
     fig1.savefig(output_path1,dpi=300,bbox_inches="tight")
     plt.close(fig1)


     ######### FALTAS COMETIDAS CAMPOGRAMA DE FALTAS

     df_fouls=all_events_df[(all_events_df["type_id"]==4) &(all_events_df["outcome"]==0) ]
     df_fouls=count_9_zones(df_fouls).reset_index()
     all_fouls=int(df_fouls["count"].sum())
     df_fouls["count"]=(df_fouls["count"]/all_fouls)*100
     counts=df_fouls["count"].tolist()

     pitch = Pitch(pitch_type='opta', pitch_color='green', line_color='white')
     fig2, ax = pitch.draw(figsize=(8, 6))

     # Determine zone boundaries for rectangles
     x_boundaries = [0] + x_lines + [100]
     y_boundaries = [0] + y_lines + [100]

     for zone_index, count in enumerate(counts):
         row = zone_index // 3
         col = zone_index % 3
         row = 2 - row  # vertical flip

         x0 = x_boundaries[col]
         x1 = x_boundaries[col + 1]
         y0 = y_boundaries[row]
         y1 = y_boundaries[row + 1]

         # Compare with target
         target = all_fouls_df.loc[zone_index, 'count']
         if count > target:
             bgcolor = 'blue'
         else:
             bgcolor = 'red'

         # Draw rectangle behind text
         ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.3)

         # Draw text
         x, y = zone_coords[zone_index]
         ax.text(x, y, f"{count:.1f}%", ha='center', va='center', fontsize=30,
                 color='white', fontweight='bold')

     # Add vertical delimiting lines
     for x in x_lines:
         ax.axvline(x=x, color='white', linestyle='--', linewidth=2)

     # Add horizontal delimiting lines
     for y in y_lines:
         ax.axhline(y=y, color='white', linestyle='--', linewidth=2)

     output_path2=f"Campograma_faltas_{team_analizing}.png"
     fig2.savefig(output_path2,dpi=300,bbox_inches="tight")
     plt.close(fig2)

     ########### perdidas de balon

     df_loss=all_events_df[(all_events_df["type_id"]==50)]
     df_loss=count_9_zones(df_loss).reset_index()
     all_loss=int(df_loss["count"].sum())
     df_loss["count"]=(df_loss["count"]/all_loss)*100
     counts=df_loss["count"].tolist()

     pitch = Pitch(pitch_type='opta', pitch_color='green', line_color='white')
     fig3, ax = pitch.draw(figsize=(8, 6))

     # Determine zone boundaries for rectangles
     x_boundaries = [0] + x_lines + [100]
     y_boundaries = [0] + y_lines + [100]

     for zone_index, count in enumerate(counts):
         row = zone_index // 3
         col = zone_index % 3
         row = 2 - row  # vertical flip

         x0 = x_boundaries[col]
         x1 = x_boundaries[col + 1]
         y0 = y_boundaries[row]
         y1 = y_boundaries[row + 1]

         # Compare with target
         target = all_loss_df.loc[zone_index, 'count']
         if count > target:
             bgcolor = 'blue'
         else:
             bgcolor = 'red'

         # Draw rectangle behind text
         ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.3)

         # Draw text
         x, y = zone_coords[zone_index]
         ax.text(x, y, f"{count:.1f}%", ha='center', va='center', fontsize=30,
                 color='white', fontweight='bold')

     # Add vertical delimiting lines
     for x in x_lines:
         ax.axvline(x=x, color='white', linestyle='--', linewidth=2)

     # Add horizontal delimiting lines
     for y in y_lines:
         ax.axhline(y=y, color='white', linestyle='--', linewidth=2)

     output_path3=f"Campograma_perdidas_{team_analizing}.png"
     fig3.savefig(output_path3,dpi=300,bbox_inches="tight")
     plt.close(fig3)

     ################ REGATES

     df_dribbles=all_events_df[(all_events_df["type_id"]==3)]
     suc_dribbles=df_dribbles[df_dribbles["outcome"]==1]
     failed_dribbles=df_dribbles[df_dribbles["outcome"]==0]

     df_dribbles=count_9_zones(df_dribbles).reset_index()
     suc_dribbles=count_9_zones(suc_dribbles).reset_index()
     failed_dribbles=count_9_zones(failed_dribbles).reset_index()

     all_dribbles=int(df_dribbles["count"].sum())
     all_succ=int(suc_dribbles["count"].sum())
     all_fail=int(failed_dribbles["count"].sum())
     suc_dribbles["count"]=(suc_dribbles["count"]/df_dribbles["count"])*100
     failed_dribbles["count"]=(failed_dribbles["count"]/df_dribbles["count"])*100

     df_dribbles["count"]=(df_dribbles["count"]/all_dribbles)*100

     counts=df_dribbles["count"].tolist()
     counts_succ=suc_dribbles["count"].tolist()
     counts_fail=failed_dribbles["count"].tolist()

     pitch = Pitch(pitch_type='opta', pitch_color='green', line_color='white')
     fig4, ax = pitch.draw(figsize=(8, 6))

     x_offset = 15  # horizontal offset
     y_offset = 12    # vertical offset


     for zone_index, (count, succ, fail) in enumerate(zip(counts, counts_succ, counts_fail)):
         row = zone_index // 3
         col = zone_index % 3
         row = 2 - row  # vertical flip

         x0 = x_boundaries[col]
         x1 = x_boundaries[col + 1]
         y0 = y_boundaries[row]
         y1 = y_boundaries[row + 1]

         # Compare with target
         target = all_loss_df.loc[zone_index, 'count']
         if count > target:
             bgcolor = 'blue'
         else:
             bgcolor = 'red'

         # Draw rectangle behind text
         ax.fill_betweenx([y0, y1], x0, x1, color=bgcolor, alpha=0.3)

         # Draw text
         x, y = zone_coords[zone_index]
         ax.text(x, y, f"{count:.1f}%", ha='center', va='center', fontsize=30,
                 color='white', fontweight='bold')
         # Bottom-left text
         ax.text(x - x_offset, y - y_offset, f"{succ:.1f}", ha='left', va='bottom', fontsize=14, color='blue')
         
         # Bottom-right text
         ax.text(x + x_offset, y - y_offset, f"{fail:.1f}", ha='right', va='bottom', fontsize=14, color='red')


     # Add vertical delimiting lines
     for x in x_lines:
         ax.axvline(x=x, color='white', linestyle='--', linewidth=2)

     # Add horizontal delimiting lines
     for y in y_lines:
         ax.axhline(y=y, color='white', linestyle='--', linewidth=2)

     output_path4=f"Campograma_regates_{team_analizing}.png"
     fig4.savefig(output_path4,dpi=300,bbox_inches="tight")
     plt.close(fig4)
     all_shots=[]
     first_match = matches_df[matches_df["matchcode"] == df_all_matches[0]]
     if first_match["team1_name"].iloc[0]==team_analizing:
         team_id=first_match["team1"].iloc[0]
     else:
         team_id=first_match["team2"].iloc[0]
     last_5_matches=df_all_matches[-5:]
    
     for match_id in last_5_matches:
         events = utils_teams.parse_f70_events(f"{folder_f70}/f70-903-{year}-{match_id}-expectedgoals.xml")
         
         events=events[events["team_id"]==str(team_id)]
         
         all_shots.append(events)
        
     all_shots_df = pd.concat(all_shots, ignore_index=True)
     
     shot_events = all_shots_df[all_shots_df['type_id'].isin(['13', '14', '15', '16'])]
     shot_events["type_id"] = shot_events["type_id"].astype(int)
     shot_events["321"] = shot_events["321"].astype(float)

     shot_events["end_location_x"] = 100
     shot_events["end_location_y"] = shot_events["102"].astype(float)
     shot_events["end_location_z"] = shot_events["103"].astype(float)
     
     
     shot_events['outcome_name'] = np.where(shot_events['type_id'] == 16, 'Goal', 'Miss')
     
     fig5, ax =  plt.subplots(figsize=(8, 4))
     goals = shot_events[shot_events["outcome_name"] == "Goal"]
     scaler=MinMaxScaler(feature_range=(50, 200))
     values = goals["321"].values.reshape(-1, 1)
     goals["321"] = scaler.fit_transform(values)
     
     
     miss = shot_events[shot_events["outcome_name"] != "Goal"]
     values = miss["321"].values.reshape(-1, 1)
     miss["321"] = scaler.fit_transform(values)

     ax.set_xlim(35, 65)
     ax.set_ylim(0, 90)

     # Goal coordinates
     goal_y = 0
     goal_height = 40
     goal_left = 44.2
     goal_right = 55.8

     # Draw goal posts
     ax.plot([goal_left, goal_left], [goal_y, goal_y + goal_height], color='black', linewidth=2)
     ax.plot([goal_right, goal_right], [goal_y, goal_y + goal_height], color='black', linewidth=2)
     ax.plot([goal_left, goal_right], [goal_y + goal_height, goal_y + goal_height], color='black', linewidth=2)

     # Scatter goals and misses
     ax.scatter(goals.end_location_y, goals.end_location_z,
                s=goals["321"], c='green', edgecolors='black', marker='o', label="Goal", alpha=0.6)
     ax.scatter(miss.end_location_y, miss.end_location_z,
                s=miss["321"], c='blue', edgecolors='black', marker='o', label="Miss", alpha=0.6)

     # Remove ticks and spines
     ax.set_xticks([])
     ax.set_yticks([])
     ax.spines['top'].set_visible(False)
     ax.spines['right'].set_visible(False)
     ax.spines['left'].set_visible(False)
     


     output_path5=f"xG_porteria_{team_analizing}.png"
     plt.tight_layout()
     fig5.savefig(output_path5, dpi=300, bbox_inches='tight')
     plt.tight_layout()
     #plt.show()
     plt.close()
     
     mask = shot_events["team_id"] == (team_id)
     shot_events.loc[mask, "x"] = 100 - shot_events.loc[mask, "x"]
     shot_events.loc[mask, "y"] = 100 - shot_events.loc[mask, "y"]

     scaler = MinMaxScaler(feature_range=(100, 500))  # tamaño mínimo 50, máximo 300
     shot_events["321"] = scaler.fit_transform(shot_events[["321"]])

     df_miss=shot_events[shot_events["type_id"]==13]
     df_post=shot_events[shot_events["type_id"]==14]
     df_blocked=shot_events[shot_events["type_id"]==15]
     df_goals=shot_events[shot_events["type_id"]==16]



     pitch = Pitch(pitch_type="opta",pad_bottom=0.5, goal_type='box', goal_alpha=0.8)  
     fig6, ax = pitch.draw(figsize=(12, 10))  

     pitch.scatter(df_miss.x, df_miss.y,  
                   s=df_miss["321"], c='red', edgecolors='black', marker='o', ax=ax, label="Fuera",alpha=0.6)
     pitch.scatter(df_post.x, df_post.y,  
                   s=df_post["321"], c='orange', edgecolors='black', marker='o', ax=ax, label="Palo",alpha=0.6)
     pitch.scatter(df_blocked.x, df_blocked.y,  
                   s=df_blocked["321"], c='yellow', edgecolors='black', marker='o', ax=ax, label="Bloqueado",alpha=0.6)
     pitch.scatter(df_goals.x, df_goals.y,  
                   s=df_goals["321"], c='green', edgecolors='black', marker='*', ax=ax, label="Gol",alpha=0.6)

     ax.legend(loc="upper right", fontsize=12)

     ax.legend(loc="lower right")

     output_path6 = f"ShotMap_{team_analizing}.png"
     
     canvas5 = FigureCanvas(fig5)
     canvas6 = FigureCanvas(fig6)
     canvas5.draw()
     canvas6.draw()
     # Convert them to RGBA arrays
     img5 = np.array(canvas5.buffer_rgba())
     img6 = np.array(canvas6.buffer_rgba())

     # Use PIL to combine them horizontally
     from PIL import Image

     im1 = Image.fromarray(img5)
     im2 = Image.fromarray(img6)

     width1, height1 = im1.size
     width2, height2 = im2.size

     combined_img = Image.new("RGBA", (max(width1, width2), height1 + height2))
     combined_img.paste(im1, (0, 0))
     combined_img.paste(im2, (0, height1))

        # Save or show
     combined_output=f"combined_tiros_{team_analizing}.png"
     combined_img.save(combined_output)
     
     fig6.savefig(output_path6, dpi=300, bbox_inches='tight')
     output_paths=[output_path1, output_path2, output_path3,
                   output_path4, output_path5, combined_output]
     return output_paths



#generate_images_events("Barcelona Femenino")
######



