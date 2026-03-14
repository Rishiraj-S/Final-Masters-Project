#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep  8 10:49:08 2025

@author: julieta
"""

import streamlit as st
from utils import login
from utils import util
import pandas as pd
import subprocess
import os
import time
from datetime import datetime
from streamlit_autorefresh import st_autorefresh
import sys
import traceback
import requests
import json
import glob
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go

def show_page():

        
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    ruta_script = os.path.join(BASE_DIR, "report_gen_teams", "Report_Equipo.py")
    Report = "Report_2RFEF_FINAL.py"
    directorio_logs=os.path.join(BASE_DIR,"logs")
    ruta_parameters=os.path.join(BASE_DIR,"report_gen","parameters.xlsx")
    ruta_script_pizza=os.path.join(BASE_DIR,"report_gen","PizzaWyscout.py")
    ruta_excel=os.path.join(BASE_DIR,"data","2RFEF_wyscout_2024.xlsx")
    ruta_excel2=os.path.join(BASE_DIR,"data")
    script_report_team=os.path.join(BASE_DIR,"report_gen_teams","Report_Equipo.py")
    folder_equipos=os.path.join(BASE_DIR,"report_gen_teams","datos_equipos")
    ruta_excel_equipos=os.path.join(BASE_DIR,"report_gen_teams","datos_equipos")
    ruta_excel_equipos_excel=os.path.join(BASE_DIR,"data","Equipos_LigaF.xlsx")
    ruta_reports_wyscout=os.path.join(BASE_DIR,"report_gen_teams","wyscout_report")
    Report_equipos="Report_Equipo.py"
    directorio_base = os.path.dirname(ruta_script)

    directorio_equipos=os.path.join(BASE_DIR,"report_gen_teams","datos_equipos")

    # Asegura existencia de la carpeta de logs
    os.makedirs(directorio_logs, exist_ok=True)

    # teams = {
    #     'Alhama': pd.read_excel(f"{directorio_equipos}/Team Stats Alhama.xlsx",decimal=','),
    #     'Athletic Club': pd.read_excel(f"{directorio_equipos}/Team Stats Athletic Club.xlsx",decimal=','),
    #     'Atletico Madrid Feminino': pd.read_excel(f"{directorio_equipos}/Team Stats Atletico Madrid Feminino.xlsx",decimal=','),
    #     'Badalona': pd.read_excel(f"{directorio_equipos}/Team Stats Badalona.xlsx",decimal=','),
    #     'Barcelona': pd.read_excel(f"{directorio_equipos}/Team Stats Barcelona.xlsx",decimal=','),
    #     'Deportivo de La Coruña': pd.read_excel(f"{directorio_equipos}/Team Stats Deportivo de La Coruña.xlsx",decimal=','),
    #     'Eibar': pd.read_excel(f"{directorio_equipos}/Team Stats Eibar.xlsx",decimal=','),
    #     'Espanyol': pd.read_excel(f"{directorio_equipos}/Team Stats Espanyol.xlsx",decimal=','),
    #     'Granada': pd.read_excel(f"{directorio_equipos}/Team Stats Granada.xlsx",decimal=','),
    #     'Levante': pd.read_excel(f"{directorio_equipos}/Team Stats Levante.xlsx",decimal=','),
    #     'Logroño': pd.read_excel(f"{directorio_equipos}/Team Stats Logroño.xlsx",decimal=','),
    #     'Madrid CFF': pd.read_excel(f"{directorio_equipos}/Team Stats Madrid CFF.xlsx",decimal=','),
    #     'Real Madrid': pd.read_excel(f"{directorio_equipos}/Team Stats Real Madrid.xlsx",decimal=','),
    #     'Real Sociedad': pd.read_excel(f"{directorio_equipos}/Team Stats Real Sociedad.xlsx",decimal=','),
    #     'Sevilla': pd.read_excel(f"{directorio_equipos}/Team Stats Sevilla.xlsx",decimal=','),
    #     'UDG Tenerife': pd.read_excel(f"{directorio_equipos}/Team Stats UDG Tenerife.xlsx",decimal=',')
    #     }
    teams=util.load_team_stats(directorio_equipos)
   
    #@st.fragment
    def filtros_fragment():

        # Ajustes básicos
        st.markdown(":material/settings: Ajustes básicos")
        

        col1, col2, col3 = st.columns([1.8, 1, 1.5])

        with col1:
            team = None
            df2=util.leer_excel_grupo(ruta_excel_equipos_excel)
            if df2 is not None:
                lista_equipos = util.obtener_lista_equipos(df2, "Equipos")
                team = st.selectbox("Equipo:", lista_equipos,placeholder="Escribe el nombre del equipo...",)
                #team_clean=util.teams_mapping(team)
            else:
                team="Barcelona"
                #team_clean=util.teams_mapping(team)

        return {
            "ruta_script": ruta_script,
            "team_analizing": team,
            "team_og":team,
            "folder_path":ruta_excel_equipos
            }

    filtros = filtros_fragment()
    TEAM=str(filtros["team_analizing"])
    @st.cache_data
    def process_teams(teams):
        for team, df in teams.items():
            df["Equipo"] = df["Equipo"].str.rstrip()
            team_avg = df[df["Equipo"] == team].mean(numeric_only=True)
            adversarios_avg = df[df["Equipo"] != team].mean(numeric_only=True)
            df.loc[df["Fecha"] == team, team_avg.index] = team_avg.values
            df.loc[df["Fecha"] == "Adversarios", adversarios_avg.index] = adversarios_avg.values
            teams[team] = df
        return teams

    teams = process_teams(teams)

     ################ Ahora individual del equipo que estamos analizando
    results_palette = {
        1: "green",
        0: "blue",
        -1: "red"
        }

    place_palette = {
        "Home": "diamond",
        "Away": "circle"
    }

    Orense = teams[TEAM]
    # Me cargo las medias de team y adversario
    Orense = Orense[2:]

    Orense[["Equipos", "Score"]] = Orense['Partido'].str.extract(r'(.+?)\s+(\d+:\d+)', expand=True)
    Orense[["Home", "Away"]] = Orense["Equipos"].str.split(" - ", expand=True)
    Orense[['goles_home', 'goles_away']] = Orense['Score'].str.split(':', expand=True).astype(int)

    Orense["Result"] = Orense.apply(
        lambda row: "Home" if row["goles_home"] > row["goles_away"]
        else "Away" if row["goles_away"] > row["goles_home"]
        else "Draw",
        axis=1
    )

    Orense.drop(["Equipos", "Score", "goles_home", "goles_away"], axis=1, inplace=True)

    # --- xG vs xGa ---
    xGa = Orense[Orense["Equipo"] == TEAM]["xG"]
    xG = Orense[Orense["Equipo"] != TEAM]["xG"]

    Orense_xG=Orense[["Fecha","xG","Home","Away","Result"]].copy()
    Orense_xG['match_id'] = Orense_xG['Home'] + ' vs ' + Orense_xG['Away'] + " - " + Orense_xG["Fecha"]
    Orense_xG.drop(["Fecha"], axis=1, inplace=True)
    
    def get_xga(group):
        if TEAM not in group['Home'].values and TEAM not in group['Away'].values:
            return group.assign(xGa=None)
        else:
            xg_values = group['xG'].values
            return group.assign(xGa=[xg_values[1], xg_values[0]])

    Orense_xG = Orense_xG.groupby('match_id', group_keys=False).apply(get_xga)
    Orense_xG = Orense_xG[Orense_xG.index % 2 == 0].copy()

    Orense_xG["Result"] = Orense_xG.apply(
        lambda x: x["Home"] if x["Result"] == "Home"
        else x["Away"] if x["Result"] == "Away"
        else "Draw",
        axis=1
    )

    Orense_xG["Result"] = Orense_xG.apply(
        lambda x: 1 if x["Result"] == TEAM
        else 0 if x["Result"] == "Draw"
        else -1,
        axis=1
    )
    Orense_xG["Result"] = Orense_xG["Result"].astype("category")
    Orense_xG["Opponent"] = Orense_xG.apply(lambda x: x["Home"] if x["Away"] == TEAM else x["Away"], axis=1)
    Orense_xG["Place"] = Orense_xG.apply(lambda x: "Home" if x["Home"] == TEAM else "Away", axis=1)
    

    fig19 = px.scatter(
        Orense_xG,
        x="xGa",
        y="xG",
        color="Result",
        symbol="Place",
        color_discrete_map=results_palette,
        symbol_map=place_palette,   # aquí mapeamos a nombres válidos
        text="Opponent",
        hover_data={
            "xGa": ":.2f",
            "xG": ":.2f",
            "Opponent": True,
            "Result": True,
            "Place": True
    },
    title=f"Goles esperados vs Goles esperados en contra ({TEAM})",
    )
    result_labels = {1: "Victoria", 0: "Empate", -1: "Derrota"}
    place_labels = {"Home": "Local", "Away": "Visitante"}  # Map symbol values to readable names

    for trace in fig19.data:
        parts = [p.strip() for p in trace.name.split(',')]
    
        # Map the result (color)
        try:
            color_key = int(parts[0])
            color_label = result_labels.get(color_key, parts[0])
        except ValueError:
            color_label = parts[0]
    
        # Map the place (symbol)
        symbol_label = place_labels.get(parts[1], parts[1]) if len(parts) > 1 else ""
    
        # Combine them for the legend
        trace.name = f"{color_label} ({symbol_label})"



    # --- Add labels "vs Opponent" above points ---
    fig19.update_traces(
        textposition="top center",
        marker=dict(size=12, line=dict(width=2, color="black"))
    )


    # --- Add 1:1 reference line ---
    max_val = max(Orense_xG["xGa"].max(), Orense_xG["xG"].max())
    fig19.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            line=dict(color="gray", dash="dash"),
            showlegend=False,
            name="1:1 line"
        )
    )


    # --- Layout adjustments ---
    fig19.update_layout(
        xaxis_title="Goles esperados en contra (xGa)",
        yaxis_title="Goles esperados (xG)",
        template="plotly_white",
        hovermode="closest",
        height=700,
        width=1000,
        xaxis=dict(range=[Orense_xG["xGa"].min() - 0.2, Orense_xG["xGa"].max() + 0.2]),
        yaxis=dict(range=[Orense_xG["xG"].min() - 0.2, Orense_xG["xG"].max() + 0.2]),
    )


    #fig19.savefig(output_path19, dpi=300, bbox_inches="tight")
    # plt.show()
     #plt.show()
     
     
    ################ PPDA vs PPDA del rival

    Orense_PPDA=Orense[["Fecha","PPDA","Home","Away","Result"]].copy()

    Orense_PPDA['match_id'] = Orense_PPDA['Home'] + ' vs ' + Orense_PPDA['Away']+ " - " + Orense_PPDA["Fecha"]
    Orense_PPDA.drop(["Fecha"], axis=1, inplace=True)    

    def get_ppdaa(group):
        if TEAM not in group['Home'].values and TEAM not in group['Away'].values:
            return group.assign(PPDA_a=None)
        else:
            ppda_values=group['PPDA'].values
            return group.assign(PPDA_a=[ppda_values[1], ppda_values[0]])

    Orense_PPDA=Orense_PPDA.groupby('match_id', group_keys=False).apply(get_ppdaa)

    Orense_PPDA=Orense_PPDA[Orense_PPDA.index%2==0].copy()

    Orense_PPDA["Result"] = Orense_PPDA.apply(
        lambda x: x["Home"] if x["Result"] == "Home"
        else x["Away"] if x["Result"] == "Away"
        else "Draw",
        axis=1
    )
    Orense_PPDA["Result"]=Orense_PPDA.apply(lambda x: 1 if x["Result"]==TEAM
                                        else 0 if x["Result"]=="Draw"
                                        else -1,axis=1)
    Orense_PPDA["Opponent"]=Orense_PPDA.apply(lambda x: x["Home"] if x["Away"]==TEAM
                                          else x["Away"],axis=1)
    Orense_PPDA["Place"] = Orense_PPDA.apply(lambda x: "Home" if x["Home"] == TEAM else "Away", axis=1)
    Orense_PPDA["Result"] = Orense_PPDA["Result"].astype("category")
    fig20 = px.scatter(
        Orense_PPDA,
        x="PPDA_a",
        y="PPDA",
        color="Result",
        symbol="Place",
        color_discrete_map=results_palette,
        symbol_map=place_palette,   # usa símbolos válidos
        text="Opponent",
        hover_data={
            "PPDA_a": ":.2f",
            "PPDA": ":.2f",
            "Opponent": True,
            "Result": True,
            "Place": True
    },
    title=f"PPDA vs PPDA del rival ({TEAM})",
    )
    result_labels = {1: "Victoria", 0: "Empate", -1: "Derrota"}
    place_labels = {"Home": "Local", "Away": "Visitante"}  # Map symbol values to readable names

    for trace in fig20.data:
        parts = [p.strip() for p in trace.name.split(',')]
    
        # Map the result (color)
        try:
            color_key = int(parts[0])
            color_label = result_labels.get(color_key, parts[0])
        except ValueError:
            color_label = parts[0]
    
        # Map the place (symbol)
        symbol_label = place_labels.get(parts[1], parts[1]) if len(parts) > 1 else ""
    
        # Combine them for the legend
        trace.name = f"{color_label} ({symbol_label})"

    # --- Add labels "vs Opponent" above points ---
    fig20.update_traces(
        textposition="top center",
        marker=dict(size=12, line=dict(width=2, color="black"))
    )


    # --- Add 1:1 reference line ---
    max_val = max(Orense_PPDA["PPDA_a"].max(), Orense_PPDA["PPDA"].max())
    fig20.add_trace(
        go.Scatter(
            x=[0, max_val],
            y=[0, max_val],
            mode="lines",
            line=dict(color="gray", dash="dash"),
            showlegend=False,
            name="1:1 line"
        )
    )


    # --- Layout adjustments ---
    fig20.update_layout(
        xaxis_title="PPDA del rival",
        yaxis_title="PPDA",
        template="plotly_white",
        hovermode="closest",
        height=700,
        width=1000,
        xaxis=dict(range=[Orense_PPDA["PPDA_a"].min() - 0.2, Orense_PPDA["PPDA_a"].max() + 0.2]),
        yaxis=dict(range=[Orense_PPDA["PPDA"].min() - 0.4, Orense_PPDA["PPDA"].max() + 0.4]),
    )
    ############## Recuperaciones en el 1 tercio vs ultimo tercio
    Orense_rec=Orense[["Fecha","Unnamed: 20","Unnamed: 22","Home","Away","Result"]].copy()
    
    Orense_rec.rename(columns={'Unnamed: 20': 'primer_tercio','Unnamed: 22': 'ultimo_tercio'}, inplace=True)

    Orense_rec['match_id'] = Orense_rec['Home'] + ' vs ' + Orense_rec['Away'] + " - " + Orense_rec["Fecha"]
    Orense_rec.drop(["Fecha"], axis=1, inplace=True)  
    
    def get_rec_a(group):
        if TEAM not in group['Home'].values and TEAM not in group['Away'].values:
            return group.assign(primer_tercio_a=None,ultimo_tercio_a=None)
        else:
            primer_tercio_values=group['primer_tercio'].values
            ultimo_tercio_values=group["ultimo_tercio"].values
            return group.assign(
                primer_tercio_a=[primer_tercio_values[1], primer_tercio_values[0]],
                ultimo_tercio_a=[ultimo_tercio_values[1], ultimo_tercio_values[0]]
            )

    Orense_rec=Orense_rec.groupby("match_id",group_keys=False).apply(get_rec_a)

    Orense_rec=Orense_rec[Orense_rec.index%2==0].copy()

    Orense_rec["Result"] = Orense_rec.apply(
        lambda x: x["Home"] if x["Result"] == "Home"
        else x["Away"] if x["Result"] == "Away"
        else "Draw",
        axis=1
    )
    Orense_rec["Result"]=Orense_rec.apply(lambda x: 1 if x["Result"]==TEAM
                                        else 0 if x["Result"]=="Draw"
                                        else -1,axis=1)
    Orense_rec["Opponent"]=Orense_rec.apply(lambda x: x["Home"] if x["Away"]==TEAM
                                          else x["Away"],axis=1)
    Orense_rec["Place"]=Orense_rec.apply(lambda x: "Home" if x["Home"]==TEAM
                                       else "Away",axis=1)
    Orense_rec["Result"] = Orense_rec["Result"].astype("category")

    fig21 = px.scatter(
        Orense_rec,
        x="primer_tercio",
        y="ultimo_tercio",
        color="Result",          # maps to hue in Seaborn
        symbol="Place",          # maps to style in Seaborn
        color_discrete_map=results_palette,
        symbol_map=place_palette,
        text="Opponent",         # opponent names as hover text
        hover_data={
            "primer_tercio": ":.2f",
            "ultimo_tercio": ":.2f",
            "Opponent": True,
            "Result": True,
            "Place": True
        },
        title=f"Balones recuperados ({TEAM})",
    )
    result_labels = {1: "Victoria", 0: "Empate", -1: "Derrota"}
    place_labels = {"Home": "Local", "Away": "Visitante"}  # Map symbol values to readable names

    for trace in fig21.data:
        parts = [p.strip() for p in trace.name.split(',')]
    
        # Map the result (color)
        try:
            color_key = int(parts[0])
            color_label = result_labels.get(color_key, parts[0])
        except ValueError:
            color_label = parts[0]
    
        # Map the place (symbol)
        symbol_label = place_labels.get(parts[1], parts[1]) if len(parts) > 1 else ""
    
        # Combine them for the legend
        trace.name = f"{color_label} ({symbol_label})"


    # --- Add labels "vs Opponent" above points ---
    fig21.update_traces(
        textposition="top center",
        marker=dict(size=12, line=dict(width=2, color="black"))
    )


    # --- Layout adjustments ---
    fig21.update_layout(
        xaxis_title="Balones recuperados en el primer tercio",
        yaxis_title="Balones recuperados en el último tercio",
        template="plotly_white",
        hovermode="closest",
        height=700,
        width=1000,
        xaxis=dict(range=[Orense_rec["primer_tercio"].min() - 0.5, Orense_rec["primer_tercio"].max() + 0.5]),
        yaxis=dict(range=[Orense_rec["ultimo_tercio"].min() - 0.5, Orense_rec["ultimo_tercio"].max() + 0.5]),
    )
    #fig21.savefig(output_path21,dpi=300,bbox_inches="tight")
    #plt.show()

    ################### Duelos ofensivos vs Defensivos

    Orense_duelos=Orense[["Fecha","Duelos defensivos / ganados","Duelos ofensivos / ganados","Home","Away","Result"]].copy()
    Orense_duelos.rename(columns={"Duelos defensivos / ganados":"duelos_defensivos","Duelos ofensivos / ganados":"duelos_ofensivos"},inplace=True)
    Orense_duelos['match_id'] = Orense_duelos['Home'] + ' vs ' + Orense_duelos['Away']+ " - " + Orense_duelos["Fecha"]
    Orense_duelos.drop(["Fecha"], axis=1, inplace=True)  
    
    def get_duelos_a(group):
        if TEAM not in group['Home'].values and TEAM not in group['Away'].values:
            return group.assign(duelos_def_a=None,duelos_of_a=None)
        else:
            duelos_def_values=group['duelos_defensivos'].values
            duelos_of_values=group["duelos_ofensivos"].values
            return group.assign(
                duelos_def_a=[duelos_def_values[1], duelos_def_values[0]],
                duelos_of_a=[duelos_of_values[1], duelos_of_values[0]]
            )

    Orense_duelos=Orense_duelos.groupby("match_id",group_keys=False).apply(get_duelos_a)

    Orense_duelos=Orense_duelos[Orense_duelos.index%2==0].copy()

    Orense_duelos["Result"] = Orense_duelos.apply(
        lambda x: x["Home"] if x["Result"] == "Home"
        else x["Away"] if x["Result"] == "Away"
        else "Draw",
        axis=1
    )
    Orense_duelos["Result"]=Orense_duelos.apply(lambda x: 1 if x["Result"]==TEAM
                                        else 0 if x["Result"]=="Draw"
                                        else -1,axis=1)
    Orense_duelos["Opponent"]=Orense_duelos.apply(lambda x: x["Home"] if x["Away"]==TEAM
                                          else x["Away"],axis=1)
    Orense_duelos["Place"]=Orense_duelos.apply(lambda x: "Home" if x["Home"]==TEAM
                                       else "Away",axis=1)
    Orense_duelos["Result"] = Orense_duelos["Result"].astype("category")
    fig22 = px.scatter(
        Orense_duelos,
        x="duelos_defensivos",
        y="duelos_ofensivos",
        color="Result",          # maps to hue in Seaborn
        symbol="Place",          # maps to style in Seaborn
        color_discrete_map=results_palette,
        symbol_map=place_palette,
        text="Opponent",         # opponent names as hover text
        hover_data={
            "duelos_defensivos": ":.2f",
            "duelos_ofensivos": ":.2f",
            "Opponent": True,
            "Result": True,
            "Place": True
        },
        title=f"Duelos defensivos vs ofensivos ({TEAM})",
    )
    result_labels = {1: "Victoria", 0: "Empate", -1: "Derrota"}
    place_labels = {"Home": "Local", "Away": "Visitante"}  # Map symbol values to readable names

    for trace in fig22.data:
        parts = [p.strip() for p in trace.name.split(',')]
    
        # Map the result (color)
        try:
            color_key = int(parts[0])
            color_label = result_labels.get(color_key, parts[0])
        except ValueError:
            color_label = parts[0]
    
        # Map the place (symbol)
        symbol_label = place_labels.get(parts[1], parts[1]) if len(parts) > 1 else ""
    
        # Combine them for the legend
        trace.name = f"{color_label} ({symbol_label})"


    # --- Add labels "vs Opponent" above points ---
    fig22.update_traces(
        textposition="top center",
        marker=dict(size=12, line=dict(width=2, color="black"))
    )


    # --- Add reference line ---
    max_val = max(Orense_duelos["duelos_defensivos"].max(), Orense_duelos["duelos_ofensivos"].max())
    fig22.add_trace(
        go.Scatter(
            x=[45, max_val],
            y=[40, max_val],
            mode="lines",
            line=dict(color="gray", dash="dash"),
            showlegend=False,
            name="Reference line"
        )
    )


    # --- Layout adjustments ---
    fig22.update_layout(
        xaxis_title="Duelos defensivos",
        yaxis_title="Duelos ofensivos",
        template="plotly_white",
        hovermode="closest",
        height=700,
        width=1000,
        xaxis=dict(range=[Orense_duelos["duelos_defensivos"].min() - 1, Orense_duelos["duelos_defensivos"].max() + 1]),
        yaxis=dict(range=[Orense_duelos["duelos_ofensivos"].min() - 1.5, Orense_duelos["duelos_ofensivos"].max() + 1.5]),
    )
    #fig22.savefig(output_path22,dpi=300,bbox_inches="tight")
    #plt.show()
    ############# Contraataque vs Ataque posicional
    Orense_contra=Orense[["Contraataques / con remate", "Ataques posicionales / con remate"
                          ,"Home","Away","Result"]].copy()
    Orense_contra.rename(columns={"Contraataques / con remate":"contraataques","Ataques posicionales / con remate":"posicionales"},inplace=True)

    Orense_contra=Orense_contra[Orense_contra.index%2==0].copy()


    Orense_contra["Result"]=Orense_contra.apply(lambda x: x["Home"] if x["Result"]=="Home"
                                                else x["Away"] if x["Result"]=="Away"
                                                else "Draw",axis=1)

    Orense_contra["Result"]=Orense_contra.apply(lambda x: 1 if x["Result"]==TEAM
                                        else 0 if x["Result"]=="Draw"
                                        else -1,axis=1)
    Orense_contra["Opponent"]=Orense_contra.apply(lambda x: x["Home"] if x["Away"]==TEAM
                                          else x["Away"],axis=1)
    Orense_contra["Place"]=Orense_contra.apply(lambda x: "Home" if x["Home"]==TEAM
                                       else "Away",axis=1)
    Orense_contra["Result"] = Orense_contra["Result"].astype("category")
    fig23 = px.scatter(
        Orense_contra,
        x="posicionales",
        y="contraataques",
        color="Result",          # maps to hue in Seaborn
        symbol="Place",          # maps to style in Seaborn
        color_discrete_map=results_palette,
        symbol_map=place_palette,
        text="Opponent",         # opponent names as hover text
        hover_data={
            "posicionales": ":.2f",
            "contraataques": ":.2f",
            "Opponent": True,
            "Result": True,
            "Place": True
        },
        title=f"Ataques posicionales vs Contraataques ({TEAM})",
    )
    result_labels = {1: "Victoria", 0: "Empate", -1: "Derrota"}
    place_labels = {"Home": "Local", "Away": "Visitante"}  # Map symbol values to readable names

    for trace in fig23.data:
        parts = [p.strip() for p in trace.name.split(',')]
    
        # Map the result (color)
        try:
            color_key = int(parts[0])
            color_label = result_labels.get(color_key, parts[0])
        except ValueError:
            color_label = parts[0]
    
        # Map the place (symbol)
        symbol_label = place_labels.get(parts[1], parts[1]) if len(parts) > 1 else ""
    
        # Combine them for the legend
        trace.name = f"{color_label} ({symbol_label})"


    # --- Add labels "vs Opponent" above points ---
    fig23.update_traces(
        textposition="top center",
        marker=dict(size=12, line=dict(width=2, color="black"))
    )


    # --- Layout adjustments ---
    fig23.update_layout(
        xaxis_title="Ataques posicionales",
        yaxis_title="Contraataques",
        template="plotly_white",
        hovermode="closest",
        height=700,
        width=1000,
        xaxis=dict(range=[Orense_contra["posicionales"].min() - 1, Orense_contra["posicionales"].max() + 1]),
        yaxis=dict(range=[Orense_contra["contraataques"].min() - 0.5, Orense_contra["contraataques"].max() + 0.5]),
    )

    #fig23.savefig(output_path23,dpi=300,bbox_inches="tight")



    plots = {
        "Goles esperados (xG) vs Goles esperados en contra (xGa)": fig19,
        "PPDA vs PPDA del rival": fig20,
        "Recuperaciones en el primer tercio vs en último tercio": fig21,
        "Duelos ofensivos vs Duelos defensivos": fig22
    }

    selected_plots = st.multiselect(
        "Elige los gráficos a mostrar:",
        list(plots.keys()),           # options
        default=["Goles esperados (xG) vs Goles esperados en contra (xGa)",
                 "PPDA vs PPDA del rival",
                 "Recuperaciones en el primer tercio vs en último tercio",
                 "Duelos ofensivos vs Duelos defensivos"]         # preselected
    )

    # Display the selected graphs
    st.title("Métricas de rendimiento de equipo")

    for name in selected_plots:
        st.subheader(name)
        st.plotly_chart(plots[name], use_container_width=True)
        
    st.divider()
    import locale
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")

    def last_modified(folder_path):
        latest_mod = 0
        for root, _, files in os.walk(folder_path):
            for f in files:
                file_path = os.path.join(root, f)
                mod_time = os.path.getmtime(file_path)
                latest_mod = max(latest_mod, mod_time)
        fecha = datetime.fromtimestamp(latest_mod)
        return fecha.strftime("%-d de %B")

    last_update=last_modified(f"{BASE_DIR}/report_gen_teams/datos_equipos")

    st.write(f"Última actualización: {last_update} | Fuente de datos: Hudl Wyscout")