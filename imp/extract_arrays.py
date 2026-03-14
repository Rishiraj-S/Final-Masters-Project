#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 24 12:55:39 2025

@author: julieta
"""
import pandas as pd
import numpy as np
import json
from mplsoccer import Radar, FontManager, grid
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from urllib.request import urlopen
from PIL import Image
from mplsoccer import PyPizza, add_image, FontManager

from highlight_text import fig_text
from matplotlib.lines import Line2D
from scipy.stats import percentileofscore
import os
import argparse
"""
        WYSCOUT DATA
"""

def extract_arrays_wyscout(wyscout_file,parameters_file,player_id_analizing,param_entry,min_minutes):
    
    if not os.path.exists(wyscout_file):
        print(f"El fichero {wyscout_file} no existe.")
        return None
    if not os.path.exists(parameters_file):
        print(f"El fichero {parameters_file} no existe.")
        return None
    df_stats=pd.read_excel(wyscout_file)
    for i,row in df_stats.iterrows():
        df_stats.loc[i,"player_id"]=i+2
    df_stats=df_stats[df_stats["Minutos jugados"]>min_minutes]
    positions_dict={"GK":"portero","LB":"lateral","RB":"lateral","DMF":"defmid","OF":"ofmid",
                     "AMF":"ofmid","LCB":"defensa","RCB":"defensa","LWF":"extremo","RWF":"extremo",
                     "LAMF":"ofmid","RAMF":"ofmid","LCMF":"ofmid","RCMF":"ofmid","CF":"delantero",
                     "CB":"defensa","RW":"extremo","LDMF":"defmid","LW":"extremo","RDMF":"defmid",
                     "RWB":"lateral","LWB":"lateral"
                     }

    positions=["portero","defensa","defmid","ofmid","lateral","delantero","extremo"]
    parameters = {}
    for position in positions:
        try:
            df_position = pd.read_excel(parameters_file, sheet_name=position)

            # Crear un diccionario con las claves 'ofensive' y 'defensive' y los valores correspondientes
            parameters[position] = {
                "ofensive": df_position['ofensivo'].dropna().tolist(),  # Convertir la columna 'ofensivo' en lista
                "defensive": df_position['defensivo'].dropna().tolist(),  # Convertir la columna 'defensivo' en lista
                "of_number": df_position["PizzaPlot_of"].dropna().tolist(),
                "ofensive_es":df_position['ofensivo es'].dropna().tolist(),
                "defensive_es":df_position['defensivo es'].dropna().tolist(),
            }
        except Exception as e:
            print(f"Error al procesar la posición {position}: {e}")
        except ValueError:
            print(f"Hoja '{position}' no encontrada en el archivo.")
    #con esta funcion se mapean las posiciones especificas a las generales
    def map_positions(positions_str):
        positions = positions_str.split(", ")  
        general_positions = [positions_dict.get(pos, pos) for pos in positions]  
        unique_positions = set(general_positions)  
        return ", ".join(unique_positions)  # Unir las posiciones únicas

    df_stats["general_position"] = df_stats["Posición específica"].apply(map_positions)
    #aqui terminamos de mapear las posiciones
    df_stats[['general_position', 'general_position2',"general_position3"]] = df_stats['general_position'].str.split(", ", n=2, expand=True)
    df_stats.fillna(df_stats.mean(numeric_only=True),inplace=True)
    df_stats["general_position2"] = df_stats["general_position2"].fillna("None")
    df_stats["general_position3"] = df_stats["general_position3"].fillna("None")

    df_general_stats=df_stats[["Jugador","Equipo","Equipo durante el período seleccionado","Edad","Valor de mercado","Vencimiento contrato","Partidos jugados","Minutos jugados","player_id",'general_position', 'general_position2',"general_position3"]].copy()
    general_stats_player=df_general_stats[df_general_stats["player_id"]==player_id_analizing].iloc[0]
    stats_player=df_stats[df_stats["player_id"]==player_id_analizing].iloc[0]
    player_position=general_stats_player["general_position"]
    df_stats_position=df_stats[(df_stats["general_position"]==player_position) | (df_stats["general_position2"]==player_position) | (df_stats["general_position3"]==player_position)].copy()
    #print(df_stats_position["general_position"])
    param_ofensive=parameters[player_position]["ofensive"]
    param_of_idioma=parameters[player_position]["ofensive_es"]
    
    param_of_idioma = [item.replace("\\n", "") for item in param_of_idioma]
    param_defensive=parameters[player_position]["defensive"]
    of_number=parameters[player_position]["of_number"]
    param_def_id=parameters[player_position]["defensive_es"]
    param_def_id = [item.replace("\\n", "") for item in param_def_id]
    param_ofensive1 = []
    param_ofensive2 = []
    min_array=[]
    max_array=[]
    player_array=[]
    params_array=[]
    all_params=param_ofensive+param_defensive   
    # Dividir los parámetros ofensivos según el valor de of_number
    def calculate_and_assign_percentiles(df, *column_lists):

        columns = pd.Series(sum(column_lists, [])).unique().tolist()
        
        # Calcular los percentiles para las columnas 
        for col in columns:
            values = df[col].values  
            percentiles = [
                percentileofscore(values, x, kind='rank') 
                for x in values
            ]
            
            
            df[col] = pd.Series(percentiles).round().astype(int).values
        
        return df
    df_stats_percentile=calculate_and_assign_percentiles(df_stats_position, parameters[player_position]["defensive"], parameters[player_position]["ofensive"])
    df_stats_percentile=df_stats_percentile[df_stats_percentile["player_id"]==player_id_analizing]
    ####
    param_of1_id=[]
    param_of2_id=[]
    for i, param in enumerate(param_ofensive):
        if of_number[i] == 1:
            param_ofensive1.append(param)
        elif of_number[i] == 2:
            param_ofensive2.append(param)
    for i,param in enumerate(param_of_idioma):
        if of_number[i] == 1:
            param_of1_id.append(param)
        elif of_number[i] == 2:
            param_of2_id.append(param)
    if param_entry=="param_of1":
        min_array=df_stats[param_ofensive1].min(axis=0)
        max_array=df_stats[param_ofensive1].max(axis=0)
        player_array=stats_player[param_ofensive1]
        params_array=param_ofensive1
        percentiles_player=df_stats_percentile[param_ofensive1].values.flatten().tolist()
        param_en=param_of1_id
        
    elif param_entry=="param_of2":
        min_array=df_stats[param_ofensive2].min(axis=0)
        max_array=df_stats[param_ofensive2].max(axis=0)
        player_array=stats_player[param_ofensive2]
        params_array=param_ofensive2
        percentiles_player=df_stats_percentile[param_ofensive2].values.flatten().tolist()
        param_en=param_of2_id
    elif param_entry=="param_def":
        min_array=df_stats[param_defensive].min(axis=0)
        max_array=df_stats[param_defensive].max(axis=0)
        player_array=stats_player[param_defensive]
        params_array=param_defensive
        percentiles_player=df_stats_percentile[param_defensive].values.flatten().tolist()
        param_en=param_def_id
    else:
        min_array=None
        max_array=None
        player_array=None
        params_array=None
        percentiles_player=None
        param_en=None
    
    
    return min_array,max_array,player_array,params_array, df_stats,percentiles_player,param_en



def extract_arrays_physical(physical_file,player_name,min_minutes):
    
    if not os.path.exists(physical_file):
        print(f"El fichero {physical_file} no existe.")
        return None
    
    df_phys=pd.read_csv(physical_file,delimiter=";")
    
    if player_name in df_phys["Short Name"].values:
        print("TODO OK")
    else:
        print(f"La jugadora {player_name} no tiene estadísticas físicas")
        return None, None, None, None, None
    
    dictionary_positions={"Delantero":"Center Forward","Defensa":"Central Defender",
                          "Centrocampista ofensivo":"Midfield","Centrocampista defensivo":"Midfield",
                          "Lateral":"Full Back","Extremo":"Wide Attacker"}
    PLAYER_POSITION=df_phys[df_phys["Short Name"]==player_name]["Position Group"].iloc[0]

    df_phys=df_phys[df_phys["Position Group"]==PLAYER_POSITION]
    
    columns_bigger=["Short Name","PSV-99","Running Distance P90","HSR Distance P90",
                   "Sprint Distance P90","HI Count P90","Medium Acceleration Count P90",
                   "High Acceleration Count P90","Medium Deceleration Count P90",
                   "High Deceleration Count P90","Explosive Acceleration to Sprint Count P90"]
    
    df_phys=df_phys[columns_bigger].copy()
    
    columns_pizza=["PSV-99","Running Distance P90","HSR Distance P90",
                   "Sprint Distance P90","HI Count P90","Medium Acceleration Count P90",
                   "High Acceleration Count P90","Medium Deceleration Count P90",
                   "High Deceleration Count P90","Explosive Acceleration to Sprint Count P90"]
    
    columns_show = ["PSV-99", "Distancia corriendo /90", "Distancia HSR /90",
                "Distancia sprint /90", "Conteo HI /90", "Conteo aceleración media /90",
                "Conteo aceleración alta /90", "Conteo desaceleración media /90",
                "Conteo desaceleración alta /90", "Conteo aceleración explosiva a sprint /90"]
    
    def calculate_and_assign_percentiles(df, *column_lists):

        columns = pd.Series(sum(column_lists, [])).unique().tolist()
        
        # Calcular los percentiles para las columnas 
        for col in columns:
            values = df[col].values  
            percentiles = [
                percentileofscore(values, x, kind='rank') 
                for x in values
            ]
            
            
            df[col] = pd.Series(percentiles).round().astype(int).values
        
        return df
    df_phys_percentile=df_phys.copy()
    df_phys_percentile=calculate_and_assign_percentiles(df_phys_percentile, columns_pizza)
    df_phys_percentile=df_phys_percentile[df_phys_percentile["Short Name"]==player_name]
    df_phys_player_stats=df_phys[df_phys["Short Name"]==player_name]
    min_array=df_phys[columns_pizza].min(axis=0)
    max_array=df_phys[columns_pizza].max(axis=0)
    player_array=df_phys_player_stats[columns_pizza]
    percentiles_player=df_phys_percentile[columns_pizza]
    
    player_array = player_array.T
    min_array = min_array.T
    max_array = max_array.T
    percentiles_player=percentiles_player.T
    percentiles_player=percentiles_player.iloc[:, 0] 
    player_array=player_array.iloc[:, 0] 

    
    return min_array,max_array,player_array,percentiles_player,columns_pizza



if __name__ == "__main__":
    print("ENTRAMOS BIEN")
    parser = argparse.ArgumentParser()
    parser.add_argument("--player_id_analizing", type=int, required=True)
    parser.add_argument("--wyscout_file", type=str, required=True)
    parser.add_argument("--parameters_file", type=str, required=True)
    parser.add_argument("--min_minutes", type=int, default=500)
    parser.add_argument("--param_entry", type=str, default="param_of1")


    args = parser.parse_args()
    
    extract_arrays_wyscout(wyscout_file=args.wyscout_file,
                           parameters_file=args.parameters_file,
                           player_id_analizing=args.player_id_analizing,
                           param_entry=args.param_entry,
                           min_minutes=args.min_minutes)


