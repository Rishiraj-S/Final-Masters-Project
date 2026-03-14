#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Apr 23 09:33:47 2025

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
import math
from reportlab.platypus import Paragraph, Image, SimpleDocTemplate, Spacer, Frame
from reportlab.platypus import PageTemplate, BaseDocTemplate, PageBreak, FrameBreak
from reportlab.platypus import Flowable
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT  
from reportlab.platypus import KeepInFrame
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Preformatted
# Si queremos tablas...
from reportlab.platypus import Table, TableStyle
# Importamos clase de hoja de estilo de ejemplos
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import KeepTogether

# Se importa el tamaño de la hoja.
from reportlab.lib.pagesizes import A4

# Y los colores.
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.units import cm
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.graphics import renderPDF
import time
from PIL import Image as PILImage
import io
from cercania_lateralidad import Heatmap_one_team, cercania_porteria_lateral, passnetwork_oneteam
from cercania_lateralidad import get_goals,get_tabla1,get_tabla2,get_tabla3,get_tabla4
from reportlab.lib.colors import Color
import datetime

import argparse
import warnings
from pathlib import Path
# Ignorar PerformanceWarning de pandas
warnings.simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


pd.options.mode.chained_assignment = None  # Oculta SettingWithCopyWarning
import os 
import tempfile
from pathlib import Path
BASE_DIR = os.path.dirname(os.path.dirname(__file__)) 
def create_report(home_team,away_team,filepath_f40,filepath_f24,filepath_f70,filepath_f73,filepath_f27home,filepath_f27away,color_selection="#FFFFFF"):

    
   
    if color_selection=="#FFFFFF":
        letter_colors="#000000"
        
    else:
        letter_colors="#FFFFFF"
        
    
    #logo_our_team=f"{BASE_DIR}/assets/Logos/Redes_Logo.png"
    df_tabla1=get_tabla1(filepath_f70,filepath_f24,filepath_f73)
    df_tabla2=get_tabla2(filepath_f24)
    df_tabla3=get_tabla3(filepath_f24)
    df_tabla4=get_tabla4(filepath_f24)
    logo_our_team=f"{BASE_DIR}/assets/Logos/URJC_Logo.png"
    if not os.path.exists(logo_our_team):
        print(f"El fichero {logo_our_team} no existe.")
        return None
    _,home_goals,away_goals=get_goals(filepath_f24)

    heatmap_home=Heatmap_one_team("home", filepath_f40, filepath_f24)
    heatmap_away=Heatmap_one_team("away", filepath_f40, filepath_f24)
    passnetwork_home=passnetwork_oneteam(filepath_f27home, filepath_f40,1)
    passnetwork_away=passnetwork_oneteam(filepath_f27away, filepath_f40,1)
    many_paths,total_xg_home,total_xg_away=cercania_porteria_lateral(filepath_f24,filepath_f70,filepath_f73)
    #######################
    #Imagenes

    TEAM_LOGO = logo_our_team

    ##################################
    class ImageFlowable(Flowable):
        def __init__(self, image_path, width, height, x=0, y=0):
            Flowable.__init__(self)
            self.image = Image(image_path, width=width, height=height)
            self.x = x  # Posición X
            self.y = y  # Posición Y
            self.image_width = width  # Guardamos el ancho
            self.image_height = height  # Guardamos la altura

        def draw(self):
            # Coloca la imagen en las coordenadas deseadas
            self.image.drawOn(self.canv, self.x, self.y)

        def wrap(self, availWidth, availHeight):
            # Retorna el tamaño de la imagen que especificamos
            return self.image_width, self.image_height

        def drawOn(self, canv, x, y, _sW=0):
            self.canv = canv
            self.x = x
            self.y = y
            self.image.drawOn(self.canv, self.x, self.y)
    
    """
    Ahora me pongo a hacer la parte del reportlab
    """
    #Aqui lo que hago es inicializar el documento y poner los estilos de las letras
   # print("linea 128 report")
    ppt_size = (12.5 * inch, 8 * inch)

    output_filename=f"{BASE_DIR}/report_gen_match/ReportsGenerados/Report_{home_team}_{away_team}.pdf"
    doc=BaseDocTemplate(output_filename,pagesize=ppt_size,bottomMargin=0,topMargin=45,leftMargin=15,rightMargin=15)
    estiloHoja=getSampleStyleSheet()
    normal_style=estiloHoja["Normal"]
    estiloHoja=getSampleStyleSheet()
    normal_style=estiloHoja["Normal"]

    # Estilos Personalizados
    title_style = ParagraphStyle(
        'Title',
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=36,
        alignment=0,
        spaceAfter=12,
        textColor=HexColor(letter_colors)  
    )
    title_style_center = ParagraphStyle(
        'Title Center',
        fontName='Helvetica-Bold',
        fontSize=40,
        leading=36,
        alignment=1,
        spaceAfter=12,
        textColor=HexColor(letter_colors)  
    )

    subtitle_style = ParagraphStyle(
        'Subtitle',
        fontName='Helvetica',
        fontSize=16,
        leading=20,
        alignment=0,
        spaceAfter=6,
        textColor=HexColor(letter_colors)  # Gris
    )

    data_style = ParagraphStyle(
        'Data',
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        alignment=1,
        textColor=HexColor(letter_colors)  # Gris oscuro
    )
    glossary_style = ParagraphStyle(
        'Data',
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        alignment=0,
        textColor=HexColor(letter_colors)  # Gris oscuro
    )
    #ESTO ES TODO PARA LA PORTADA
    # Función para el Fondo de la Portada
    logo_right_path = f"{BASE_DIR}/assets/Logos/Redes_Logo.png"
    def add_background(canvas, doc):
        #print("Adding background to page", doc.page)
        width,height=doc.pagesize
        canvas.saveState()
        canvas.setFillColor(HexColor(color_selection))  # grey-blue background
        canvas.rect(0, 0, width,height, fill=1, stroke=0)  # Full-page rectangle
        # Logo paths (update with your actual paths)
        
        logo_right_path = f"{BASE_DIR}/assets/Logos/Redes_Logo.png"
        logo_left_path=f"{BASE_DIR}/assets/Logos/URJC_Logo.png"
        # Logo size (adjust as needed)
        logo_width = 75
        logo_height = 75
        logo_width2=64

        # Draw right logo (top-right corner)
        canvas.drawImage(
            logo_right_path,
            x=width - logo_width - 0.3 * inch,
            y=height - logo_height - 0.3 * inch,
            width=logo_width,
           height=logo_height,
           mask='auto'
        )
        
        canvas.drawImage(
            logo_left_path,
            x=width - 2.2*logo_width - 0.3 * inch,
            y=height - logo_height - 0.3 * inch,
            width=logo_width,
           height=logo_height,
           mask='auto'
        )
        
        page_num = canvas.getPageNumber()
        text = f"Página {page_num}"
        canvas.setFont("Helvetica", 10)
        canvas.setFillColorRGB(0, 0, 0)  # Black text
        canvas.drawRightString(width- 0.5 * inch, 0.5 * inch, text)
        
        text="Departamento de Sports Analytics"
        canvas.setFont("Helvetica",10)
        canvas.setFillColorRGB(0, 0, 0)  # Black text
        canvas.drawRightString(2.25 * inch, 0.5 * inch, text)
        
        meses = {
            1: 'enero', 2: 'febrero', 3: 'marzo', 4: 'abril',
            5: 'mayo', 6: 'junio', 7: 'julio', 8: 'agosto',
        9: 'septiembre', 10: 'octubre', 11: 'noviembre', 12: 'diciembre'
        }

        hoy = datetime.date.today()
        fecha_formateada = f"{hoy.day} de {meses[hoy.month]} de {hoy.year}"

        text=f"{fecha_formateada}"
        canvas.setFont("Helvetica",10)
        canvas.setFillColorRGB(0, 0, 0)  # Black text
        canvas.drawRightString(6.75 * inch, 0.5 * inch, text)
        
        rectangle_width=1000
        rectangle_height=6
        x=0
        y=height - logo_height - 0.5 * inch - 4
        canvas.setFillColor(HexColor("#1F5DB5"), alpha=0.5)
        canvas.rect(x, y, rectangle_width/4, rectangle_height, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#3083DC"), alpha=0.5)  
        canvas.rect(x+rectangle_width/4, y, 2*rectangle_width/4, rectangle_height, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#2ab9da"), alpha=0.5)  
        canvas.rect(x+rectangle_width/2, y, 3*rectangle_width/4, rectangle_height, fill=1, stroke=0)
        canvas.setFillColor(HexColor("#96cbe1"), alpha=0.5)  # Second color
        canvas.rect(x+3*rectangle_width/4, y, 4*rectangle_width/4, rectangle_height, fill=1, stroke=0)


        canvas.restoreState()
        

    # Creación de la Portada
    def create_front_page(canvas, doc):
        add_background(canvas, doc)
        canvas.saveState()
        # Líneas decorativas
        canvas.setStrokeColor(HexColor(letter_colors))
        canvas.setLineWidth(1)
        # page_num = canvas.getPageNumber()
        # text = f"Page {page_num}"
        # canvas.setFont("Helvetica", 9)
        # canvas.setFillColorRGB(0, 0, 0)  # Black text
        # canvas.drawRightString(A4[0] - 0.5 * inch, 0.5 * inch, text)
        canvas.restoreState()
    

    # # Elementos de la Portada

    # Estilos
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleCustom',
                                 parent=styles['Title'],
                                 fontSize=34,
                                 alignment=TA_CENTER,
                                 textColor=colors.HexColor("#2B67A2")
                                 )

    subtitle_style = ParagraphStyle('SubtitleCustom',
                                parent=styles['Normal'],
                                fontSize=22,
                                alignment=TA_CENTER,
                                textColor=colors.HexColor("#2B67A2")
                                )

    footer_style = ParagraphStyle('Footer',
                                  parent=styles['Normal'],
                                  fontSize=16,
                                  alignment=TA_CENTER,
                                  textColor=colors.black
                                  )

    header_style = ParagraphStyle('HeaderSmall',
                                  parent=styles['Normal'],
                                  fontSize=12,
                                  alignment=TA_LEFT,
                                  textColor=colors.HexColor("#2B67A2")
                                  )
    story = []
    title_front = ParagraphStyle('TitleCustom',
                                 parent=styles['Title'],
                                 fontSize=34,
                                 alignment=TA_LEFT,
                                 textColor=colors.white
                                 )
    subtitle_front = ParagraphStyle('SubtitleCustom',
                                parent=styles['Normal'],
                                fontSize=24,
                                alignment=TA_LEFT,
                                textColor=colors.white
                                )
    top_style=ParagraphStyle('TopCustom',
                                parent=styles['Normal'],
                                fontSize=20,
                                alignment=TA_LEFT,
                                textColor=colors.HexColor("#2B67A2")
                                )
    # Fondo azul grande (imitando bloque del título)

    story.append(Paragraph("Departamento de Sports Analytics",top_style))
    story.append(Spacer(0, 2 * inch))
    title_box = Table(
        [["", ""]], colWidths=[ppt_size[0] * 0.85, ppt_size[0] * 0.30], rowHeights=2 * inch
        )
    title_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor("#2B67A2")),  # Azul oscuro
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor("#A9D0E6")),  # Cuadro celeste derecha (simulado)
        ('INNERGRID', (0, 0), (-1, -1), 0, colors.white),
        ('BOX', (0, 0), (-1, -1), 0, colors.white)
        ]))
    story.append(title_box)

    # Título encima del bloque azul
    
    story.append(Spacer(0, -1.7 * inch))
    story.append(Paragraph("Informe Post-Partido", title_front))
    story.append(Spacer(0, 20))
    story.append(Paragraph(f"Partido: {home_team} - {away_team}", subtitle_front))

    # Fecha y pie
    story.append(Spacer(0, 2.5 * inch))
    story.append(Paragraph(f"Informe generado el {time.strftime('%d/%m/%Y')}", header_style))


    #print("linea 365 report")
    estilo_frames1 = ParagraphStyle(
        'BodyText',
        parent=estiloHoja['BodyText'],
        textColor=HexColor("#808080"),  # White text for visibility on dark background
        fontSize=12,
        fontName="Helvetica-Bold",
        alignment=1
    )
    estilo_frames2 = ParagraphStyle(
        'BodyText',
        parent=estiloHoja['BodyText'],
        textColor=HexColor(letter_colors),  # White text for visibility on dark background
        fontSize=12,
        fontName="Helvetica",
        alignment=1
    )
    style_figuras=ParagraphStyle(
        'BodyText',
        parent=estiloHoja['BodyText'],
        textColor=HexColor(letter_colors),  # White text for visibility on dark background
        fontSize=11,
        fontName="Helvetica",
        alignment=1
    )
    

    logo_buffer=1.5*inch
    frame_main = Frame(
        doc.leftMargin,  # Start from left margin
        doc.bottomMargin,  # Start from the bottom
        doc.width,  # Full width of the page
        doc.height-logo_buffer,  # Full height of the page
        id="main_frame"
    )
    #page 2 of report
    frame_main2 = Frame(
        doc.leftMargin,  # Start from left margin
        0,  # Start from the bottom
        doc.width,  # Full width of the page
        doc.height-logo_buffer,
        #doc.height+doc.topMargin,  # Full height of the page
        id="main_frame2"
    )
    #templates for frontpage and main page
    frame_front_page = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='front_page_frame')
    
    template_front_page = PageTemplate(id='front_page', frames=[frame_front_page], onPage=create_front_page)
    template_main = PageTemplate(id='main', frames=[frame_main],onPage=add_background)
    template_main2=PageTemplate(id="main_2",frames=[frame_main2],onPage=add_background)
    template_main3=PageTemplate(id="main_3",frames=[frame_main2],onPage=add_background)
    #aqui ya seguimos con main page

    main_story1=[]
    title_1=ParagraphStyle('Title 1',
                                 fontName='Helvetica',
                                 fontSize=24,
                                 alignment=TA_LEFT,
                                 textColor=colors.HexColor("#2B67A2")
                                 )
    subtitle1=ParagraphStyle('Subtitle 1',
                                 parent=styles['Heading2'],
                                 fontName='Helvetica',
                                 fontSize=20,
                                 alignment=TA_LEFT,
                                 textColor=colors.HexColor("#2B67A2")
                                 )
    
    #main_story1.append(Spacer(0,5))
    main_story1.append(Paragraph("Aspectos Destacados del Rival",title_1))
    main_story1.append(Paragraph(f"{home_team} - {away_team}",subtitle1))
    main_story1.append(Spacer(0,7))
    main_story1.append(Paragraph("Notas:",subtitle1))
    main_story1.append(Spacer(0,7))
    #BLUE BOX
    rectangle_width = 800  # Adjust width
    rectangle_height = 350  # Adjust height

    blue_box = Table([[""]], colWidths=rectangle_width, rowHeights=rectangle_height,hAlign="CENTER")
    blue_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.lightblue),
        ("BOX", (0, 0), (-1, -1), 0, colors.white),  # Optional: remove border
        ]))
    main_story1.append(blue_box)
    
    main_story111=[]
    main_story111.append(Spacer(0,5))
    main_story111.append(Paragraph("Estadísticas Globales",title_1))
    main_story111.append(Paragraph(f"Goles, ocasiones, goles esperados, pases completados y acciones defensivas",subtitle1))
    main_story111.append(Spacer(0,20))
    styles = getSampleStyleSheet()
    normal_big = ParagraphStyle('normal_big', parent=styles['Normal'], fontSize=18, leading=16,alignment=1)
    data = []
    for row in [df_tabla1.columns.tolist()] + df_tabla1.values.tolist():
        data.append([Paragraph(str(cell), normal_big) for cell in row])




    table = Table(data)

    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), HexColor("#C7D9F0")),  # encabezado gris
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('VALIGN',(0,0),(-1,-1),'CENTER'),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor("#E8EEF7")]),
        ('FONTSIZE',(0,0),(-1,0),18),
        ('FONTSIZE',(0,1),(-1,-1),16),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ])
    table.setStyle(style)
    main_story111.append(table)
    
    main_story112=[]
    main_story112.append(Spacer(0,5))
    main_story112.append(Paragraph("Estadísticas Globales",title_1))
    main_story112.append(Paragraph(f"Pases por Acción Defensiva (PPDAs) y faltas cometidas",subtitle1))
    main_story112.append(Spacer(0,20))
    
    data2=[]
    for row in [df_tabla2.columns.tolist()] + df_tabla2.values.tolist():
        data2.append([Paragraph(str(cell), normal_big) for cell in row])

    table2 = Table(data2)
    table2.setStyle(style)
    main_story112.append(table2)
    
    main_story113=[]
    main_story113.append(Spacer(0,5))
    main_story113.append(Paragraph("Estadísticas Globales",title_1))
    main_story113.append(Paragraph(f"Pases cortados y entradas",subtitle1))
    main_story113.append(Spacer(0,20))
    
    data3=[]
    for row in [df_tabla3.columns.tolist()] + df_tabla3.values.tolist():
        data3.append([Paragraph(str(cell), normal_big) for cell in row])

    table3 = Table(data3)

    table3.setStyle(style)
    main_story113.append(table3)
    
    main_story114=[]
    main_story114.append(Spacer(0,5))
    main_story114.append(Paragraph("Estadísticas Globales",title_1))
    main_story114.append(Paragraph(f"Despejes y bloqueos de balón",subtitle1))
    main_story114.append(Spacer(0,20))
    
    data4=[]
    for row in [df_tabla4.columns.tolist()] + df_tabla4.values.tolist():
        data4.append([Paragraph(str(cell), normal_big) for cell in row])

    table4 = Table(data4)

    table4.setStyle(style)
    main_story114.append(table4)

    
    main_story2=[]
    
    main_story2.append(Paragraph("Informe de Partidos",title_1))
    main_story2.append(Paragraph(f"{home_team} - {away_team}",subtitle1))
    main_story2.append(Spacer(0,200))
    main_story2.append(Paragraph("VARIABLES DE EQUIPO",title_style_center))
    
    #home heatmap
    main_story3=[]
    main_story3.append(Spacer(0,5))
    main_story3.append(Paragraph("Mapas de calor",title_1))
    main_story3.append(Paragraph(f"Mapa de calor {home_team} (local)",subtitle1))
    main_story3.append(Spacer(0,20))
    heatmap_home=Image(heatmap_home,width=502,height=380)
    heatmap_home.hAlign="CENTER"
    main_story3.append(heatmap_home)
    main_story3.append(Paragraph("<font color='blue'> Figura 1. </font>  Mapa de calor basado en todos los eventos registrados durante el partido.",style_figuras))
    
    #away heatmap
    main_story4=[]
    main_story4.append(Spacer(0,5))
    main_story4.append(Paragraph("Mapas de calor",title_1))
    main_story4.append(Paragraph(f"Mapa de calor {away_team} (visitante)",subtitle1))
    main_story4.append(Spacer(0,20))
    heatmap_away=Image(heatmap_away,width=502,height=380)
    heatmap_away.hAlign="CENTER"
    main_story4.append(heatmap_away)
    main_story4.append(Paragraph("<font color='blue'> Figura 2. </font>  Mapa de calor basado en todos los eventos registrados durante el partido.",style_figuras))
    
    #red pases home
    main_story5=[]
    main_story5.append(Spacer(0,5))
    main_story5.append(Paragraph("Red de pases",title_1))
    main_story5.append(Paragraph(f"Red de pases entre jugadores {home_team} (local)",subtitle1))
    main_story5.append(Spacer(0,20))
    passnetwork_home=Image(passnetwork_home,width=476,height=375)
    passnetwork_home.hAlign="CENTER"
    main_story5.append(passnetwork_home)
    main_story5.append(Paragraph("<font color='blue'> Figura 4. </font>  Relación entre jugadores a través de los pases. Las flechas representan el número de pases (se muestran solo si son al menos 7) y su grosor es proporcional a esa cantidad. El tamaño de los círculos refleja la importancia de cada jugador. La posición de cada jugador corresponde al promedio de las posiciones de sus pases.",style_figuras))
    
    #red pases away
    main_story6=[]
    main_story6.append(Spacer(0,5))
    main_story6.append(Paragraph("Red de pases",title_1))
    main_story6.append(Paragraph(f"Red de pases entre jugadores {away_team} (visitante)",subtitle1))
    main_story6.append(Spacer(0,20))
    passnetwork_away=Image(passnetwork_away,width=476,height=375)
    passnetwork_away.hAlign="CENTER"
    main_story6.append(passnetwork_away)
    main_story6.append(Paragraph("<font color='blue'> Figura 5. </font>  Relación entre jugadores a través de los pases. Las flechas representan el número de pases (se muestran solo si son al menos 7) y su grosor es proporcional a esa cantidad. El tamaño de los círculos refleja la importancia de cada jugador. La posición de cada jugador corresponde al promedio de las posiciones de sus pases.",style_figuras))
    
    ### aqui irian 3 más para cada equipo que serían por zonas
    
    #cercania porteria rival
    main_story7=[]
    main_story7.append(Spacer(0,5))
    main_story7.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story7.append(Paragraph("Cercanía de la red de pases respecto a la portería rival",subtitle1))
    main_story7.append(Spacer(0,20))
    cercania_red=Image(many_paths[0],width=659,height=350)
    cercania_red.hAlign="CENTER"
    main_story7.append(cercania_red)
    main_story7.append(Paragraph("<font color='blue'> Figura 6. </font> Posición promedio de los jugadores durante el partido, para ambos equipos, en relación con la portería rival. Cada punto corresponde al promedio de 30 pases.",style_figuras))
    
    #lateralidad 
    main_story8=[]
    main_story8.append(Spacer(0,5))
    main_story8.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story8.append(Paragraph("Posición lateral promedio de la red de pases",subtitle1))
    main_story8.append(Spacer(0,20))
    lateralidad_red=Image(many_paths[1],width=659,height=350)
    lateralidad_red.hAlign="CENTER"
    main_story8.append(lateralidad_red)
    main_story8.append(Paragraph("<font color='blue'> Figura 7. </font> Posición lateral promedio durante el partido (izquierda/derecha), para ambos equipos. Cada punto corresponde al promedio de 30 pases.",style_figuras))
    
    
    #pases acumulados 
    main_story9=[]
    main_story9.append(Spacer(0,5))
    main_story9.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story9.append(Paragraph("Número de pases acumulados por cada equipo",subtitle1))
    main_story9.append(Spacer(0,20))
    pases_acumulados=Image(many_paths[2],width=659,height=350)
    pases_acumulados.hAlign="CENTER"
    main_story9.append(pases_acumulados)
    main_story9.append(Paragraph("<font color='blue'> Figura 8. </font> Número de pases acumulados por cada equipo. Inset: Diferencia en el número de pases (local - visitante).",style_figuras))
    
    
    #ritmo de juego
    main_story10=[]
    main_story10.append(Spacer(0,5))
    main_story10.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story10.append(Paragraph("Ritmo de juego de cada equipo (velocidad del balón)",subtitle1))
    main_story10.append(Spacer(0,20))
    ritmo_juego=Image(many_paths[5],width=659,height=350)
    ritmo_juego.hAlign="CENTER"
    main_story10.append(ritmo_juego)
    main_story10.append(Paragraph("<font color='blue'> Figura 9. </font> Ritmo de juego medido como la velocidad del balón en metros por segundo. Las líneas horizontales indican la media de cada equipo.",style_figuras))
    
    #long passchains
    main_story11=[]
    main_story11.append(Spacer(0,5))
    main_story11.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story11.append(Paragraph("Longitud de las jugadas en número de pases.",subtitle1))
    main_story11.append(Spacer(0,20))
    long_jugadas=Image(many_paths[6],width=659,height=350)
    long_jugadas.hAlign="CENTER"
    main_story11.append(long_jugadas)
    main_story11.append(Paragraph("<font color='blue'> Figura 10. </font> Longitud de las jugadas en número de pases. Promedio de 15 jugadas. Las líneas horizontales indican la media de cada equipo.",style_figuras))
    
    #acc defensivas acumuladas
    main_story12=[]
    main_story12.append(Spacer(0,5))
    main_story12.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story12.append(Paragraph("Número de acciones defensivas acumuladas: Faltas, tackles, pases cortados y challenges",subtitle1))
    main_story12.append(Spacer(0,20))
    acc_def_acumuladas=Image(many_paths[3],width=659,height=350)
    acc_def_acumuladas.hAlign="CENTER"
    main_story12.append(acc_def_acumuladas)
    main_story12.append(Paragraph("<font color='blue'> Figura 11. </font> Acciones defensivas acumuladas: Faltas cometidas, tackles (entradas), pases cortados y challenges (robos no conseguidos).",style_figuras))
    
    #acc defensivas altura
    main_story13=[]
    main_story13.append(Spacer(0,5))
    main_story13.append(Paragraph("Evolución a lo largo del partido",title_1))
    main_story13.append(Paragraph("Posición promedio de las acciones defensivas acumuladas",subtitle1))
    main_story13.append(Spacer(0,20))
    acc_def_altura=Image(many_paths[4],width=659,height=350)
    acc_def_altura.hAlign="CENTER"
    main_story13.append(acc_def_altura)
    main_story13.append(Paragraph("<font color='blue'> Figura 12. </font> Posición promedio de las 10 últimas acciones defensivas: Faltas cometidas, tackles (entradas), pases cortados y challenges (robos no conseguidos).",style_figuras))
    
    #xG evolution
    main_story14=[]
    main_story14.append(Spacer(0,5))
    main_story14.append(Paragraph("Goles Esperados",title_1))
    main_story14.append(Paragraph("Goles esperados durante el partido",subtitle1))
    main_story14.append(Spacer(0,20))
    xG_evol=Image(many_paths[7],width=659,height=350)
    xG_evol.hAlign="CENTER"
    main_story14.append(xG_evol)
    main_story14.append(Paragraph("<font color='blue'> Figura 13. </font> Evolución de los goles esperados (xG) de ambos equipos. Tiempo en minutos.",style_figuras))
    
    #xG evolution
    main_story15=[]
    main_story15.append(Spacer(0,5))
    main_story15.append(Paragraph("Goles Esperados",title_1))
    main_story15.append(Paragraph("Posición en el campo de las ocaciones de gol (xG)",subtitle1))
    main_story15.append(Spacer(0,20))
    xG_positions=Image(many_paths[8],width=539,height=350)
    xG_positions.hAlign="CENTER"
    main_story15.append(xG_positions)
    main_story15.append(Paragraph("<font color='blue'> Figura 14. </font> Posición en el campo de los goles esperados (xG) de ambos equipos. En verde, ocasiones marcadas.",style_figuras))

    #xG goalmouth
    main_story16=[]
    main_story16.append(Spacer(0,5))
    main_story16.append(Paragraph("Goles Esperados",title_1))
    main_story16.append(Paragraph("Finalización de las ocaciones de gol (xG): Tiros a puerta",subtitle1))
    main_story16.append(Spacer(0,20))
    xG_positions=Image(many_paths[9],width=382,height=380)
    xG_positions.hAlign="CENTER"
    main_story16.append(xG_positions)
    main_story16.append(Paragraph("<font color='blue'> Figura 15. </font> Goles esperados (xG) de ambos equipos: Localización de los tiros a puerta. En rojo, ocasiones marcadas.",style_figuras))
    
    main_story31=[]
    main_story31.append(Spacer(0,5))
    main_story31.append(Paragraph("Análisis de Rival",title_1))
    main_story31.append(Paragraph(f"{home_team}",subtitle1))
    main_story31.append(Spacer(0,30))
    

    
    style_despedida=ParagraphStyle(
        'BodyText',
        parent=estiloHoja['Title'],
        textColor=HexColor("#000000"), 
        fontSize=24,
        fontName="Helvetica-Bold",
        alignment=1
    )
    
    text_despedida="Departamento de Sports Analytics"
    main_story31.append(Paragraph(text_despedida,style_despedida))
    main_story31.append(Spacer(0,5))
    logo_fuenla=Image(logo_right_path,width=303,height=303)
    logo_fuenla.hAlign="CENTER"
    main_story31.append(logo_fuenla)
    #print("linea 920 report")
    
    doc.addPageTemplates([template_front_page, template_main,template_main2,template_main3])
    
    full_Story = ( 
        story + [PageBreak()] +
        main_story1 + [PageBreak()] +
        main_story111 + [PageBreak()] +
        main_story112 + [PageBreak()] +
        main_story113 + [PageBreak()] +
        main_story114 + [PageBreak()] +
        main_story2 + [PageBreak()] +
        main_story3 + [PageBreak()] +
        main_story4 + [PageBreak()] +
        main_story5 + [PageBreak()] +
        main_story6 + [PageBreak()] +
        main_story7 + [PageBreak()] +
        main_story8 + [PageBreak()] +
        main_story9 + [PageBreak()] +
        main_story10 + [PageBreak()] +
        main_story11 + [PageBreak()] +
        main_story12 + [PageBreak()] +
        main_story13 + [PageBreak()] +
        main_story14 + [PageBreak()] +
        main_story15 + [PageBreak()] +
        main_story16+ [PageBreak()] +
        main_story31+ [PageBreak()] 
        )


    #print("linea 968 report")
    doc.build(
        full_Story
    )
    #print("linea 972 report")
    heatmap_home=Heatmap_one_team("home", filepath_f40, filepath_f24)
    heatmap_away=Heatmap_one_team("away", filepath_f40, filepath_f24)
    passnetwork_home=passnetwork_oneteam(filepath_f27home, filepath_f40,1)
    passnetwork_away=passnetwork_oneteam(filepath_f27away, filepath_f40,1)
    images_to_delete = [heatmap_home,heatmap_away,passnetwork_home,passnetwork_away]+many_paths
    #print(image_files)
    for image_file in images_to_delete:
        #print("linea 976 report")
        try:
            os.remove(image_file)
        except Exception as e:
            print(f"Error deleting {image_file}: {e}")
    print("PDF generated successfully!")
    
    
  

if __name__ == "__main__":
    #print("ENTRAMOS BIEN")
    parser = argparse.ArgumentParser()
    parser.add_argument("--home_team", type=str, required=True)
    parser.add_argument("--away_team", type=str, required=True)

    parser.add_argument("--filepath_f40", type=str, required=True)
    parser.add_argument("--filepath_f24", type=str, required=True)
    parser.add_argument("--filepath_f70", type=str, required=True)
    parser.add_argument("--filepath_f73", type=str, required=True)
    parser.add_argument("--filepath_f27home", type=str, required=True)
    parser.add_argument("--filepath_f27away", type=str, required=True)

    
    parser.add_argument("--color_selection", type=str, default="#FFFFFF")


    args = parser.parse_args()
    create_report(home_team=args.home_team,
                  away_team=args.away_team,
                  filepath_f40=args.filepath_f40,
                  filepath_f24=args.filepath_f24,
                  filepath_f70=args.filepath_f70,
                  filepath_f73=args.filepath_f73,
                  filepath_f27home=args.filepath_f27home,
                  filepath_f27away=args.filepath_f27away,
                  color_selection="#FFFFFF"
    )



# create_report("Real Sociedad Femenino","Levante Badalona Femenino","/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f40/f40-squad-102.xml","/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f24/f24-903-2024-2482803-eventdetails.xml",
#               "/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f70/f70-903-2024-2482803-expectedgoals.xml","/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f27/pass_matrix_903_2024_g2482803_t13324.xml",
#               "/Users/julieta/Desktop/APP_Generic_Femeni/data_femeni/raw/f27/pass_matrix_903_2024_g2482803_t18643.xml",color_selection="#FFFFFF")
# #create_report("UD Sanse","/Users/julieta/Desktop/APP_Generic/report_gen_teams/datos_equipos","/Users/julieta/Desktop/APP_Generic/report_gen_teams/wyscout_report",color_selection="#FFFFFF")