# dashboard/dashboard_generator.py
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import dash
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State
import json
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import IsolationForest
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
import webbrowser
import threading
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DashboardGenerator:
    """Generador de dashboard web interactivo para visualizar resultados del análisis"""
    
    def __init__(self, output_folder, line, analysis_type, port=8050):
        self.output_folder = output_folder
        self.line = line
        self.analysis_type = analysis_type
        self.port = port
        self.dataframes = {}
        self.app = None
        self.server_thread = None
        self.running = False
        
        # Colores para las gráficas
        self.colors = {
            'background': '#F0F2F6',
            'card_background': '#FFFFFF',
            'primary': '#2C3E50',
            'secondary': '#3498DB',
            'success': '#2ECC71',
            'info': '#3498DB',
            'warning': '#F39C12',
            'danger': '#E74C3C',
            'text': '#2C3E50'
        }
        
        self.line_colors = {
            'L1': '#FF0000',  # Rojo
            'L2': '#FFCC00',  # Amarillo
            'L4': '#0066CC',  # Azul
            'L4A': '#9900CC',  # Morado
            'L5': '#009933'   # Verde
        }
    
    def load_data(self):
        """Cargar datos desde los archivos CSV generados"""
        try:
            if self.analysis_type == "CDV":
                # Cargar archivos CDV
                fo_file_path = os.path.join(self.output_folder, f'df_{self.line}_FO_Mensual.csv')
                fl_file_path = os.path.join(self.output_folder, f'df_{self.line}_FL_Mensual.csv')
                ocup_file_path = os.path.join(self.output_folder, f'df_{self.line}_OCUP_Mensual.csv')
                main_file_path = os.path.join(self.output_folder, f'df_{self.line}_CDV.csv')
                
                if os.path.exists(fo_file_path):
                    self.dataframes['fallos_ocupacion'] = pd.read_csv(fo_file_path)
                    # Convertir fechas
                    if 'Fecha Hora' in self.dataframes['fallos_ocupacion'].columns:
                        self.dataframes['fallos_ocupacion']['Fecha Hora'] = pd.to_datetime(
                            self.dataframes['fallos_ocupacion']['Fecha Hora'], errors='coerce')
                
                if os.path.exists(fl_file_path):
                    self.dataframes['fallos_liberacion'] = pd.read_csv(fl_file_path)
                    # Convertir fechas
                    if 'Fecha Hora' in self.dataframes['fallos_liberacion'].columns:
                        self.dataframes['fallos_liberacion']['Fecha Hora'] = pd.to_datetime(
                            self.dataframes['fallos_liberacion']['Fecha Hora'], errors='coerce')
                
                if os.path.exists(ocup_file_path):
                    self.dataframes['ocupaciones'] = pd.read_csv(ocup_file_path)
                    # Convertir fechas
                    if 'Fecha' in self.dataframes['ocupaciones'].columns:
                        self.dataframes['ocupaciones']['Fecha'] = pd.to_datetime(
                            self.dataframes['ocupaciones']['Fecha'], errors='coerce')
                
                if os.path.exists(main_file_path):
                    self.dataframes['main'] = pd.read_csv(main_file_path)
                    # Convertir fechas
                    if 'Fecha Hora' in self.dataframes['main'].columns:
                        self.dataframes['main']['Fecha Hora'] = pd.to_datetime(
                            self.dataframes['main']['Fecha Hora'], errors='coerce')
                
            elif self.analysis_type == "ADV":
                # Cargar archivos ADV
                disc_file_path = os.path.join(self.output_folder, f'df_{self.line}_ADV_DISC_Mensual.csv')
                mov_file_path = os.path.join(self.output_folder, f'df_{self.line}_ADV_MOV_Mensual.csv')
                
                if os.path.exists(disc_file_path):
                    self.dataframes['discordancias'] = pd.read_csv(disc_file_path)
                    # Convertir fechas
                    if 'Fecha Hora' in self.dataframes['discordancias'].columns:
                        self.dataframes['discordancias']['Fecha Hora'] = pd.to_datetime(
                            self.dataframes['discordancias']['Fecha Hora'], dayfirst=True, errors='coerce')
                
                if os.path.exists(mov_file_path):
                    self.dataframes['movimientos'] = pd.read_csv(mov_file_path)
                    # Convertir fechas
                    if 'Fecha' in self.dataframes['movimientos'].columns:
                        self.dataframes['movimientos']['Fecha'] = pd.to_datetime(
                            self.dataframes['movimientos']['Fecha'], errors='coerce')
            
            logger.info(f"Datos cargados exitosamente para {self.line} - {self.analysis_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error al cargar los datos: {str(e)}")
            return False
    
    def generate_insights(self):
        """Generar insights y recomendaciones basadas en el análisis de datos"""
        insights = {
            'recomendaciones': [],
            'patrones_detectados': [],
            'anomalias': [],
            'resumen': {}
        }
        
        try:
            if self.analysis_type == "CDV":
                if 'fallos_ocupacion' in self.dataframes and not self.dataframes['fallos_ocupacion'].empty:
                    # Analizar fallos de ocupación
                    fo_df = self.dataframes['fallos_ocupacion']
                    
                    # Agrupar por equipo para encontrar los más problemáticos
                    problematic_equip = fo_df.groupby('Equipo').size().sort_values(ascending=False)
                    
                    if not problematic_equip.empty:
                        # Top 5 equipos con más fallos
                        top_equipos = problematic_equip.head(5).index.tolist()
                        insights['resumen']['top_equipos_fallos_ocupacion'] = top_equipos
                        
                        # Recomendaciones basadas en los equipos más problemáticos
                        for equipo in top_equipos[:3]:  # Top 3 para recomendaciones específicas
                            insights['recomendaciones'].append(
                                f"Realizar inspección y mantenimiento prioritario del CDV: {equipo} debido a alta frecuencia de fallos de ocupación."
                            )
                    
                    # Detección de patrones temporales
                    if 'Fecha Hora' in fo_df.columns:
                        fo_df['hora'] = fo_df['Fecha Hora'].dt.hour
                        hour_distribution = fo_df['hora'].value_counts().sort_index()
                        
                        # Detectar horas pico de fallos
                        peak_hours = hour_distribution[hour_distribution > hour_distribution.mean() + hour_distribution.std()].index.tolist()
                        if peak_hours:
                            insights['patrones_detectados'].append(
                                f"Se detectan más fallos de ocupación durante las horas: {', '.join(map(str, peak_hours))}"
                            )
                            insights['recomendaciones'].append(
                                f"Programar inspecciones adicionales durante las horas pico de fallos: {', '.join(map(str, peak_hours))}"
                            )
                
                if 'fallos_liberacion' in self.dataframes and not self.dataframes['fallos_liberacion'].empty:
                    # Analizar fallos de liberación
                    fl_df = self.dataframes['fallos_liberacion']
                    
                    # Agrupar por equipo para encontrar los más problemáticos
                    problematic_equip_fl = fl_df.groupby('Equipo').size().sort_values(ascending=False)
                    
                    if not problematic_equip_fl.empty:
                        # Top 5 equipos con más fallos de liberación
                        top_equipos_fl = problematic_equip_fl.head(5).index.tolist()
                        insights['resumen']['top_equipos_fallos_liberacion'] = top_equipos_fl
                        
                        # Recomendaciones basadas en los equipos más problemáticos
                        for equipo in top_equipos_fl[:3]:  # Top 3 para recomendaciones específicas
                            insights['recomendaciones'].append(
                                f"Programar ajuste de sensibilidad para el CDV: {equipo} debido a fallos recurrentes de liberación."
                            )
                
                # Análisis conjunto para equipos con ambos tipos de fallos
                if 'fallos_ocupacion' in self.dataframes and 'fallos_liberacion' in self.dataframes:
                    fo_equipos = set(self.dataframes['fallos_ocupacion']['Equipo'].unique())
                    fl_equipos = set(self.dataframes['fallos_liberacion']['Equipo'].unique())
                    
                    common_equipos = fo_equipos.intersection(fl_equipos)
                    if common_equipos:
                        insights['resumen']['equipos_con_ambos_fallos'] = list(common_equipos)
                        insights['recomendaciones'].append(
                            f"Considerar reemplazo preventivo de los CDVs con ambos tipos de fallos: {', '.join(list(common_equipos)[:3])}"
                        )
                
                # Análisis de tendencias recientes
                if 'ocupaciones' in self.dataframes and not self.dataframes['ocupaciones'].empty:
                    ocup_df = self.dataframes['ocupaciones']
                    
                    # Convertir Count a numérico si es string
                    if 'Count' in ocup_df.columns and ocup_df['Count'].dtype == 'object':
                        ocup_df['Count'] = pd.to_numeric(ocup_df['Count'], errors='coerce')
                    
                    # Analizar tendencias por día de la semana
                    if 'Fecha' in ocup_df.columns:
                        ocup_df['dia_semana'] = ocup_df['Fecha'].dt.day_name()
                        day_avg = ocup_df.groupby('dia_semana')['Count'].mean().sort_values(ascending=False)
                        
                        insights['resumen']['dia_mayor_ocupacion'] = day_avg.index[0] if not day_avg.empty else "No disponible"
                        insights['patrones_detectados'].append(
                            f"El día con mayor promedio de ocupaciones es {day_avg.index[0] if not day_avg.empty else 'No disponible'}"
                        )
            
            elif self.analysis_type == "ADV":
                if 'discordancias' in self.dataframes and not self.dataframes['discordancias'].empty:
                    # Analizar discordancias
                    disc_df = self.dataframes['discordancias']
                    
                    # Contar discordancias por equipo
                    if 'Equipo Estacion' in disc_df.columns:
                        disc_count = disc_df['Equipo Estacion'].value_counts().head(5)
                        top_disc_equipos = disc_count.index.tolist()
                        
                        insights['resumen']['top_equipos_discordancias'] = top_disc_equipos
                        insights['recomendaciones'].append(
                            f"Realizar verificación prioritaria de los mecanismos de las agujas: {', '.join(top_disc_equipos[:3])}"
                        )
                
                if 'movimientos' in self.dataframes and not self.dataframes['movimientos'].empty:
                    # Analizar movimientos
                    mov_df = self.dataframes['movimientos']
                    
                    # Convertir Count a numérico si es string
                    if 'Count' in mov_df.columns and mov_df['Count'].dtype == 'object':
                        mov_df['Count'] = pd.to_numeric(mov_df['Count'], errors='coerce')
                    
                    # Identificar agujas con mayor movimiento
                    if 'Equipo' in mov_df.columns and 'Count' in mov_df.columns:
                        mov_count = mov_df.groupby('Equipo')['Count'].sum().sort_values(ascending=False)
                        top_mov_equipos = mov_count.head(5).index.tolist()
                        
                        insights['resumen']['top_equipos_movimientos'] = top_mov_equipos
                        insights['recomendaciones'].append(
                            f"Programar lubricación y mantenimiento preventivo para las agujas con mayor uso: {', '.join(top_mov_equipos[:3])}"
                        )
                        
                        # Recomendación de mantenimiento predictivo
                        insights['recomendaciones'].append(
                            "Implementar plan de lubricación semanal para las agujas con más de 100 movimientos por día"
                        )
            
            # Generar recomendaciones generales basadas en el tipo de análisis
            if self.analysis_type == "CDV":
                insights['recomendaciones'].append(
                    "Establecer un programa de inspección visual mensual para los CDVs con mayor frecuencia de fallos"
                )
                insights['recomendaciones'].append(
                    "Implementar un protocolo de limpieza trimestral para los circuitos de vía en estaciones con mayor tráfico"
                )
            elif self.analysis_type == "ADV":
                insights['recomendaciones'].append(
                    "Establecer un programa de inspección y lubricación preventiva para agujas con más de 50 movimientos diarios"
                )
                insights['recomendaciones'].append(
                    "Verificar mensualmente la calibración de los sistemas de detección en agujas con discordancias recurrentes"
                )
            
            logger.info(f"Insights generados exitosamente para {self.line} - {self.analysis_type}")
            return insights
            
        except Exception as e:
            logger.error(f"Error al generar insights: {str(e)}")
            # Devolver insights básicos en caso de error
            return insights
    
    def detect_anomalies(self, df, column, contamination=0.05):
        """Detectar anomalías utilizando Isolation Forest"""
        try:
            if df.empty or column not in df.columns:
                return pd.Series([False] * len(df))
            
            # Convertir a numérico si es necesario
            if df[column].dtype == 'object':
                df[column] = pd.to_numeric(df[column], errors='coerce')
            
            # Preparar datos para el modelo
            X = df[column].values.reshape(-1, 1)
            
            # Aplicar Isolation Forest
            model = IsolationForest(contamination=contamination, random_state=42)
            preds = model.fit_predict(X)
            
            # -1 para anomalías, 1 para inliers
            return pd.Series(preds == -1, index=df.index)
            
        except Exception as e:
            logger.error(f"Error al detectar anomalías: {str(e)}")
            return pd.Series([False] * len(df))
    
    def create_dashboard(self):
        """Crear y configurar el dashboard web"""
        if not self.dataframes:
            logger.error("No hay datos cargados para generar el dashboard")
            return False
        
        try:
            # Generar insights
            insights = self.generate_insights()
            
            # Crear aplicación Dash
            self.app = dash.Dash(__name__, suppress_callback_exceptions=True)
            
            # Estilo CSS para el dashboard
            external_stylesheets = [
                'https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css'
            ]
            
            # Definir el layout del dashboard
            self.app.layout = html.Div(style={'backgroundColor': self.colors['background'], 'minHeight': '100vh'}, children=[
                # Header
                html.Div(style={'backgroundColor': self.colors['primary'], 'color': 'white', 'padding': '20px', 'marginBottom': '20px'}, children=[
                    html.H2(f"Dashboard de Análisis - {self.line} {self.analysis_type}", style={'textAlign': 'center'}),
                    html.P(f"Fecha de generación: {datetime.now().strftime('%d-%m-%Y %H:%M')}", style={'textAlign': 'center'})
                ]),
                
                # Contenedor principal
                html.Div(className='container', children=[
                    # Fila de KPIs
                    html.Div(className='row mb-4', children=[
                        self.create_kpi_cards()
                    ]),
                    
                    # Fila de gráficos principales
                    html.Div(className='row mb-4', children=[
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Tendencia Temporal", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    dcc.Graph(id='time-trend-graph', figure=self.create_time_trend_figure())
                                ])
                            ])
                        ]),
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Distribución por Equipo", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    dcc.Graph(id='equipment-distribution', figure=self.create_equipment_distribution_figure())
                                ])
                            ])
                        ])
                    ]),
                    
                    # Fila de filtros y controles
                    html.Div(className='row mb-4', children=[
                        html.Div(className='col-md-12', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Filtros y Controles", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    html.Div(className='row', children=[
                                        html.Div(className='col-md-4', children=[
                                            html.Label("Rango de Fechas:"),
                                            dcc.DatePickerRange(
                                                id='date-range',
                                                min_date_allowed=self.get_min_date(),
                                                max_date_allowed=self.get_max_date(),
                                                start_date=self.get_min_date(),
                                                end_date=self.get_max_date()
                                            ),
                                        ]),
                                        html.Div(className='col-md-4', children=[
                                            html.Label("Equipo:"),
                                            dcc.Dropdown(
                                                id='equipment-filter',
                                                options=[{'label': equipo, 'value': equipo} for equipo in self.get_equipment_list()],
                                                multi=True,
                                                placeholder="Seleccionar equipos..."
                                            ),
                                        ]),
                                        html.Div(className='col-md-4', children=[
                                            html.Label("Tipo de Visualización:"),
                                            dcc.RadioItems(
                                                id='visualization-type',
                                                options=[
                                                    {'label': 'Diario', 'value': 'daily'},
                                                    {'label': 'Semanal', 'value': 'weekly'},
                                                    {'label': 'Mensual', 'value': 'monthly'}
                                                ],
                                                value='daily',
                                                labelStyle={'display': 'block'}
                                            ),
                                        ])
                                    ]),
                                    html.Div(className='row mt-3', children=[
                                        html.Div(className='col-md-12 text-center', children=[
                                            html.Button('Aplicar filtros', id='apply-filters-button', className='btn btn-primary', style={
                                                'backgroundColor': self.colors['secondary'],
                                                'color': 'white',
                                                'fontWeight': 'bold',
                                                'padding': '10px 20px',
                                                'border': 'none',
                                                'borderRadius': '5px',
                                                'cursor': 'pointer'
                                            }),
                                        ])
                                    ])
                                ])
                            ])
                        ])
                    ]),
                    
                    # Fila de gráficos adicionales
                    html.Div(className='row mb-4', children=[
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Distribución Horaria", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    dcc.Graph(id='hourly-distribution', figure=self.create_hourly_distribution_figure())
                                ])
                            ])
                        ]),
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Mapa de Calor", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    dcc.Graph(id='heatmap', figure=self.create_heatmap_figure())
                                ])
                            ])
                        ])
                    ]),
                    
                    # Fila de recomendaciones y análisis
                    html.Div(className='row mb-4', children=[
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header bg-info text-white', children=[
                                    html.H5("Recomendaciones de Mantenimiento", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    html.Ul([html.Li(rec) for rec in insights['recomendaciones']])
                                ])
                            ])
                        ]),
                        html.Div(className='col-md-6', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header bg-warning', children=[
                                    html.H5("Patrones Detectados", className='card-title')
                                ]),
                                html.Div(className='card-body', children=[
                                    html.Ul([html.Li(pat) for pat in insights['patrones_detectados']]) if insights['patrones_detectados'] else html.P("No se detectaron patrones significativos")
                                ])
                            ])
                        ])
                    ]),
                    
                    # Fila para tabla de datos
                    html.Div(className='row mb-4', children=[
                        html.Div(className='col-md-12', children=[
                            html.Div(className='card', style={'backgroundColor': self.colors['card_background']}, children=[
                                html.Div(className='card-header', children=[
                                    html.H5("Datos Detallados", className='card-title')
                                ]),
                                html.Div(className='card-body', style={'overflowX': 'auto'}, children=[
                                    self.create_data_table()
                                ])
                            ])
                        ])
                    ])
                ])
            ])
            
            # Configurar callbacks
            self.setup_callbacks()
            
            logger.info(f"Dashboard creado exitosamente para {self.line} - {self.analysis_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error al crear el dashboard: {str(e)}")
            return False
    
    def create_kpi_cards(self):
        """Crear tarjetas de KPI según el tipo de análisis"""
        kpi_cards = []
        
        try:
            if self.analysis_type == "CDV":
                # KPIs para CDV
                
                # Total de fallos de ocupación
                total_fo = len(self.dataframes.get('fallos_ocupacion', pd.DataFrame()))
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-danger mb-3', children=[
                            html.Div(className='card-header', children=["Fallos de Ocupación"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{total_fo}", className='card-title'),
                                html.P("Total de fallos detectados", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Total de fallos de liberación
                total_fl = len(self.dataframes.get('fallos_liberacion', pd.DataFrame()))
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-warning mb-3', children=[
                            html.Div(className='card-header', children=["Fallos de Liberación"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{total_fl}", className='card-title'),
                                html.P("Total de fallos detectados", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Total de equipos afectados
                equipos_fo = set(self.dataframes.get('fallos_ocupacion', pd.DataFrame()).get('Equipo', pd.Series()).unique())
                equipos_fl = set(self.dataframes.get('fallos_liberacion', pd.DataFrame()).get('Equipo', pd.Series()).unique())
                total_equipos = len(equipos_fo.union(equipos_fl))
                
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-primary mb-3', children=[
                            html.Div(className='card-header', children=["Equipos Afectados"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{total_equipos}", className='card-title'),
                                html.P("CDVs con fallos detectados", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Índice de fiabilidad
                ocupaciones_df = self.dataframes.get('ocupaciones', pd.DataFrame())
                if not ocupaciones_df.empty and 'Count' in ocupaciones_df.columns:
                    # Convertir a numérico si es string
                    if ocupaciones_df['Count'].dtype == 'object':
                        ocupaciones_df['Count'] = pd.to_numeric(ocupaciones_df['Count'], errors='coerce')
                    
                    total_ocupaciones = ocupaciones_df['Count'].sum()
                    if total_ocupaciones > 0:
                        fiabilidad = 100 * (1 - (total_fo + total_fl) / total_ocupaciones)
                        fiabilidad = max(0, min(100, fiabilidad))  # Limitar entre 0 y 100
                    else:
                        fiabilidad = "N/A"
                else:
                    fiabilidad = "N/A"
                
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-success mb-3', children=[
                            html.Div(className='card-header', children=["Índice de Fiabilidad"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{fiabilidad if isinstance(fiabilidad, str) else f'{fiabilidad:.2f}%'}", className='card-title'),
                                html.P("Porcentaje de operaciones sin fallos", className='card-text')
                            ])
                        ])
                    ])
                )
                
            elif self.analysis_type == "ADV":
                # KPIs para ADV
                
                # Total de discordancias
                total_disc = len(self.dataframes.get('discordancias', pd.DataFrame()))
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-danger mb-3', children=[
                            html.Div(className='card-header', children=["Discordancias"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{total_disc}", className='card-title'),
                                html.P("Total de discordancias detectadas", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Total de movimientos
                movimientos_df = self.dataframes.get('movimientos', pd.DataFrame())
                if not movimientos_df.empty and 'Count' in movimientos_df.columns:
                    # Convertir a numérico si es string
                    if movimientos_df['Count'].dtype == 'object':
                        movimientos_df['Count'] = pd.to_numeric(movimientos_df['Count'], errors='coerce')
                    
                    total_mov = movimientos_df['Count'].sum()
                else:
                    total_mov = 0
                
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-info mb-3', children=[
                            html.Div(className='card-header', children=["Movimientos"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{total_mov}", className='card-title'),
                                html.P("Total de movimientos registrados", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Total de equipos con discordancias
                equipos_disc = set()
                if 'discordancias' in self.dataframes and 'Equipo Estacion' in self.dataframes['discordancias'].columns:
                    equipos_disc = set(self.dataframes['discordancias']['Equipo Estacion'].unique())
                
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-primary mb-3', children=[
                            html.Div(className='card-header', children=["Agujas Afectadas"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{len(equipos_disc)}", className='card-title'),
                                html.P("Agujas con discordancias", className='card-text')
                            ])
                        ])
                    ])
                )
                
                # Índice de fiabilidad
                if total_disc > 0 and total_mov > 0:
                    fiabilidad = 100 * (1 - total_disc / total_mov)
                    fiabilidad = max(0, min(100, fiabilidad))  # Limitar entre 0 y 100
                else:
                    fiabilidad = "N/A"
                
                kpi_cards.append(
                    html.Div(className='col-md-3', children=[
                        html.Div(className='card text-white bg-success mb-3', children=[
                            html.Div(className='card-header', children=["Índice de Fiabilidad"]),
                            html.Div(className='card-body', children=[
                                html.H5(f"{fiabilidad if isinstance(fiabilidad, str) else f'{fiabilidad:.2f}%'}", className='card-title'),
                                html.P("Porcentaje de movimientos sin discordancias", className='card-text')
                            ])
                        ])
                    ])
                )
            
            return kpi_cards
        except Exception as e:
            logger.error(f"Error al crear tarjetas KPI: {str(e)}")
            # Devolver tarjeta de error
            return [
                html.Div(className='col-md-12', children=[
                    html.Div(className='card text-white bg-danger mb-3', children=[
                        html.Div(className='card-header', children=["Error"]),
                        html.Div(className='card-body', children=[
                            html.H5("Error al generar KPIs", className='card-title'),
                            html.P(f"Detalles: {str(e)}", className='card-text')
                        ])
                    ])
                ])
            ]
    
    def create_time_trend_figure(self, dataframes=None):
        """Crear gráfico de tendencia temporal"""
        # Usar los dataframes filtrados si se proporcionan, o los originales si no
        dfs = dataframes if dataframes else self.dataframes
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in dfs and 'Fecha Hora' in dfs['fallos_ocupacion'].columns:
                df = dfs['fallos_ocupacion'].copy()
                
                # Agrupar por fecha para contar fallos
                df['fecha'] = pd.to_datetime(df['Fecha Hora']).dt.date
                fallas_por_dia = df.groupby('fecha').size().reset_index(name='conteo')
                fallas_por_dia['fecha'] = pd.to_datetime(fallas_por_dia['fecha'])
                
                fig = px.line(
                    fallas_por_dia, 
                    x='fecha', 
                    y='conteo',
                    labels={'fecha': 'Fecha', 'conteo': 'Número de Fallos'},
                    title="Tendencia de Fallos de Ocupación",
                    color_discrete_sequence=[self.colors['danger']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10)
                )
                
                return fig
            
        elif self.analysis_type == "ADV":
            if 'discordancias' in self.dataframes and 'Fecha Hora' in self.dataframes['discordancias'].columns:
                df = self.dataframes['discordancias'].copy()
                
                # Agrupar por fecha para contar discordancias
                df['fecha'] = pd.to_datetime(df['Fecha Hora']).dt.date
                disc_por_dia = df.groupby('fecha').size().reset_index(name='conteo')
                disc_por_dia['fecha'] = pd.to_datetime(disc_por_dia['fecha'])
                
                fig = px.line(
                    disc_por_dia, 
                    x='fecha', 
                    y='conteo',
                    labels={'fecha': 'Fecha', 'conteo': 'Número de Discordancias'},
                    title="Tendencia de Discordancias en Agujas",
                    color_discrete_sequence=[self.colors['danger']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10)
                )
                
                return fig
        
        # Figura vacía en caso de no tener datos
        fig = go.Figure()
        fig.update_layout(
            title="No hay datos disponibles para mostrar tendencia temporal",
            xaxis=dict(title="Fecha"),
            yaxis=dict(title="Valor"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font_color=self.colors['text']
        )
        
        return fig
    
    def create_equipment_distribution_figure(self, dataframes=None):
        """Crear gráfico de distribución por equipo"""
        # Usar los dataframes filtrados si se proporcionan, o los originales si no
        dfs = dataframes if dataframes else self.dataframes
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in dfs and 'Equipo' in dfs['fallos_ocupacion'].columns:
                df = dfs['fallos_ocupacion'].copy()
                
                # Contar fallos por equipo
                fallas_por_equipo = df['Equipo'].value_counts().reset_index()
                fallas_por_equipo.columns = ['Equipo', 'Conteo']
                
                # Tomar los 15 equipos con más fallos
                top_equipos = fallas_por_equipo.head(15)
                
                fig = px.bar(
                    top_equipos, 
                    x='Equipo', 
                    y='Conteo',
                    labels={'Equipo': 'CDV', 'Conteo': 'Número de Fallos'},
                    title="Distribución de Fallos por CDV (Top 15)",
                    color_discrete_sequence=[self.colors['primary']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10),
                    xaxis={'categoryorder':'total descending'}
                )
                
                return fig
                
        elif self.analysis_type == "ADV":
            if 'discordancias' in dfs and 'Equipo Estacion' in dfs['discordancias'].columns:
                df = dfs['discordancias'].copy()
                
                # Contar discordancias por equipo
                disc_por_equipo = df['Equipo Estacion'].value_counts().reset_index()
                disc_por_equipo.columns = ['Equipo', 'Conteo']
                
                # Tomar los 15 equipos con más discordancias
                top_equipos = disc_por_equipo.head(15)
                
                fig = px.bar(
                    top_equipos, 
                    x='Equipo', 
                    y='Conteo',
                    labels={'Equipo': 'Aguja', 'Conteo': 'Número de Discordancias'},
                    title="Distribución de Discordancias por Aguja (Top 15)",
                    color_discrete_sequence=[self.colors['primary']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10),
                    xaxis={'categoryorder':'total descending'}
                )
                
                return fig
        
        # Figura vacía en caso de no tener datos
        fig = go.Figure()
        fig.update_layout(
            title="No hay datos disponibles para mostrar distribución por equipo",
            xaxis=dict(title="Equipo"),
            yaxis=dict(title="Conteo"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font_color=self.colors['text']
        )
        
        return fig
    
    def create_hourly_distribution_figure(self, dataframes=None, viz_type='daily'):
        """Crear gráfico de distribución horaria"""
        # Usar los dataframes filtrados si se proporcionan, o los originales si no
        dfs = dataframes if dataframes else self.dataframes
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in dfs and 'Fecha Hora' in dfs['fallos_ocupacion'].columns:
                df = dfs['fallos_ocupacion'].copy()
                
                # Extraer hora del día
                df['hora'] = pd.to_datetime(df['Fecha Hora']).dt.hour
                
                # Aplicar agrupación basada en el tipo de visualización
                if viz_type == 'weekly':
                    df['dia_semana'] = pd.to_datetime(df['Fecha Hora']).dt.day_name()
                    fallas_por_tiempo = df.groupby('dia_semana').size().reset_index(name='Conteo')
                    fallas_por_tiempo.columns = ['Periodo', 'Conteo']
                    titulo = "Distribución de Fallos por Día de la Semana"
                    x_label = "Día de la Semana"
                elif viz_type == 'monthly':
                    df['mes'] = pd.to_datetime(df['Fecha Hora']).dt.month_name()
                    fallas_por_tiempo = df.groupby('mes').size().reset_index(name='Conteo')
                    fallas_por_tiempo.columns = ['Periodo', 'Conteo']
                    titulo = "Distribución de Fallos por Mes"
                    x_label = "Mes"
                else:  # default: daily
                    fallas_por_tiempo = df['hora'].value_counts().reset_index()
                    fallas_por_tiempo.columns = ['Periodo', 'Conteo']
                    fallas_por_tiempo = fallas_por_tiempo.sort_values('Periodo')
                    titulo = "Distribución Horaria de Fallos"
                    x_label = "Hora del Día"
                
                fig = px.line(
                    fallas_por_tiempo, 
                    x='Periodo', 
                    y='Conteo',
                    labels={'Periodo': x_label, 'Conteo': 'Número de Fallos'},
                    title=titulo,
                    markers=True,
                    color_discrete_sequence=[self.colors['info']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10)
                )
                
                if viz_type == 'daily':
                    fig.update_xaxes(tickmode='linear', tick0=0, dtick=1)
                
                return fig
                
        elif self.analysis_type == "ADV":
            if 'discordancias' in dfs and 'Fecha Hora' in dfs['discordancias'].columns:
                df = dfs['discordancias'].copy()
                
                # Extraer hora del día
                df['hora'] = pd.to_datetime(df['Fecha Hora']).dt.hour
                
                # Aplicar agrupación basada en el tipo de visualización
                if viz_type == 'weekly':
                    df['dia_semana'] = pd.to_datetime(df['Fecha Hora']).dt.day_name()
                    disc_por_tiempo = df.groupby('dia_semana').size().reset_index(name='Conteo')
                    disc_por_tiempo.columns = ['Periodo', 'Conteo']
                    titulo = "Distribución de Discordancias por Día de la Semana"
                    x_label = "Día de la Semana"
                elif viz_type == 'monthly':
                    df['mes'] = pd.to_datetime(df['Fecha Hora']).dt.month_name()
                    disc_por_tiempo = df.groupby('mes').size().reset_index(name='Conteo')
                    disc_por_tiempo.columns = ['Periodo', 'Conteo']
                    titulo = "Distribución de Discordancias por Mes"
                    x_label = "Mes"
                else:  # default: daily
                    disc_por_hora = df['hora'].value_counts().reset_index()
                    disc_por_hora.columns = ['Periodo', 'Conteo']
                    disc_por_tiempo = disc_por_hora.sort_values('Periodo')
                    titulo = "Distribución Horaria de Discordancias"
                    x_label = "Hora del Día"
                
                fig = px.line(
                    disc_por_tiempo, 
                    x='Periodo', 
                    y='Conteo',
                    labels={'Periodo': x_label, 'Conteo': 'Número de Discordancias'},
                    title=titulo,
                    markers=True,
                    color_discrete_sequence=[self.colors['info']]
                )
                
                fig.update_layout(
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    font_color=self.colors['text'],
                    margin=dict(l=10, r=10, t=50, b=10)
                )
                
                if viz_type == 'daily':
                    fig.update_xaxes(tickmode='linear', tick0=0, dtick=1)
                
                return fig
        
        # Figura vacía en caso de no tener datos
        fig = go.Figure()
        fig.update_layout(
            title="No hay datos disponibles para mostrar distribución horaria",
            xaxis=dict(title="Hora"),
            yaxis=dict(title="Conteo"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font_color=self.colors['text']
        )
        
        return fig
    
    def create_heatmap_figure(self, dataframes=None, viz_type='daily'):
        """Crear mapa de calor (día de la semana vs. hora)"""
        # Usar los dataframes filtrados si se proporcionan, o los originales si no
        dfs = dataframes if dataframes else self.dataframes
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in dfs and 'Fecha Hora' in dfs['fallos_ocupacion'].columns:
                df = dfs['fallos_ocupacion'].copy()
                
                # Extraer diferentes dimensiones temporales
                fecha_dt = pd.to_datetime(df['Fecha Hora'])
                df['dia_semana'] = fecha_dt.dt.day_name()
                df['hora'] = fecha_dt.dt.hour
                df['mes'] = fecha_dt.dt.month_name()
                df['semana'] = fecha_dt.dt.isocalendar().week
                
                # Configurar dimensiones basadas en el tipo de visualización
                if viz_type == 'monthly':
                    index_col = 'mes'
                    columns_col = 'dia_semana'
                    title = "Mapa de Calor: Fallos por Mes y Día de la Semana"
                    x_label = "Día de la Semana"
                    y_label = "Mes"
                elif viz_type == 'weekly':
                    index_col = 'semana'
                    columns_col = 'dia_semana'
                    title = "Mapa de Calor: Fallos por Semana y Día"
                    x_label = "Día de la Semana"
                    y_label = "Semana del Año"
                else:  # default: daily
                    index_col = 'dia_semana'
                    columns_col = 'hora'
                    title = "Mapa de Calor: Fallos por Día y Hora"
                    x_label = "Hora del Día"
                    y_label = "Día de la Semana"
                
                # Orden de los días
                dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                
                # Crear tabla pivote para el heatmap
                try:
                    heatmap_data = pd.pivot_table(
                        df, 
                        values='Equipo',
                        index=index_col,
                        columns=columns_col,
                        aggfunc='count',
                        fill_value=0
                    )
                    
                    # Reordenar días si es necesario
                    if columns_col == 'dia_semana':
                        heatmap_data = heatmap_data.reindex(columns=dias_orden)
                    elif index_col == 'dia_semana':
                        heatmap_data = heatmap_data.reindex(dias_orden)
                    
                    # Crear heatmap
                    fig = px.imshow(
                        heatmap_data,
                        labels=dict(x=x_label, y=y_label, color="Número de Fallos"),
                        title=title,
                        color_continuous_scale='Viridis'
                    )
                    
                    fig.update_layout(
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font_color=self.colors['text'],
                        margin=dict(l=10, r=10, t=50, b=10)
                    )
                    
                    return fig
                except:
                    # En caso de error con pivot_table (normalmente por falta de datos)
                    pass
                
        elif self.analysis_type == "ADV":
            if 'discordancias' in dfs and 'Fecha Hora' in dfs['discordancias'].columns:
                df = dfs['discordancias'].copy()
                
                # Extraer diferentes dimensiones temporales
                fecha_dt = pd.to_datetime(df['Fecha Hora'])
                df['dia_semana'] = fecha_dt.dt.day_name()
                df['hora'] = fecha_dt.dt.hour
                df['mes'] = fecha_dt.dt.month_name()
                df['semana'] = fecha_dt.dt.isocalendar().week
                
                # Configurar dimensiones basadas en el tipo de visualización
                if viz_type == 'monthly':
                    index_col = 'mes'
                    columns_col = 'dia_semana'
                    title = "Mapa de Calor: Discordancias por Mes y Día de la Semana"
                    x_label = "Día de la Semana"
                    y_label = "Mes"
                elif viz_type == 'weekly':
                    index_col = 'semana'
                    columns_col = 'dia_semana'
                    title = "Mapa de Calor: Discordancias por Semana y Día"
                    x_label = "Día de la Semana"
                    y_label = "Semana del Año"
                else:  # default: daily
                    index_col = 'dia_semana'
                    columns_col = 'hora'
                    title = "Mapa de Calor: Discordancias por Día y Hora"
                    x_label = "Hora del Día"
                    y_label = "Día de la Semana"
                
                # Orden de los días
                dias_orden = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                
                # Crear tabla pivote para el heatmap
                try:
                    heatmap_data = pd.pivot_table(
                        df, 
                        values='Equipo Estacion',
                        index=index_col,
                        columns=columns_col,
                        aggfunc='count',
                        fill_value=0
                    )
                    
                    # Reordenar días si es necesario
                    if columns_col == 'dia_semana':
                        heatmap_data = heatmap_data.reindex(columns=dias_orden)
                    elif index_col == 'dia_semana':
                        heatmap_data = heatmap_data.reindex(dias_orden)
                    
                    # Crear heatmap
                    fig = px.imshow(
                        heatmap_data,
                        labels=dict(x=x_label, y=y_label, color="Número de Discordancias"),
                        title=title,
                        color_continuous_scale='Viridis'
                    )
                    
                    fig.update_layout(
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        font_color=self.colors['text'],
                        margin=dict(l=10, r=10, t=50, b=10)
                    )
                    
                    return fig
                except:
                    # En caso de error con pivot_table (normalmente por falta de datos)
                    pass
        
        # Figura vacía en caso de no tener datos
        fig = go.Figure()
        fig.update_layout(
            title="No hay datos disponibles para mostrar mapa de calor",
            xaxis=dict(title="Hora"),
            yaxis=dict(title="Día"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font_color=self.colors['text']
        )
        
        return fig
    
    def create_data_table(self):
        """Crear tabla de datos"""
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in self.dataframes and not self.dataframes['fallos_ocupacion'].empty:
                df = self.dataframes['fallos_ocupacion'].copy()
                
                # Seleccionar columnas relevantes
                if 'Fecha Hora' in df.columns and 'Equipo' in df.columns and 'Estacion' in df.columns:
                    df = df[['Fecha Hora', 'Equipo', 'Estacion', 'Diff.Time_+1_row']]
                    
                    # Formatear para mostrar
                    df['Fecha Hora'] = df['Fecha Hora'].dt.strftime('%d-%m-%Y %H:%M:%S')
                    df['Diff.Time_+1_row'] = df['Diff.Time_+1_row'].astype(str)
                    
                    return html.Table(
                        # Encabezado
                        [html.Tr([html.Th(col) for col in df.columns])] +
                        # Cuerpo
                        [html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(min(50, len(df)))],
                        className='table table-striped table-hover'
                    )
                
        elif self.analysis_type == "ADV":
            if 'discordancias' in self.dataframes and not self.dataframes['discordancias'].empty:
                df = self.dataframes['discordancias'].copy()
                
                # Seleccionar columnas relevantes
                columns_to_show = ['Fecha Hora', 'Equipo Estacion', 'Linea']
                columns_present = [col for col in columns_to_show if col in df.columns]
                
                if columns_present:
                    df = df[columns_present]
                    
                    # Formatear para mostrar si es necesario
                    if 'Fecha Hora' in df.columns:
                        df['Fecha Hora'] = pd.to_datetime(df['Fecha Hora']).dt.strftime('%d-%m-%Y %H:%M:%S')
                    
                    return html.Table(
                        # Encabezado
                        [html.Tr([html.Th(col) for col in df.columns])] +
                        # Cuerpo
                        [html.Tr([html.Td(df.iloc[i][col]) for col in df.columns]) for i in range(min(50, len(df)))],
                        className='table table-striped table-hover'
                    )
        
        # Tabla vacía en caso de no tener datos
        return html.Div("No hay datos disponibles para mostrar en la tabla.")
    
    def get_min_date(self):
        """Obtener la fecha mínima de los datos"""
        min_date = datetime.now()
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in self.dataframes and 'Fecha Hora' in self.dataframes['fallos_ocupacion'].columns:
                date_min = self.dataframes['fallos_ocupacion']['Fecha Hora'].min()
                if date_min and not pd.isna(date_min):
                    min_date = min(min_date, date_min)
            
            if 'fallos_liberacion' in self.dataframes and 'Fecha Hora' in self.dataframes['fallos_liberacion'].columns:
                date_min = self.dataframes['fallos_liberacion']['Fecha Hora'].min()
                if date_min and not pd.isna(date_min):
                    min_date = min(min_date, date_min)
        
        elif self.analysis_type == "ADV":
            if 'discordancias' in self.dataframes and 'Fecha Hora' in self.dataframes['discordancias'].columns:
                date_min = pd.to_datetime(self.dataframes['discordancias']['Fecha Hora']).min()
                if date_min and not pd.isna(date_min):
                    min_date = min(min_date, date_min)
        
        # Retroceder 30 días por defecto
        return min_date.date()
    
    def get_max_date(self):
        """Obtener la fecha máxima de los datos"""
        max_date = datetime.now().date()
        return max_date
    
    def get_equipment_list(self):
        """Obtener lista de equipos disponibles"""
        equipos = []
        
        if self.analysis_type == "CDV":
            if 'fallos_ocupacion' in self.dataframes and 'Equipo' in self.dataframes['fallos_ocupacion'].columns:
                equipos.extend(self.dataframes['fallos_ocupacion']['Equipo'].unique())
            
            if 'fallos_liberacion' in self.dataframes and 'Equipo' in self.dataframes['fallos_liberacion'].columns:
                equipos.extend(self.dataframes['fallos_liberacion']['Equipo'].unique())
        
        elif self.analysis_type == "ADV":
            if 'discordancias' in self.dataframes and 'Equipo Estacion' in self.dataframes['discordancias'].columns:
                equipos.extend(self.dataframes['discordancias']['Equipo Estacion'].unique())
        
        return sorted(list(set(equipos)))
    
    def setup_callbacks(self):
        """Configurar callbacks para interactividad"""
        if not self.app:
            return
        
        # Primero definir la función del callback
        def update_graphs(n_clicks, start_date, end_date, selected_equipments, viz_type):
            # No actualizar si no se ha presionado el botón
            if n_clicks is None:
                # Retornar figuras iniciales
                return [
                    self.create_time_trend_figure(),
                    self.create_equipment_distribution_figure(),
                    self.create_hourly_distribution_figure(),
                    self.create_heatmap_figure()
                ]
                
            try:
                # Preparar fecha de inicio y fin
                start_date = pd.to_datetime(start_date)
                end_date = pd.to_datetime(end_date)
                
                # Crear copias filtradas de los dataframes originales
                filtered_dfs = {}
                
                # Filtrar datos para CDV
                if self.analysis_type == "CDV":
                    # Aplicar filtros de fecha a todos los dataframes
                    for key, df in self.dataframes.items():
                        if df is not None and not df.empty:
                            filtered_dfs[key] = df.copy()
                            
                            # Filtrar por fecha si la columna adecuada existe
                            if 'Fecha Hora' in df.columns and start_date and end_date:
                                # Asegurar que Fecha Hora es datetime
                                filtered_dfs[key]['Fecha Hora'] = pd.to_datetime(filtered_dfs[key]['Fecha Hora'])
                                filtered_dfs[key] = filtered_dfs[key][
                                    (filtered_dfs[key]['Fecha Hora'] >= start_date) & 
                                    (filtered_dfs[key]['Fecha Hora'] <= end_date)
                                ]
                            elif 'Fecha' in df.columns and start_date and end_date:
                                # Asegurar que Fecha es datetime
                                filtered_dfs[key]['Fecha'] = pd.to_datetime(filtered_dfs[key]['Fecha'])
                                filtered_dfs[key] = filtered_dfs[key][
                                    (filtered_dfs[key]['Fecha'] >= pd.to_datetime(start_date)) & 
                                    (filtered_dfs[key]['Fecha'] <= pd.to_datetime(end_date))
                                ]
                            
                            # Filtrar por equipamiento si es necesario
                            if selected_equipments and len(selected_equipments) > 0 and 'Equipo' in df.columns:
                                filtered_dfs[key] = filtered_dfs[key][
                                    filtered_dfs[key]['Equipo'].isin(selected_equipments)
                                ]
                    
                    # Generar gráficos con los datos filtrados
                    if not filtered_dfs:
                        # Si no hay datos filtrados, usar los originales
                        time_trend = self.create_time_trend_figure()
                        equip_dist = self.create_equipment_distribution_figure()
                        hourly_dist = self.create_hourly_distribution_figure()
                        heatmap = self.create_heatmap_figure()
                    else:
                        # Usar versiones temporales de las funciones de creación de gráficos
                        # que aceptan los dataframes filtrados
                        time_trend = self.create_time_trend_figure(dataframes=filtered_dfs)
                        equip_dist = self.create_equipment_distribution_figure(dataframes=filtered_dfs)
                        hourly_dist = self.create_hourly_distribution_figure(dataframes=filtered_dfs)
                        heatmap = self.create_heatmap_figure(dataframes=filtered_dfs, viz_type=viz_type)
                    
                    return time_trend, equip_dist, hourly_dist, heatmap
                
                # Filtrar datos para ADV
                elif self.analysis_type == "ADV":
                    # Similar implementación para ADV
                    for key, df in self.dataframes.items():
                        if df is not None and not df.empty:
                            filtered_dfs[key] = df.copy()
                            
                            # Filtrar por fecha
                            if 'Fecha Hora' in df.columns and start_date and end_date:
                                # Asegurar que Fecha Hora es datetime
                                filtered_dfs[key]['Fecha Hora'] = pd.to_datetime(filtered_dfs[key]['Fecha Hora'])
                                filtered_dfs[key] = filtered_dfs[key][
                                    (filtered_dfs[key]['Fecha Hora'] >= start_date) & 
                                    (filtered_dfs[key]['Fecha Hora'] <= end_date)
                                ]
                            elif 'Fecha' in df.columns and start_date and end_date:
                                # Asegurar que Fecha es datetime
                                filtered_dfs[key]['Fecha'] = pd.to_datetime(filtered_dfs[key]['Fecha'])
                                filtered_dfs[key] = filtered_dfs[key][
                                    (filtered_dfs[key]['Fecha'] >= pd.to_datetime(start_date)) & 
                                    (filtered_dfs[key]['Fecha'] <= pd.to_datetime(end_date))
                                ]
                            
                            # Filtrar por equipamiento
                            if selected_equipments and len(selected_equipments) > 0:
                                if 'Equipo' in df.columns:
                                    filtered_dfs[key] = filtered_dfs[key][
                                        filtered_dfs[key]['Equipo'].isin(selected_equipments)
                                    ]
                                elif 'Equipo Estacion' in df.columns:
                                    filtered_dfs[key] = filtered_dfs[key][
                                        filtered_dfs[key]['Equipo Estacion'].isin(selected_equipments)
                                    ]
                    
                    # Generar gráficos con los datos filtrados
                    if not filtered_dfs:
                        # Si no hay datos filtrados, usar los originales
                        time_trend = self.create_time_trend_figure()
                        equip_dist = self.create_equipment_distribution_figure()
                        hourly_dist = self.create_hourly_distribution_figure()
                        heatmap = self.create_heatmap_figure()
                    else:
                        # Usar versiones de las funciones que aceptan los dataframes filtrados
                        time_trend = self.create_time_trend_figure(dataframes=filtered_dfs)
                        equip_dist = self.create_equipment_distribution_figure(dataframes=filtered_dfs)
                        hourly_dist = self.create_hourly_distribution_figure(dataframes=filtered_dfs)
                        heatmap = self.create_heatmap_figure(dataframes=filtered_dfs, viz_type=viz_type)
                    
                    return time_trend, equip_dist, hourly_dist, heatmap
                
                # Valores por defecto
                return (
                    self.create_time_trend_figure(), 
                    self.create_equipment_distribution_figure(),
                    self.create_hourly_distribution_figure(),
                    self.create_heatmap_figure()
                )
                    
            except Exception as e:
                logger.error(f"Error en callback de actualización de gráficos: {str(e)}")
                # Devolver gráficos vacíos en caso de error
                empty_fig = go.Figure()
                empty_fig.update_layout(
                    title="Error al actualizar gráficos",
                    xaxis=dict(title=""),
                    yaxis=dict(title=""),
                    annotations=[dict(
                        text=f"Error: {str(e)}",
                        xref="paper", yref="paper",
                        x=0.5, y=0.5, showarrow=False
                    )]
                )
                return empty_fig, empty_fig, empty_fig, empty_fig
        
        # Luego aplicar el decorador a la función
        self.app.callback(
            [Output('time-trend-graph', 'figure'),
            Output('equipment-distribution', 'figure'),
            Output('hourly-distribution', 'figure'),
            Output('heatmap', 'figure')],
            [Input('apply-filters-button', 'n_clicks')],  # Usar el botón como trigger
            [State('date-range', 'start_date'),  # Los demás parámetros como State
            State('date-range', 'end_date'),
            State('equipment-filter', 'value'),
            State('visualization-type', 'value')]
        )(update_graphs)  # Aplicar el decorador a la función ya definida
    
    def run_dashboard(self):
        """Ejecutar el dashboard web"""
        if not self.app:
            logger.error("No se ha creado el dashboard. Ejecute create_dashboard() primero.")
            return False
        
        try:
            # Iniciar servidor en un hilo separado
            self.server_thread = threading.Thread(target=self._run_server)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            # Abrir navegador
            url = f"http://localhost:{self.port}"
            webbrowser.open(url)
            
            self.running = True
            logger.info(f"Dashboard iniciado en {url}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error al iniciar el dashboard: {str(e)}")
            return False
    
    def _run_server(self):
        """Método interno para ejecutar el servidor Dash"""
        try:
            self.app.run_server(debug=False, port=self.port, use_reloader=False)
        except Exception as e:
            logger.error(f"Error en el servidor Dash: {str(e)}")
    
    def stop_dashboard(self):
        """Detener el dashboard web"""
        self.running = False
        logger.info("Dashboard detenido")
        return True