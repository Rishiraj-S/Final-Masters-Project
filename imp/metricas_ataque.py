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
            team_avg = df[df["Equipo"] == team].mean(numeric_only=True)
            adversarios_avg = df[df["Equipo"] != team].mean(numeric_only=True)
            df.loc[df["Fecha"] == team, team_avg.index] = team_avg.values
            df.loc[df["Fecha"] == "Adversarios", adversarios_avg.index] = adversarios_avg.values
            teams[team] = df
        return teams

    teams = process_teams(teams)

    ################# METRICAS DE ATAQUE ####################

    ############# Contraataques vs ataques posicionales
    Contraataques = []

    for team, df in teams.items():
        contras = df[df["Fecha"] == team]["Contraataques / con remate"].values
        posicionales = df[df["Fecha"] == team]["Ataques posicionales / con remate"].values
        Contraataques.append({"Equipo": team, "contras": contras, "posicionales": posicionales})
    Contraataques = pd.DataFrame(Contraataques)
    Contraataques["contras"] = Contraataques["contras"].str[0]
    Contraataques["posicionales"] = Contraataques["posicionales"].str[0]

    fig11 = logo_utils.create_scatter_with_logos_plotly(
        Contraataques,
        x_col="posicionales",
        y_col="contras",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Ataques posicionales vs Contraataques",
        xlabel="Ataques posicionales",
        ylabel="Contraataques",
        logo_size=45,
        logo_visual_percent=2  # 200% of figure dimension
    )

    ################ Pases totales vs % de acierto
    Pases = []

    for team, df in teams.items():
        pases = df[df["Fecha"] == team]["Pases / logrados"].values
        aciertos = df[df["Fecha"] == team]["Unnamed: 13"].values
        Pases.append({"Equipo": team, "pases": pases, "acertados": aciertos})

    Pases = pd.DataFrame(Pases)
    Pases["pases"] = Pases["pases"].str[0]
    Pases["acertados"] = Pases["acertados"].str[0]

    mean_duelos_ganados = Pases['acertados'].mean()

    fig12 = logo_utils.create_scatter_with_logos_plotly(
        Pases,
        x_col="pases",
        y_col="acertados",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Pases totales vs % de acierto en el pase",
        xlabel="Pases totales",
        ylabel="% de acierto en el pase",
        logo_size=45,
        logo_visual_percent=0.6  # 60% of figure dimension
    )

    ########## Pases ultimo tercio vs en profundidad
    Profundidad = []

    for team, df in teams.items():
        pases_3_tercio = df[df["Fecha"] == team]["Pases en el último tercio / logrados"].values
        profundidad = df[df["Fecha"] == team]["Pases en profundidad completados"].values
        Profundidad.append({"Equipo": team, "pases_3_tercio": pases_3_tercio,
                            "profundidad": profundidad})

    Profundidad = pd.DataFrame(Profundidad)
    Profundidad["pases_3_tercio"] = Profundidad["pases_3_tercio"].str[0]
    Profundidad["profundidad"] = Profundidad["profundidad"].str[0]

    fig13 = logo_utils.create_scatter_with_logos_plotly(
        Profundidad,
        x_col="pases_3_tercio",
        y_col="profundidad",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Pases en el último tercio vs Pases en profundidad",
        xlabel="Pases en el último tercio",
        ylabel="Pases en profundidad",
        logo_size=45,
        logo_visual_percent=0.08  # 8% of figure dimension
    )

    ############# Centros totales vs centros precisos
    Centros = []

    for team, df in teams.items():
        centros = df[df["Fecha"] == team]["Centros / precisos"].values
        precisos = df[df["Fecha"] == team]["Unnamed: 49"].values
        Centros.append({"Equipo": team, "centros": centros, "precisos": precisos})
    Centros = pd.DataFrame(Centros)
    Centros["centros"] = Centros["centros"].str[0]
    Centros["precisos"] = Centros["precisos"].str[0]
    
    mean_centros_ganados = Centros['precisos'].mean()
    
    fig14 = logo_utils.create_scatter_with_logos_plotly(
        Centros,
        x_col="centros",
        y_col="precisos",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Centros totales vs % de acierto en los centros",
        xlabel="Centros totales",
        ylabel="% de acierto en los centros",
        logo_size=45,
        logo_visual_percent=0.20  # 20% of figure dimension
    )

    plots = {
        "Contraataque vs Ataque posicional": fig11,
        "Número de pases totales vs % de acierto": fig12,
        "Pases último tercio vs. Pases en profundidad": fig13,
        "Centros totales vs Centros precisos": fig14,
    }

    selected_plots = st.multiselect(
        "Elige los gráficos a mostrar:",
        list(plots.keys()),
        default=list(plots.keys())
    )

    # Display the selected graphs
    st.title("Métricas de Ataque")
    st.markdown("*Análisis de patrones ofensivos y efectividad en ataque*")

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