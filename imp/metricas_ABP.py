#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep  8 10:49:08 2025

@author: julieta
"""

import streamlit as st
from utils import login
from utils import util
from utils import logo_utils  # Import logo utilities
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
    directorio_logs = os.path.join(BASE_DIR, "logs")
    ruta_parameters = os.path.join(BASE_DIR, "report_gen", "parameters.xlsx")
    ruta_script_pizza = os.path.join(BASE_DIR, "report_gen", "PizzaWyscout.py")
    ruta_excel = os.path.join(BASE_DIR, "data", "2RFEF_wyscout_2024.xlsx")
    ruta_excel2 = os.path.join(BASE_DIR, "data")
    script_report_team = os.path.join(BASE_DIR, "report_gen_teams", "Report_Equipo.py")
    folder_equipos = os.path.join(BASE_DIR, "report_gen_teams", "datos_equipos")
    ruta_excel_equipos = os.path.join(BASE_DIR, "report_gen_teams", "datos_equipos")
    ruta_excel_equipos_excel = os.path.join(BASE_DIR, "data", "Equipos_2RFEF.xlsx")
    ruta_reports_wyscout = os.path.join(BASE_DIR, "report_gen_teams", "wyscout_report")
    Report_equipos = "Report_Equipo.py"
    directorio_base = os.path.dirname(ruta_script)
    directorio_equipos = os.path.join(BASE_DIR, "report_gen_teams", "datos_equipos")
    
    # Logo directory
    logos_dir = os.path.join(BASE_DIR, "assets", "logos_table")

    # Asegura existencia de la carpeta de logs
    os.makedirs(directorio_logs, exist_ok=True)

    teams = util.load_team_stats(directorio_equipos)

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

    #################### ACCIONES A BALON PARADO ####################

    ######## ABP vs % ABP con remate
    ABP = []

    for team, df in teams.items():
        abp = df[df["Fecha"] == team]["Jugadas a balón parado / con remate"].values
        abp_precision = df[df["Fecha"] == team]["Unnamed: 37"].values
        ABP.append({"Equipo": team, "abp": abp, "abp_precision": abp_precision})

    ABP = pd.DataFrame(ABP)
    ABP["abp"] = ABP["abp"].str[0]
    ABP["abp_precision"] = ABP["abp_precision"].str[0]

    mean_abp_ganados = ABP['abp_precision'].mean()
    
    fig15 = logo_utils.create_scatter_with_logos_plotly(
        ABP,
        x_col="abp",
        y_col="abp_precision",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Acciones a balón parado vs Efectividad de remate",
        xlabel="ABP totales",
        ylabel="% ABP rematadas",
        logo_size=45,
        logo_visual_percent=0.30  # 30% of figure dimension
    )

    ############# corners totales vs rematados
    Corners = []

    for team, df in teams.items():
        corners = df[df["Fecha"] == team]["Córneres / con remate"].values
        precision_corners = df[df["Fecha"] == team]["Unnamed: 40"].values
        Corners.append({"Equipo": team, "corners": corners,
                        "corners_precision": precision_corners})
    Corners = pd.DataFrame(Corners)
    Corners["corners"] = Corners["corners"].str[0]
    Corners["corners_precision"] = Corners["corners_precision"].str[0]

    mean_corners_ganados = Corners['corners_precision'].mean()

    fig16 = logo_utils.create_scatter_with_logos_plotly(
        Corners,
        x_col="corners",
        y_col="corners_precision",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Córneres totales vs Efectividad de remate",
        xlabel="Córneres totales",
        ylabel="% córneres rematados",
        logo_size=45,
        logo_visual_percent=0.50  # 50% of figure dimension
    )

    ############## tiros libres totales vs rematados
    Tiros_libres = []

    for team, df in teams.items():
        tiros = df[df["Fecha"] == team]["Tiros libres / con remate"].values
        tiros_precision = df[df["Fecha"] == team]["Unnamed: 43"].values
        Tiros_libres.append({"Equipo": team, "tiros": tiros,
                             "tiros_precision": tiros_precision})
    Tiros_libres = pd.DataFrame(Tiros_libres)
    Tiros_libres["tiros"] = Tiros_libres["tiros"].str[0]
    Tiros_libres["tiros_precision"] = Tiros_libres["tiros_precision"].str[0]
    mean_tiros_ganados = Tiros_libres['tiros_precision'].mean()

    fig17 = logo_utils.create_scatter_with_logos_plotly(
        Tiros_libres,
        x_col="tiros",
        y_col="tiros_precision",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Tiros libres totales vs Efectividad de remate",
        xlabel="Tiros libres totales",
        ylabel="% tiros libres rematados",
        logo_size=45,
        logo_visual_percent=1.8  # 180% of figure dimension
    )

    ############### penaltis vs % de penaltis marcados
    Penaltis = []

    for team, df in teams.items():
        penaltis = df[df["Fecha"] == team]["Penaltis / marcados"].values
        penaltis_aciertos = df[df["Fecha"] == team]["Unnamed: 46"].values
        Penaltis.append({"Equipo": team, "penaltis": penaltis,
                         "penaltis_aciertos": penaltis_aciertos})
    Penaltis = pd.DataFrame(Penaltis)
    Penaltis["penaltis"] = Penaltis["penaltis"].str[0]
    Penaltis["penaltis_aciertos"] = Penaltis["penaltis_aciertos"].str[0]

    mean_penaltis_ganados = Penaltis['penaltis_aciertos'].mean()

    fig18 = logo_utils.create_scatter_with_logos_plotly(
        Penaltis,
        x_col="penaltis",
        y_col="penaltis_aciertos",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Penaltis totales vs Efectividad de conversión",
        xlabel="Penaltis totales",
        ylabel="% penaltis marcados",
        logo_size=45,
        logo_visual_percent=8  # 800% of figure dimension
    )

    plots = {
        "Acciones a balón parado: Volumen vs efectividad de remate": fig15,
        "Córneres: Volumen vs efectividad de remate": fig16,
        "Tiros libres: Volumen vs efectividad de remate": fig17,
        "Penaltis: Volumen vs efectividad de conversión": fig18,
    }

    selected_plots = st.multiselect(
        "Elige los gráficos a mostrar:",
        list(plots.keys()),
        default=list(plots.keys())
    )

    # Display the selected graphs
    st.title("Métricas de Acciones a Balón Parado")
    st.markdown("*Análisis de volumen y efectividad en jugadas estratégicas*")

    for name in selected_plots:
        st.subheader(name)
        st.plotly_chart(plots[name], use_container_width=True)

    st.divider()
    import locale
    try:
        locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
    except:
        pass

    def last_modified(folder_path):
        latest_mod = 0
        for root, _, files in os.walk(folder_path):
            for f in files:
                file_path = os.path.join(root, f)
                mod_time = os.path.getmtime(file_path)
                latest_mod = max(latest_mod, mod_time)
        fecha = datetime.fromtimestamp(latest_mod)
        try:
            return fecha.strftime("%-d de %B")
        except:
            return fecha.strftime("%d de %B")

    last_update = last_modified(f"{BASE_DIR}/report_gen_teams/datos_equipos")

    st.write(f"Última actualización: {last_update} | Fuente de datos: Hudl Wyscout")