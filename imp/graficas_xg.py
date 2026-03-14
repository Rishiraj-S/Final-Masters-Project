#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep  8 10:41:56 2025

@author: julieta
"""

import streamlit as st
from utils import login
from utils import util
from utils import logo_utils  # Import the new logo utilities
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
import unicodedata


def show_xg():

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

    # --- xG For ---
    xG_for = []
    for team, df in teams.items():
        xg = df[df["Fecha"] == team]["xG"].values
        xG_for.append({"Equipo": team, "xG": xg})
    xG_for = pd.DataFrame(xG_for)
    xG_for["xG"] = xG_for["xG"].str[0]

    # --- xG Against ---
    xG_against = []
    for team, df in teams.items():
        xga = df[df["Fecha"] == "Adversarios"]["xG"].values
        xG_against.append({"Equipo": team, "xGa": xga})
    xG_against = pd.DataFrame(xG_against)
    xG_against["xGa"] = xG_against["xGa"].str[0]

    # --- Final Calculations ---
    xG_for["xG-xGa"] = xG_for["xG"] - xG_against["xGa"]
    xG_for["xGa"] = xG_against["xGa"]
    xG_for = xG_for.sort_values(by="xG-xGa", ascending=False)

    # --- Bar Chart (Plotly) ---
    fig1 = px.bar(
        xG_for,
        x="Equipo",
        y="xG-xGa",
        color="xG-xGa",
        color_continuous_scale="Blues",
        title="Ranking goles esperados (xG) - goles esperados en contra (xGA)",
        hover_data={
            "xG": ":.2f",
            "xGa": ":.2f",
            "xG-xGa": ":.2f"
        },
    )

    fig1.add_hline(y=0, line_dash="solid", line_color="black")

    fig1.update_layout(
        xaxis_title="Equipo",
        yaxis_title="xG - xGA",
        xaxis_tickangle=-45,
        template="plotly_white",
        height=600,
    )

    # --- Scatter plot xG vs xGa WITH LOGOS (Plotly) ---
    fig2 = logo_utils.create_scatter_with_logos_plotly(
        xG_for,
        x_col="xGa",
        y_col="xG",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Goles esperados (xG) vs Goles esperados en contra (xGa)",
        xlabel="Goles esperados en contra (xGa)",
        ylabel="Goles esperados (xG)",
        logo_size=45,
        logo_visual_percent=0.18  # Adjust this value to control logo size (5% of figure)
    )

    # --- xG per shot calculation ---
    Goles_por_tiro = []

    for team, df in teams.items():
        xg = df[df["Fecha"] == team]["xG"].values
        tiros = df[df["Fecha"] == team]["Tiros / a la portería "].values
        goles_por_tiro = xg / tiros
        xga = df[df["Fecha"] == "Adversarios"]["xG"].values
        xga_por_tiro = xga / tiros
        Goles_por_tiro.append({"Equipo": team, "xG_por_tiro": goles_por_tiro,
                               "xGa_por_tiro": xga_por_tiro})
    Goles_por_tiro = pd.DataFrame(Goles_por_tiro)
    Goles_por_tiro["xG_por_tiro"] = Goles_por_tiro["xG_por_tiro"].str[0]
    Goles_por_tiro["xGa_por_tiro"] = Goles_por_tiro["xGa_por_tiro"].str[0]

    # --- Scatter plot xG per shot WITH LOGOS (Plotly) ---
    fig3 = logo_utils.create_scatter_with_logos_plotly(
        Goles_por_tiro,
        x_col="xGa_por_tiro",
        y_col="xG_por_tiro",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Goles esperados por tiro vs Goles esperados por tiro rival",
        xlabel="Goles esperados por tiro rival",
        ylabel="Goles esperados por tiro",
        logo_size=45,
        logo_visual_percent=0.2  # Adjust this value to control logo size (6% of figure)
    )

    # --- Plot selection and display ---
    plots = {
        "Ranking goles esperados (xG) - goles esperados en contra (xGA)": fig1,
        "Goles esperados (xG) vs Goles esperados en contra (xGa)": fig2,
        "Goles esperados por tiro vs Goles esperados por tiro rival": fig3
    }

    selected_plots = st.multiselect(
        "Elige los gráficos a mostrar:",
        list(plots.keys()),
        default=["Ranking goles esperados (xG) - goles esperados en contra (xGA)",
                 "Goles esperados (xG) vs Goles esperados en contra (xGa)",
                 "Goles esperados por tiro vs Goles esperados por tiro rival"]
    )

    # Display the selected graphs
    st.title("Métricas de Expected Goals (xG)")

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