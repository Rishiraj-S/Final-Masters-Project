#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep  8 10:45:10 2025

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
            if team == "UDG Tenerife":
                print(df)
        return teams

    teams = process_teams(teams)

    ########## METRICAS DEFENSIVAS ####################

    ########### balones recuperados en primer y ultimo tercio
    Recuperaciones = []

    for team, df in teams.items():
        primer_tercio = df[df["Fecha"] == team]["Unnamed: 20"].values
        ultimo_tercio = df[df["Fecha"] == team]["Unnamed: 22"].values
        Recuperaciones.append({"Equipo": team, "recuperaciones_1_tercio": primer_tercio,
                               "recuperaciones_3_tercio": ultimo_tercio})
    Recuperaciones = pd.DataFrame(Recuperaciones)
    Recuperaciones["recuperaciones_1_tercio"] = Recuperaciones["recuperaciones_1_tercio"].str[0]
    Recuperaciones["recuperaciones_3_tercio"] = Recuperaciones["recuperaciones_3_tercio"].str[0]

    fig4 = logo_utils.create_scatter_with_logos_plotly(
        Recuperaciones,
        x_col="recuperaciones_1_tercio",
        y_col="recuperaciones_3_tercio",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Recuperaciones en primer tercio vs en último tercio",
        xlabel="Balones recuperados en el primer tercio",
        ylabel="Balones recuperados en el último tercio",
        logo_size=45,
        logo_visual_percent=0.085  # 8.5% of figure dimension
    )

    ################## duelos defensivos vs duelos ofensivos
    Duelos = []

    for team, df in teams.items():
        duelos_ofensivos = df[df["Fecha"] == team]["Duelos ofensivos / ganados"].values
        duelos_defensivos = df[df["Fecha"] == team]["Duelos defensivos / ganados"].values
        Duelos.append({"Equipo": team, "duelos_ofensivos": duelos_ofensivos,
                       "duelos_defensivos": duelos_defensivos})
    Duelos = pd.DataFrame(Duelos)
    Duelos["duelos_ofensivos"] = Duelos["duelos_ofensivos"].str[0]
    Duelos["duelos_defensivos"] = Duelos["duelos_defensivos"].str[0]

    fig5 = logo_utils.create_scatter_with_logos_plotly(
        Duelos,
        x_col="duelos_defensivos",
        y_col="duelos_ofensivos",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Duelos ofensivos vs Duelos defensivos",
        xlabel="Duelos defensivos",
        ylabel="Duelos ofensivos",
        logo_size=45,
        logo_visual_percent=0.1  # 10% of figure dimension
    )

    ############## Duelos aereos totales vs aereos ganados
    Duelos_aereos = []

    for team, df in teams.items():
        duelos_aereos = df[df["Fecha"] == team]["Duelos aéreos / ganados"].values
        duelos_aereos_ganados1 = df[df["Fecha"] == team]["Unnamed: 68"].values
        duelos_aereos_ganados = (duelos_aereos_ganados1 * 100) / duelos_aereos
        Duelos_aereos.append({"Equipo": team, "duelos_aereos": duelos_aereos,
                             "duelos_ganados": duelos_aereos_ganados})
    Duelos_aereos = pd.DataFrame(Duelos_aereos)
    Duelos_aereos["duelos_aereos"] = Duelos_aereos["duelos_aereos"].str[0]
    Duelos_aereos["duelos_ganados"] = Duelos_aereos["duelos_ganados"].str[0]

    mean_duelos_ganados = Duelos_aereos['duelos_ganados'].mean()

    fig6 = logo_utils.create_scatter_with_logos_plotly(
        Duelos_aereos,
        x_col="duelos_aereos",
        y_col="duelos_ganados",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Duelos aéreos vs % Duelos aéreos ganados",
        xlabel="Duelos aéreos",
        ylabel="% Duelos aéreos ganados",
        logo_size=45,
        logo_visual_percent=0.16  # 16% of figure dimension
    )

    ############# Despejes vs Interceptaciones
    Despejes = []

    for team, df in teams.items():
        despejes = df[df["Fecha"] == team]["Despejes"].values
        interceptaciones = df[df["Fecha"] == team]["Interceptaciones"].values
        Despejes.append({"Equipo": team, "despejes": despejes, "interceptaciones": interceptaciones})

    Despejes = pd.DataFrame(Despejes)
    Despejes["despejes"] = Despejes["despejes"].str[0]
    Despejes["interceptaciones"] = Despejes["interceptaciones"].str[0]

    fig7 = logo_utils.create_scatter_with_logos_plotly(
        Despejes,
        x_col="interceptaciones",
        y_col="despejes",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="Interceptaciones vs Despejes",
        xlabel="Interceptaciones",
        ylabel="Despejes",
        logo_size=45,
        logo_visual_percent=0.08  # 8% of figure dimension
    )

    ############ PPDA bar graph
    PPDA = []

    for team, df in teams.items():
        ppda = df[df["Fecha"] == team]["PPDA"].values
        PPDA.append({"Equipo": team, "PPDA": ppda})
    PPDA = pd.DataFrame(PPDA)
    PPDA["PPDA"] = PPDA["PPDA"].str[0]

    PPDA = PPDA.sort_values(by="PPDA", ascending=False)

    fig8 = px.bar(
        PPDA,
        x="Equipo",
        y="PPDA",
        text="PPDA",
        color_discrete_sequence=["blue"],
        title="PPDA por equipo",
    )

    # --- Customize text labels and marker style ---
    fig8.update_traces(
        texttemplate="%{text:.2f}",
        textposition="outside",
        marker_line_color="black",
        marker_line_width=1.5
    )

    # --- Layout adjustments ---
    fig8.update_layout(
        xaxis_title=None,
        yaxis_title="PPDA",
        template="plotly_white",
        xaxis_tickangle=45,
        xaxis_tickfont=dict(size=18, family="Arial Black"),
        yaxis=dict(title_font=dict(size=16, family="Arial Black")),
        height=700,
        width=1000
    )

    ############## PPDA scatter
    PPDA_full = []

    for team, df in teams.items():
        ppda = df[df["Fecha"] == team]["PPDA"].values
        ppda_against = df[df["Fecha"] == "Adversarios"]["PPDA"].values
        PPDA_full.append({"Equipo": team, "PPDA": ppda, "PPDA_against": ppda_against})
    PPDA_full = pd.DataFrame(PPDA_full)
    PPDA_full["PPDA"] = PPDA_full["PPDA"].str[0]
    PPDA_full["PPDA_against"] = PPDA_full["PPDA_against"].str[0]

    fig9 = logo_utils.create_scatter_with_logos_plotly(
        PPDA_full,
        x_col="PPDA_against",
        y_col="PPDA",
        team_col="Equipo",
        logos_dir=logos_dir,
        title="PPDA vs PPDA del rival",
        xlabel="PPDA del rival",
        ylabel="PPDA",
        logo_size=45,
        logo_visual_percent=0.08  # 5% of figure dimension
    )

    ############# tarjetas amarillas y rojas
    tarjetas = []

    for team, df in teams.items():
        yellow = df[df["Fecha"] == team]["Tarjetas amarillas"].values
        red = df[df["Fecha"] == team]["Tarjetas rojas"].values
        tarjetas.append({"Equipo": team, "Amarillas": yellow, "Rojas": red})
    tarjetas = pd.DataFrame(tarjetas)
    tarjetas["Amarillas"] = tarjetas["Amarillas"].str[0].astype(float)
    tarjetas["Rojas"] = tarjetas["Rojas"].str[0].astype(float)

    tarjetas["Totales"] = tarjetas["Amarillas"] + tarjetas["Rojas"]
    tarjetas = tarjetas.sort_values("Totales", ascending=False)

    fig10 = go.Figure()

    # --- Add red cards ---
    fig10.add_trace(
        go.Bar(
            x=tarjetas["Equipo"],
            y=tarjetas["Rojas"],
            name="Rojas",
            marker_color="#C70000",
            marker_line_color="black",
            marker_line_width=1.5,
            text=tarjetas["Rojas"],
            textposition="outside"
        )
    )

    # --- Add yellow cards stacked on top ---
    fig10.add_trace(
        go.Bar(
            x=tarjetas["Equipo"],
            y=tarjetas["Amarillas"],
            name="Amarillas",
            marker_color="#FFE000",
            marker_line_color="black",
            marker_line_width=1.5,
            text=tarjetas["Amarillas"],
            textposition="outside",
            offsetgroup=0,
        )
    )

    # --- Layout adjustments ---
    fig10.update_layout(
        barmode='stack',
        xaxis_title=None,
        yaxis_title="Promedio de tarjetas",
        template="plotly_white",
        xaxis_tickangle=45,
        xaxis_tickfont=dict(size=18, family="Arial Black"),
        yaxis=dict(title_font=dict(size=16, family="Arial Black")),
        height=700,
        width=1000
    )

    plots = {
        "Recuperaciones en primer tercio vs en último tercio": fig4,
        "Duelos ofensivos vs Duelos defensivos": fig5,
        "Duelos aéreos totales vs Duelos aéreos ganados": fig6,
        "Interceptaciones vs Despejes": fig7,
        "Pases Permitidos por Acción Defensiva (PPDA)": fig8,
        "PPDA vs PPDA del rival": fig9,
        "Tarjetas amarillas y Tarjetas rojas, por partido": fig10
    }

    selected_plots = st.multiselect(
        "Elige los gráficos a mostrar:",
        list(plots.keys()),
        default=list(plots.keys())
    )

    # Display the selected graphs
    st.title("Métricas Defensivas")
    st.markdown("*Análisis de comportamiento defensivo y efectividad*")

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