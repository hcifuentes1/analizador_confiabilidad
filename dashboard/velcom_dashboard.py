# dashboard/velcom_dashboard.py
import os
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import webbrowser
from threading import Timer
import plotly.graph_objs as go




# Modificación para la función load_data en velcom_dashboard.py

def load_data(data_path):
    """Cargar datos procesados de Velcom y fallos CDV"""
    data = {
        'velcom_data': pd.read_csv(os.path.join(data_path, 'velcom_data.csv')),
        'velcom_trains': pd.read_csv(os.path.join(data_path, 'velcom_trains.csv')),
        'velcom_stations': pd.read_csv(os.path.join(data_path, 'velcom_stations.csv')),
        'velcom_info': pd.read_csv(os.path.join(data_path, 'velcom_info.csv'))
    }
    
    # 1. Convertir columnas de tiempo a datetime
    for col in ['arrival_time', 'departure_time']:
        if col in data['velcom_data'].columns:
            data['velcom_data'][col] = pd.to_datetime(data['velcom_data'][col], errors='coerce')
    
    for col in ['first_arrival', 'last_arrival']:
        if col in data['velcom_trains'].columns:
            data['velcom_trains'][col] = pd.to_datetime(data['velcom_trains'][col], errors='coerce')
    
    # Cargar datos de fallos CDV
    try:
        # Intentar cargar fallos de ocupación
        fo_path = os.path.join(data_path, 'df_L2_FO_Mensual.csv')
        if os.path.exists(fo_path):
            data['fallos_ocupacion'] = pd.read_csv(fo_path)
            # Convertir fechas
            if 'Fecha Hora' in data['fallos_ocupacion'].columns:
                data['fallos_ocupacion']['Fecha Hora'] = pd.to_datetime(data['fallos_ocupacion']['Fecha Hora'])
            print(f"Cargados {len(data['fallos_ocupacion'])} registros de fallos de ocupación")
        else:
            print(f"Archivo de fallos de ocupación no encontrado en: {fo_path}")
        
        # Intentar cargar fallos de liberación
        fl_path = os.path.join(data_path, 'df_L2_FL_Mensual.csv')
        if os.path.exists(fl_path):
            data['fallos_liberacion'] = pd.read_csv(fl_path)
            # Convertir fechas
            if 'Fecha Hora' in data['fallos_liberacion'].columns:
                data['fallos_liberacion']['Fecha Hora'] = pd.to_datetime(data['fallos_liberacion']['Fecha Hora'])
            print(f"Cargados {len(data['fallos_liberacion'])} registros de fallos de liberación")
        else:
            print(f"Archivo de fallos de liberación no encontrado en: {fl_path}")
    
    except Exception as e:
        print(f"Error al cargar datos de fallos CDV: {e}")
    
    # 2. Preparar datos para visualización 3D
    
    # 2.1 Crear copia de trabajo para no modificar los datos originales
    df_3d = data['velcom_data'].copy()
    
    # 2.2 Ordenar por tren y tiempo de llegada para cálculos secuenciales
    df_3d = df_3d.sort_values(['train_number', 'arrival_time'])
    
    # 2.3 Calcular tiempo desde inicio del día (en horas, para eje X)
    df_3d['time_hours'] = df_3d['arrival_time'].dt.hour + df_3d['arrival_time'].dt.minute/60
    
    # 2.4 Calcular tiempo entre estaciones consecutivas por tren
    df_3d['prev_arrival'] = df_3d.groupby('train_number')['arrival_time'].shift(1)
    df_3d['time_diff'] = (df_3d['arrival_time'] - df_3d['prev_arrival']).dt.total_seconds() / 60  # en minutos
    
    # 2.5 Calcular tiempo de permanencia en cada estación
    # Asegurarse de que ambas columnas son datetime
    if 'departure_time' in df_3d.columns and 'arrival_time' in df_3d.columns:
        df_3d['stay_time'] = (df_3d['departure_time'] - df_3d['arrival_time']).dt.total_seconds() / 60  # en minutos
    else:
        df_3d['stay_time'] = 0  # valor por defecto si no hay datos
    
    # 2.6 Calcular velocidad relativa
    # Para cada tren, calculamos una velocidad relativa basada en el tiempo entre estaciones
    train_groups = df_3d.groupby('train_number')
    
    all_trains_data = []
    for train, train_data in train_groups:
        if len(train_data) > 1:
            # Llenar NaN al inicio con valor similar al siguiente
            train_data['time_diff'] = train_data['time_diff'].fillna(train_data['time_diff'].median())
            
            # Invertir tiempo (a mayor tiempo entre estaciones, menor velocidad)
            max_time = train_data['time_diff'].max() if train_data['time_diff'].max() > 0 else 1
            train_data['speed'] = 10 * (1 - train_data['time_diff'] / max_time) + 1  # Escala de 1 a 11
        else:
            # Solo hay un registro para este tren
            train_data['speed'] = 5  # Valor medio por defecto
            
        all_trains_data.append(train_data)
    
    # Combinar todos los datos procesados
    if all_trains_data:
        df_3d_processed = pd.concat(all_trains_data)
    else:
        df_3d_processed = df_3d.copy()
        df_3d_processed['speed'] = 5  # Valor por defecto
    
    # En load_data()
    # 2.7 Crear mapeo numérico de estaciones para visualización 3D
    ordered_stations = [
        'AV', 'ZA', 'DO', 'EI', 'CE', 'CB', 'PT', 'CA', 'AN', 'HE', 'TO', 'PQ', 
        'RO', 'FR', 'LL', 'SM', 'LV', 'DE', 'CN', 'LO', 'EP', 'LC', 'EB', 'OB', 
        'CM', 'PI'
    ]
    
    # Crear diccionario de mapeo según el orden específico
    station_mapping = {station: i for i, station in enumerate(ordered_stations)}
    
    # Para estaciones que no están en la lista, añadirlas al final
    all_stations = df_3d_processed['station'].unique()
    max_value = len(ordered_stations)
    for station in all_stations:
        if station not in station_mapping:
            station_mapping[station] = max_value
            max_value += 1
    
    # Asignar valores numéricos a las estaciones
    df_3d_processed['station_num'] = df_3d_processed['station'].map(station_mapping)
    
    # 2.8 Llenar valores NaN en datos críticos
    for col in ['time_diff', 'stay_time', 'speed']:
        df_3d_processed[col] = df_3d_processed[col].fillna(0)
    
    # 3. Guardar los datos procesados
    data['velcom_data_3d'] = df_3d_processed
    data['station_mapping'] = station_mapping
    data['ordered_stations'] = ordered_stations
    
    # 4. Procesar datos de fallos CDV para visualización
    process_failure_data(data)
    
    return data
    
def process_failure_data(data):
    """Procesar datos de fallos CDV para visualización"""
    # Sólo proceder si existen datos de fallos
    if 'fallos_ocupacion' not in data and 'fallos_liberacion' not in data:
        print("No se encontraron datos de fallos CDV")
        return
    
    # Crear un DataFrame combinado de fallos 
    failures_list = []
    
    if 'fallos_ocupacion' in data:
        fo_df = data['fallos_ocupacion'].copy()
        fo_df['tipo_fallo'] = 'Falsa Ocupación'
        failures_list.append(fo_df)
    
    if 'fallos_liberacion' in data:
        fl_df = data['fallos_liberacion'].copy()
        fl_df['tipo_fallo'] = 'Falsa Liberación'
        failures_list.append(fl_df)
    
    if failures_list:
        # Combinar datos de fallos
        combined_failures = pd.concat(failures_list, ignore_index=True)
        
        # Extraer estación del nombre del equipo si es posible
        # Formato típico: Estacion_CDV_XX
        combined_failures['station'] = combined_failures['Equipo'].str.extract(r'(\w+)_CDV_')
        
        # Para equipos sin el formato estándar, intentar otra extracción
        mask = combined_failures['station'].isna()
        if mask.any():
            # Intentar extraer del final del nombre (patrón alternativo)
            combined_failures.loc[mask, 'station'] = combined_failures.loc[mask, 'Equipo'].str.extract(r'_(\w+)$')
        
        # Añadir hora del día para análisis
        combined_failures['time_hours'] = combined_failures['Fecha Hora'].dt.hour + combined_failures['Fecha Hora'].dt.minute/60
        
        # Asignar valores numéricos a las estaciones usando el mismo mapeo
        if 'station_mapping' in data:
            station_mapping = data['station_mapping']  # Obtener del diccionario data
            combined_failures['station_num'] = combined_failures['station'].map(station_mapping)
            
            # Para estaciones que no están en el mapeo, asignar un valor por defecto
            combined_failures['station_num'] = combined_failures['station_num'].fillna(-1)
            
            # Verificar mapeo de estaciones en fallos
            stations_in_failures = combined_failures['station'].unique()
            stations_not_in_mapping = [s for s in stations_in_failures if s not in station_mapping]
            if stations_not_in_mapping:
                print(f"Advertencia: Algunas estaciones en fallos no están en el mapeo: {stations_not_in_mapping}")
        
        # Guardar el DataFrame procesado
        data['combined_failures'] = combined_failures
        print(f"Procesados {len(combined_failures)} registros de fallos combinados")

def create_dashboard(data_path):
    """Crear aplicación Dash para visualizar datos Velcom"""
    # Cargar datos
    data = load_data(data_path)
    
    # Obtener info del reporte
    report_info = data['velcom_info'].iloc[0]
    
    # Crear aplicación Dash
    app = dash.Dash(__name__, title="Dashboard Velcom - Línea 2")
    
    # Obtener listas de valores únicos para filtros
    train_numbers = sorted(data['velcom_data']['train_number'].unique())
    materials = sorted(data['velcom_data']['material'].unique())
    stations = sorted(data['velcom_data']['station'].unique())
    
    # Diseñar layout
    app.layout = html.Div([
        html.H1("Dashboard de Datos Velcom - Línea 2", className="dashboard-title"),
        
        # Información general del reporte
        html.Div([
            html.Div([
                html.H3("Información del Reporte"),
                html.P(f"Periodo: {report_info['start_date']} a {report_info['end_date']}"),
                html.P(f"Total de registros: {report_info['records_count']}"),
                html.P(f"Total de trenes: {report_info['trains_count']}"),
                html.P(f"Total de estaciones: {report_info['stations_count']}"),
                html.P(f"Procesado el: {report_info['processing_date']}")
            ], className="info-box")
        ], className="info-container"),
        
        # Filtros
        html.Div([
            html.H3("Filtros"),
            
            html.Div([
                html.Div([
                    html.Label("Seleccionar Tren:"),
                    dcc.Dropdown(
                        id='train-dropdown',
                        options=[{'label': f'Tren {num}', 'value': num} for num in train_numbers],
                        value=None,
                        placeholder="Seleccionar tren..."
                    )
                ], className="filter-col"),
                
                html.Div([
                    html.Label("Seleccionar Material:"),
                    dcc.Dropdown(
                        id='material-dropdown',
                        options=[{'label': mat, 'value': mat} for mat in materials],
                        value=None,
                        placeholder="Seleccionar material..."
                    )
                ], className="filter-col"),
                
                html.Div([
                    html.Label("Seleccionar Estación:"),
                    dcc.Dropdown(
                        id='station-dropdown',
                        options=[{'label': sta, 'value': sta} for sta in stations],
                        value=None,
                        placeholder="Seleccionar estación..."
                    )
                ], className="filter-col")
            ], className="filters-row"),
            
            html.Div([
                html.Button('Limpiar Filtros', id='clear-filters-button', className="clear-button")
            ], className="button-container")
        ], className="filters-container"),
        
        # Pestañas para diferentes vistas
        dcc.Tabs([
            # Pestaña de Trenes
            dcc.Tab(label='Trenes', children=[
                html.Div([
                    html.Div([
                        html.H3("Trenes en operación"),
                        dash_table.DataTable(
                            id='trains-table',
                            columns=[
                                {'name': 'Número de Tren', 'id': 'train_number'},
                                {'name': 'Material', 'id': 'material'},
                                {'name': 'Estaciones Visitadas', 'id': 'stations_count'},
                                {'name': 'Primera Llegada', 'id': 'first_arrival'},
                                {'name': 'Última Llegada', 'id': 'last_arrival'}
                            ],
                            data=data['velcom_trains'].to_dict('records'),
                            page_size=10,
                            filter_action='native',
                            sort_action='native',
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'left', 'padding': '8px'},
                            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}
                        )
                    ], className="content-box"),
                    
                    html.Div([
                        html.H3("Distribución de Trenes por Estación"),
                        dcc.Graph(id='trains-by-station-graph')
                    ], className="content-box")
                ], className="tab-content")
            ]),
            
            # Pestaña de Estaciones
            dcc.Tab(label='Estaciones', children=[
                html.Div([
                    html.Div([
                        html.H3("Actividad por Estación"),
                        dash_table.DataTable(
                            id='stations-table',
                            columns=[
                                {'name': 'Estación', 'id': 'station'},
                                {'name': 'Trenes', 'id': 'train_count'},
                                {'name': 'Vía Promedio', 'id': 'avg_track'},
                                {'name': 'Llegadas', 'id': 'arrival_count'}
                            ],
                            data=data['velcom_stations'].to_dict('records'),
                            page_size=10,
                            filter_action='native',
                            sort_action='native',
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'left', 'padding': '8px'},
                            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}
                        )
                    ], className="content-box"),
                    
                    html.Div([
                        html.H3("Distribución de Llegadas por Estación"),
                        dcc.Graph(id='arrivals-by-station-graph')
                    ], className="content-box")
                ], className="tab-content")
            ]),
            
            # Pestaña de Trayectos
            dcc.Tab(label='Trayectos', children=[
                html.Div([
                    html.Div([
                        html.H3("Trayectos de Trenes"),
                        dcc.Graph(id='train-journey-graph')
                    ], className="content-box full-width"),
                    
                    html.Div([
                        html.H3("Detalle de Trayectos"),
                        dash_table.DataTable(
                            id='journey-details-table',
                            columns=[
                                {'name': 'Tren', 'id': 'train_number'},
                                {'name': 'Material', 'id': 'material'},
                                {'name': 'Vía', 'id': 'track'},
                                {'name': 'Estación', 'id': 'station'},
                                {'name': 'Llegada', 'id': 'arrival_time'},
                                {'name': 'Salida', 'id': 'departure_time'}
                            ],
                            data=data['velcom_data'].to_dict('records'),
                            page_size=15,
                            filter_action='native',
                            sort_action='native',
                            style_table={'overflowX': 'auto'},
                            style_cell={'textAlign': 'left', 'padding': '8px'},
                            style_header={'backgroundColor': 'lightgrey', 'fontWeight': 'bold'}
                        )
                    ], className="content-box full-width")
                ], className="tab-content")
            ]),
            
            # Nueva pestaña para visualización 3D
            dcc.Tab(label='Visualización 3D', children=[
                html.Div([
                    html.Div([
                        html.H3("Visualización 3D de Trayectos"),
                        html.Div([
                            html.Label("Variable para eje Z:"),
                            dcc.RadioItems(
                                id='z-axis-variable',
                                options=[
                                    {'label': 'Hora del día', 'value': 'time_hours'},
                                    {'label': 'Tiempo entre estaciones', 'value': 'time_diff'},
                                    {'label': 'Velocidad relativa', 'value': 'speed'},
                                    {'label': 'Tiempo de permanencia', 'value': 'stay_time'}
                                ],
                                value='speed',
                                labelStyle={'display': 'inline-block', 'marginRight': '20px'}
                            )
                        ], style={'marginBottom': '20px', 'backgroundColor': '#f8f9fa', 'padding': '10px', 'borderRadius': '5px'}),
                        
                        # Checklist para visualizar fallos CDV (añadido dentro de la pestaña)
                        html.Div([
                            html.Label("Visualizar fallos CDV:"),
                            dcc.Checklist(
                                id='show-failures-checkbox',
                                options=[
                                    {'label': 'Mostrar fallos de ocupación', 'value': 'fo'},
                                    {'label': 'Mostrar fallos de liberación', 'value': 'fl'}
                                ],
                                value=[],  # Inicialmente no seleccionados
                                labelStyle={'display': 'inline-block', 'marginRight': '20px'}
                            )
                        ], style={'marginBottom': '20px', 'backgroundColor': '#f8f9fa', 'padding': '10px', 'borderRadius': '5px'}),
                        
                        dcc.Graph(id='train-3d-graph', style={'height': '700px'})
                    ], className="content-box full-width")
                ], className="tab-content")
            ]),
            
            # Nueva pestaña de correlación tren-fallos
            dcc.Tab(label='Correlación Trenes-Fallos', children=[
                html.Div([
                    html.Div([
                        html.H3("Densidad de fallos por hora del día"),
                        dcc.Graph(id='failures-heatmap')
                    ], className="content-box full-width"),
                    
                    html.Div([
                        html.H3("Distribución de fallos por estación"),
                        dcc.Graph(id='failures-by-station')
                    ], className="content-box full-width"),
                    
                    html.Div([
                        html.H3("Relación entre tráfico de trenes y fallos"),
                        dcc.Graph(id='traffic-failures-correlation')
                    ], className="content-box full-width")
                ], className="tab-content")
            ])
        ], className="tabs-container")
    ], className="dashboard-container")
    
    # Callback para actualizar gráfico de trenes por estación
    @app.callback(
        Output('trains-by-station-graph', 'figure'),
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value')]
    )
    def update_trains_by_station(train_number, material, station):
        df = data['velcom_data'].copy()
        
        # Aplicar filtros
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
        # Contar trenes por estación
        station_counts = df.groupby('station')['train_number'].nunique().reset_index()
        station_counts.columns = ['Estación', 'Cantidad de Trenes']
        station_counts = station_counts.sort_values('Cantidad de Trenes', ascending=False)
        
        # Crear gráfico
        fig = px.bar(
            station_counts, 
            x='Estación', 
            y='Cantidad de Trenes',
            title='Distribución de Trenes por Estación',
            color='Cantidad de Trenes',
            color_continuous_scale='Blues'
        )
        
        fig.update_layout(
            xaxis_title='Estación',
            yaxis_title='Cantidad de Trenes',
            template='plotly_white'
        )
        
        return fig
    
    @app.callback(
        Output('failures-heatmap', 'figure'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('station-dropdown', 'value')]
    )
    def update_failures_heatmap(start_date, end_date, station):
        """Crear mapa de calor de fallos por hora del día y estación"""
        if 'combined_failures' not in data or data['combined_failures'].empty:
            # Crear figura vacía si no hay datos
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de fallos disponibles",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        df = data['combined_failures'].copy()
        
        # Filtrar por fecha si se proporciona rango
        if start_date and end_date:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            df = df[(df['Fecha Hora'] >= start_date) & (df['Fecha Hora'] <= end_date)]
        
        # Filtrar por estación si está seleccionada
        if station:
            df = df[df['station'] == station]
        
        # Verificar si hay datos después del filtrado
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos para los filtros seleccionados",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        # Crear bins por hora del día
        df['hour_bin'] = df['Fecha Hora'].dt.hour
        
        # Agrupar por hora y estación
        heatmap_data = df.groupby(['hour_bin', 'station', 'tipo_fallo']).size().reset_index(name='count')
        
        # Crear tabla pivote para el heatmap - separada por tipo de fallo
        pivot_fo = heatmap_data[heatmap_data['tipo_fallo'] == 'Falsa Ocupación'].pivot(
            index='station', columns='hour_bin', values='count'
        ).fillna(0)
        
        pivot_fl = heatmap_data[heatmap_data['tipo_fallo'] == 'Falsa Liberación'].pivot(
            index='station', columns='hour_bin', values='count'
        ).fillna(0)
        
        # Reordenar las estaciones según el orden específico
        if 'ordered_stations' in data:
            ordered_stations = [s for s in data['ordered_stations'] if s in df['station'].unique()]
            if pivot_fo is not None and not pivot_fo.empty:
                pivot_fo = pivot_fo.reindex(ordered_stations)
            if pivot_fl is not None and not pivot_fl.empty:
                pivot_fl = pivot_fl.reindex(ordered_stations)
        
        # Crear dos subplots para los dos tipos de fallos
        fig = make_subplots(
            rows=2, cols=1,
            subplot_titles=("Fallos de Ocupación por Hora y Estación", 
                            "Fallos de Liberación por Hora y Estación"),
            vertical_spacing=0.12
        )
        
        # Añadir mapa de calor para fallos de ocupación
        if pivot_fo is not None and not pivot_fo.empty:
            fig.add_trace(
                go.Heatmap(
                    z=pivot_fo.values,
                    x=pivot_fo.columns,
                    y=pivot_fo.index,
                    colorscale='Reds',
                    showscale=True,
                    colorbar=dict(title="Fallos FO"),
                    hovertemplate='Estación: %{y}<br>Hora: %{x}<br>Fallos: %{z}'
                ),
                row=1, col=1
            )
        
        # Añadir mapa de calor para fallos de liberación
        if pivot_fl is not None and not pivot_fl.empty:
            fig.add_trace(
                go.Heatmap(
                    z=pivot_fl.values,
                    x=pivot_fl.columns,
                    y=pivot_fl.index,
                    colorscale='Oranges',
                    showscale=True,
                    colorbar=dict(title="Fallos FL"),
                    hovertemplate='Estación: %{y}<br>Hora: %{x}<br>Fallos: %{z}'
                ),
                row=2, col=1
            )
        
        # Actualizar diseño
        fig.update_layout(
            height=800,
            title_text="Densidad de fallos CDV por hora y estación",
            xaxis=dict(title='Hora del día (0-23)'),
            xaxis2=dict(title='Hora del día (0-23)'),
            yaxis=dict(title='Estación'),
            yaxis2=dict(title='Estación')
        )
        
        return fig

    @app.callback(
        Output('failures-by-station', 'figure'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('station-dropdown', 'value')]
    )
    def update_failures_by_station(start_date, end_date, station):
        """Crear gráfico de barras de fallos por estación, dividido por tipo"""
        if 'combined_failures' not in data or data['combined_failures'].empty:
            # Crear figura vacía si no hay datos
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos de fallos disponibles",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        df = data['combined_failures'].copy()
        
        # Filtrar por fecha si se proporciona rango
        if start_date and end_date:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            df = df[(df['Fecha Hora'] >= start_date) & (df['Fecha Hora'] <= end_date)]
        
        # Filtrar por estación si está seleccionada
        if station:
            df = df[df['station'] == station]
        
        # Verificar si hay datos después del filtrado
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos para los filtros seleccionados",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        # Agrupar por estación y tipo de fallo
        grouped_data = df.groupby(['station', 'tipo_fallo']).size().reset_index(name='count')
        
        # Reordenar según el orden específico de estaciones
        if 'ordered_stations' in data:
            # Crear diccionario de mapeo para ordenar
            station_order = {s: i for i, s in enumerate(data['ordered_stations'])}
            # Aplicar el orden personalizado
            grouped_data['station_order'] = grouped_data['station'].map(
                lambda x: station_order.get(x, len(station_order)))
            grouped_data = grouped_data.sort_values('station_order')
            grouped_data = grouped_data.drop('station_order', axis=1)
        
        # Crear gráfico de barras agrupadas
        fig = px.bar(
            grouped_data,
            x='station',
            y='count',
            color='tipo_fallo',
            barmode='group',
            title='Distribución de fallos por estación',
            labels={'station': 'Estación', 'count': 'Número de fallos', 'tipo_fallo': 'Tipo de fallo'},
            color_discrete_map={'Falsa Ocupación': 'red', 'Falsa Liberación': 'orange'}
        )
        
        fig.update_layout(
            xaxis=dict(title='Estación'),
            yaxis=dict(title='Número de fallos'),
            legend=dict(title='Tipo de fallo'),
            height=500
        )
        
        return fig

    @app.callback(
        Output('traffic-failures-correlation', 'figure'),
        [Input('date-range', 'start_date'),
        Input('date-range', 'end_date'),
        Input('station-dropdown', 'value')]
    )
    def update_traffic_failures_correlation(start_date, end_date, station):
        """Crear gráfico que muestre la correlación entre tráfico de trenes y fallos CDV"""
        # Verificar si tenemos datos de tren y fallos
        if ('combined_failures' not in data or data['combined_failures'].empty or
            'velcom_data_3d' not in data or data['velcom_data_3d'].empty):
            # Crear figura vacía si no hay datos
            fig = go.Figure()
            fig.update_layout(
                title="No hay suficientes datos para mostrar correlación",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        # Copiar los datos para no modificar los originales
        train_df = data['velcom_data_3d'].copy()
        failures_df = data['combined_failures'].copy()
        
        # Filtrar por fecha si se proporciona rango
        if start_date and end_date:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date) + pd.Timedelta(days=1)
            
            train_df = train_df[(train_df['arrival_time'] >= start_date) & 
                            (train_df['arrival_time'] <= end_date)]
            
            failures_df = failures_df[(failures_df['Fecha Hora'] >= start_date) & 
                                    (failures_df['Fecha Hora'] <= end_date)]
        
        # Filtrar por estación si está seleccionada
        if station:
            train_df = train_df[train_df['station'] == station]
            failures_df = failures_df[failures_df['station'] == station]
        
        # Verificar si hay datos después del filtrado
        if train_df.empty or failures_df.empty:
            fig = go.Figure()
            fig.update_layout(
                title="No hay datos suficientes para los filtros seleccionados",
                xaxis=dict(title=""),
                yaxis=dict(title="")
            )
            return fig
        
        # Agrupar datos de trenes por hora y estación
        train_df['hour'] = train_df['arrival_time'].dt.hour
        train_traffic = train_df.groupby(['station', 'hour']).size().reset_index(name='train_count')
        
        # Agrupar datos de fallos por hora y estación
        failures_df['hour'] = failures_df['Fecha Hora'].dt.hour
        failure_counts = failures_df.groupby(['station', 'hour', 'tipo_fallo']).size().reset_index(name='failure_count')
        
        # Combinar datos de tráfico y fallos
        merged_data = pd.merge(
            train_traffic, 
            failure_counts,
            on=['station', 'hour'],
            how='outer'
        ).fillna(0)
        
        # Crear scatter plot para mostrar correlación
        fig = px.scatter(
            merged_data,
            x='train_count',
            y='failure_count',
            color='tipo_fallo',
            hover_data=['station', 'hour'],
            title='Correlación entre tráfico de trenes y fallos CDV',
            labels={
                'train_count': 'Número de trenes', 
                'failure_count': 'Número de fallos',
                'tipo_fallo': 'Tipo de fallo'
            },
            color_discrete_map={'Falsa Ocupación': 'red', 'Falsa Liberación': 'orange'},
            trendline="ols"  # Añadir línea de tendencia
        )
        
        fig.update_layout(
            xaxis=dict(title='Número de trenes por hora'),
            yaxis=dict(title='Número de fallos'),
            legend=dict(title='Tipo de fallo'),
            height=500
        )
        
        return fig
    
    
    # Callback para actualizar gráfico de llegadas por estación
    @app.callback(
        Output('arrivals-by-station-graph', 'figure'),
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value')]
    )
    def update_arrivals_by_station(train_number, material, station):
        df = data['velcom_data'].copy()
        
        # Aplicar filtros
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
        # Contar llegadas por estación
        arrival_counts = df.groupby('station')['arrival_time'].count().reset_index()
        arrival_counts.columns = ['Estación', 'Número de Llegadas']
        arrival_counts = arrival_counts.sort_values('Número de Llegadas', ascending=False)
        
        # Crear gráfico
        fig = px.bar(
            arrival_counts, 
            x='Estación', 
            y='Número de Llegadas',
            title='Distribución de Llegadas por Estación',
            color='Número de Llegadas',
            color_continuous_scale='Greens'
        )
        
        fig.update_layout(
            xaxis_title='Estación',
            yaxis_title='Número de Llegadas',
            template='plotly_white'
        )
        
        return fig
    
    # Callback para actualizar gráfico de trayectos de trenes
    @app.callback(
        Output('train-journey-graph', 'figure'),
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value')]
    )
    def update_train_journey(train_number, material, station):
        df = data['velcom_data'].copy()
        
        # Aplicar filtros
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
        # Limitar el número de trenes para evitar gráficos sobrecargados
        if not train_number and len(df['train_number'].unique()) > 10:
            top_trains = df['train_number'].value_counts().nlargest(10).index.tolist()
            df = df[df['train_number'].isin(top_trains)]
        
        # Ordenar por tren y tiempo
        df = df.sort_values(['train_number', 'arrival_time'])
        
        # Crear gráfico de trayectos
        fig = go.Figure()
        
        # Crear una línea por cada tren
        for train in df['train_number'].unique():
            train_data = df[df['train_number'] == train]
            material_id = train_data['material'].iloc[0]
            
            # Añadir línea para el trayecto
            fig.add_trace(go.Scatter(
                x=train_data['arrival_time'],
                y=train_data['station'],
                mode='lines+markers',
                name=f'Tren {train} - {material_id}',
                hovertemplate='<b>Tren:</b> %{text}<br>' +
                             '<b>Estación:</b> %{y}<br>' +
                             '<b>Llegada:</b> %{x}<br>',
                text=[f"{train} ({material_id})" for _ in range(len(train_data))]
            ))
        
        # Personalizar layout
        fig.update_layout(
            title='Trayectos de Trenes por Estación y Tiempo',
            xaxis_title='Hora',
            yaxis_title='Estación',
            template='plotly_white',
            legend_title='Trenes',
            height=600
        )
        
        return fig
    
    @app.callback(
        Output('train-3d-graph', 'figure'),
        [Input('train-dropdown', 'value'),
        Input('material-dropdown', 'value'),
        Input('station-dropdown', 'value'),
        Input('z-axis-variable', 'value'),
        Input('show-failures-checkbox', 'value'),  # Nuevo input
        Input('date-range', 'start_date'),         # Incluir filtro de fechas
        Input('date-range', 'end_date')]
    )
    def update_train_3d_journey(train_number, material, station, z_variable, show_failures, start_date, end_date):
        df = data['velcom_data_3d'].copy()
        
        # Aplicar filtros a datos de trenes
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
        # Filtrar por fecha si se proporciona rango
        if start_date and end_date:
            start_date = pd.to_datetime(start_date)
            end_date = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # Incluir el último día completo
            df = df[(df['arrival_time'] >= start_date) & (df['arrival_time'] <= end_date)]
        
        # Si no hay datos después de filtrar, devolver figura vacía
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title='No hay datos para los filtros seleccionados',
                scene=dict(
                    xaxis_title='Hora del día',
                    yaxis_title='Estación',
                    zaxis_title='Valor'
                )
            )
            return fig
        
        # Limitar el número de trenes para evitar gráficos sobrecargados
        if not train_number and len(df['train_number'].unique()) > 5:
            top_trains = df['train_number'].value_counts().nlargest(5).index.tolist()
            df = df[df['train_number'].isin(top_trains)]
        
        # Usar el orden específico y mapeo establecido en load_data
        ordered_stations = data['ordered_stations']
        station_mapping = data['station_mapping']
        
        # Crear gráfico 3D
        fig = go.Figure()
        
        # Crear una línea 3D para cada tren
        for train in df['train_number'].unique():
            train_data = df[df['train_number'] == train].copy()
            material_id = train_data['material'].iloc[0]
            
            # Rellenar NaN con 0 para el primer registro de cada tren
            train_data['time_diff'] = train_data['time_diff'].fillna(0)
            train_data['stay_time'] = train_data['stay_time'].fillna(0)
            
            # Seleccionar la variable Z según la selección del usuario
            z_title = ''
            if z_variable == 'time_hours':
                z_values = train_data['time_hours']
                z_title = 'Hora del día'
            elif z_variable == 'time_diff':
                z_values = train_data['time_diff']
                z_title = 'Tiempo entre estaciones (min)'
            elif z_variable == 'stay_time':
                z_values = train_data['stay_time']
                z_title = 'Tiempo de permanencia (min)'
            else:  # 'speed'
                z_values = train_data['speed']
                z_title = 'Velocidad relativa'
            
            # Ajustar tamaño de los marcadores según el tiempo de permanencia
            marker_size = train_data['stay_time'] * 2 + 3  # Ajustar escala para visualización
            
            # Añadir línea 3D para el trayecto
            fig.add_trace(go.Scatter3d(
                x=train_data['time_hours'],       # Hora del día
                y=train_data['station_num'],      # Estación (convertida a número según orden específico)
                z=z_values,                       # Valor Z seleccionado
                mode='lines+markers',
                name=f'Tren {train} - {material_id}',
                line=dict(width=4),
                marker=dict(
                    size=marker_size,  # Tamaño basado en tiempo de permanencia
                    color=z_values,    # Color basado en el valor Z
                    colorscale='Viridis'
                ),
                hovertemplate='<b>Tren:</b> %{text}<br>' +
                            '<b>Hora:</b> %{x:.2f}<br>' +
                            '<b>Estación:</b> ' + train_data['station'] + '<br>' +
                            '<b>Permanencia:</b> ' + train_data['stay_time'].round(1).astype(str) + ' min<br>' +
                            '<b>' + z_title + ':</b> %{z:.2f}<br>',
                text=[f"{train} ({material_id})" for _ in range(len(train_data))]
            ))
        
        # Añadir visualización de fallos si está seleccionada y si tenemos datos de fallos
        if show_failures and ('combined_failures' in data) and not data['combined_failures'].empty:
            failures_df = data['combined_failures'].copy()
            
            # Filtrar por fecha si se proporciona rango
            if start_date and end_date:
                failures_df = failures_df[(failures_df['Fecha Hora'] >= start_date) & 
                                        (failures_df['Fecha Hora'] <= end_date)]
            
            # Filtrar por estación si está seleccionada
            if station:
                failures_df = failures_df[failures_df['station'] == station]
            
            # Añadir puntos para fallos de ocupación
            if 'fo' in show_failures:
                fo_failures = failures_df[failures_df['tipo_fallo'] == 'Falsa Ocupación']
                if not fo_failures.empty:
                    # El valor Z será basado en el mismo eje que los trenes, pero ligeramente elevado
                    # para que se vean por encima de las rutas
                    if z_variable == 'speed':
                        z_values_fo = [11] * len(fo_failures)  # Valor constante por encima del máximo de velocidad
                    elif z_variable == 'time_diff':
                        z_values_fo = fo_failures['time_hours'] * 0 + max(df[z_variable].max() * 1.1, 10)
                    elif z_variable == 'stay_time':
                        z_values_fo = fo_failures['time_hours'] * 0 + max(df[z_variable].max() * 1.1, 10)
                    else:  # time_hours - usar el valor real de la hora
                        z_values_fo = fo_failures['time_hours']
                    
                    fig.add_trace(go.Scatter3d(
                        x=fo_failures['time_hours'],
                        y=fo_failures['station_num'],
                        z=z_values_fo,
                        mode='markers',
                        name='Fallos de Ocupación',
                        marker=dict(
                            size=10,
                            symbol='circle',
                            color='red',
                            opacity=0.7
                        ),
                        hovertemplate='<b>Fallo de Ocupación</b><br>' +
                                    '<b>Hora:</b> %{x:.2f}<br>' +
                                    '<b>Estación:</b> %{text}<br>' +
                                    '<b>Equipo:</b> ' + fo_failures['Equipo'] + '<br>' +
                                    '<b>Fecha:</b> ' + fo_failures['Fecha Hora'].dt.strftime('%d-%m-%Y %H:%M:%S'),
                        text=fo_failures['station']
                    ))
            
            # Añadir puntos para fallos de liberación
            if 'fl' in show_failures:
                fl_failures = failures_df[failures_df['tipo_fallo'] == 'Falsa Liberación']
                if not fl_failures.empty:
                    # El valor Z será basado en el mismo eje que los trenes, pero ligeramente elevado
                    # y diferente a los fallos de ocupación para distinguirlos
                    if z_variable == 'speed':
                        z_values_fl = [12] * len(fl_failures)  # Valor constante por encima de FO
                    elif z_variable == 'time_diff':
                        z_values_fl = fl_failures['time_hours'] * 0 + max(df[z_variable].max() * 1.2, 12)
                    elif z_variable == 'stay_time':
                        z_values_fl = fl_failures['time_hours'] * 0 + max(df[z_variable].max() * 1.2, 12)
                    else:  # time_hours - usar el valor real de la hora
                        z_values_fl = fl_failures['time_hours']
                    
                    fig.add_trace(go.Scatter3d(
                        x=fl_failures['time_hours'],
                        y=fl_failures['station_num'],
                        z=z_values_fl,
                        mode='markers',
                        name='Fallos de Liberación',
                        marker=dict(
                            size=10,
                            symbol='diamond',
                            color='orange',
                            opacity=0.7
                        ),
                        hovertemplate='<b>Fallo de Liberación</b><br>' +
                                    '<b>Hora:</b> %{x:.2f}<br>' +
                                    '<b>Estación:</b> %{text}<br>' +
                                    '<b>Equipo:</b> ' + fl_failures['Equipo'] + '<br>' +
                                    '<b>Fecha:</b> ' + fl_failures['Fecha Hora'].dt.strftime('%d-%m-%Y %H:%M:%S'),
                        text=fl_failures['station']
                    ))
        
        # Etiquetas para el eje Y (estaciones) - Mostrar según el orden específico
        # Filtrar la lista ordenada para incluir solo las estaciones presentes en los datos
        visible_stations = [st for st in ordered_stations if st in df['station'].unique()]
        y_tickvals = [station_mapping[station] for station in visible_stations]
        y_ticktext = visible_stations
        
        # Personalizar layout
        fig.update_layout(
            title='Visualización 3D de Trayectos de Trenes y Fallos CDV',
            scene=dict(
                xaxis_title='Hora del día',
                yaxis_title='Estación',
                zaxis_title=z_title,
                xaxis=dict(
                    range=[min(df['time_hours'])-0.5, max(df['time_hours'])+0.5]
                ),
                yaxis=dict(
                    tickvals=y_tickvals,
                    ticktext=y_ticktext,
                    # Añadir esto para mejorar la legibilidad:
                    tickfont=dict(size=10),
                    # Asegúrate que el rango cubra todos los valores posibles:
                    range=[min(df['station_num'])-0.5, max(df['station_num'])+0.5]
                ),
                camera=dict(
                    eye=dict(x=1.5, y=-1.5, z=1.2)
                )
            ),
            legend=dict(
                title='Trenes y Fallos',
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01
            ),
            margin=dict(l=0, r=0, t=30, b=0),
            height=700
        )
        
        return fig
    
    # Callback para actualizar tabla de detalles de trayectos
    @app.callback(
        Output('journey-details-table', 'data'),
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value')]
    )
    def update_journey_details(train_number, material, station):
        df = data['velcom_data'].copy()
        
        # Aplicar filtros
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
        # Convertir a formato legible para la tabla
        df['arrival_time'] = df['arrival_time'].dt.strftime('%d/%m/%Y %H:%M:%S')
        df['departure_time'] = df['departure_time'].dt.strftime('%d/%m/%Y %H:%M:%S')
        
        # Ordenar por tren y tiempo de llegada
        df = df.sort_values(['train_number', 'arrival_time'])
        
        return df.to_dict('records')
    
    # Callback para limpiar filtros
    @app.callback(
        [Output('train-dropdown', 'value'),
         Output('material-dropdown', 'value'),
         Output('station-dropdown', 'value')],
        [Input('clear-filters-button', 'n_clicks')]
    )
    def clear_filters(n_clicks):
        # Si el botón no ha sido presionado, no hacer nada
        if n_clicks is None:
            return dash.no_update, dash.no_update, dash.no_update
        
        # Limpiar todos los filtros
        return None, None, None
    
    # Actualizar tablas iniciales
    @app.callback(
        [Output('trains-table', 'data'),
         Output('stations-table', 'data')],
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value')]
    )
    def update_tables(train_number, material, station):
        # Datos de trenes filtrados
        trains_df = data['velcom_trains'].copy()
        if train_number:
            trains_df = trains_df[trains_df['train_number'] == train_number]
        if material:
            trains_df = trains_df[trains_df['material'] == material]
        
        # Datos de estaciones filtrados
        stations_df = data['velcom_stations'].copy()
        if station:
            stations_df = stations_df[stations_df['station'] == station]
            
        # Si hay filtros de tren o material, filtrar estaciones relacionadas
        if train_number or material:
            filtered_df = data['velcom_data'].copy()
            if train_number:
                filtered_df = filtered_df[filtered_df['train_number'] == train_number]
            if material:
                filtered_df = filtered_df[filtered_df['material'] == material]
                
            related_stations = filtered_df['station'].unique()
            stations_df = stations_df[stations_df['station'].isin(related_stations)]
        
        # Formatear fechas para visualización
        trains_df['first_arrival'] = pd.to_datetime(trains_df['first_arrival']).dt.strftime('%d/%m/%Y %H:%M:%S')
        trains_df['last_arrival'] = pd.to_datetime(trains_df['last_arrival']).dt.strftime('%d/%m/%Y %H:%M:%S')
        
        return trains_df.to_dict('records'), stations_df.to_dict('records')
    
    # Añadir CSS para estilizar el dashboard
    app.index_string = '''
    <!DOCTYPE html>
    <html>
        <head>
            {%metas%}
            <title>{%title%}</title>
            {%favicon%}
            {%css%}
            <style>
                .dashboard-container {
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    font-family: "Segoe UI", Arial, sans-serif;
                }
                .dashboard-title {
                    text-align: center;
                    color: #2C3E50;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #3498DB;
                    margin-bottom: 20px;
                }
                .info-container {
                    margin-bottom: 20px;
                }
                .info-box {
                    background-color: #F8F9F9;
                    border-left: 5px solid #3498DB;
                    padding: 15px;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .filters-container {
                    background-color: #F8F9F9;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }
                .filters-row {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    margin-bottom: 15px;
                }
                .filter-col {
                    flex: 1;
                    min-width: 200px;
                }
                .button-container {
                    display: flex;
                    justify-content: center;
                }
                .clear-button {
                    background-color: #E74C3C;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    transition: background-color 0.3s;
                }
                .clear-button:hover {
                    background-color: #C0392B;
                }
                .tabs-container {
                    margin-top: 20px;
                }
                .tab-content {
                    display: flex;
                    flex-wrap: wrap;
                    gap: 20px;
                    padding: 20px 0;
                }
                .content-box {
                    background-color: white;
                    padding: 15px;
                    border-radius: 5px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    flex: 1 1 calc(50% - 20px);
                    min-width: 300px;
                }
                .full-width {
                    flex: 1 1 100%;
                }
                h3 {
                    color: #2C3E50;
                    border-bottom: 1px solid #EAECEE;
                    padding-bottom: 10px;
                    margin-top: 0;
                }
            </style>
        </head>
        <body>
            {%app_entry%}
            <footer>
                {%config%}
                {%scripts%}
                {%renderer%}
            </footer>
        </body>
    </html>
    '''
    
    return app

def open_browser(port):
    """Abrir navegador en la URL del dashboard"""
    webbrowser.open_new(f"http://localhost:{port}")

def launch_velcom_dashboard(data_path, port=8055):
    """Lanzar dashboard de Velcom"""
    # Crear la aplicación
    app = create_dashboard(data_path)
    
    # Abrir navegador después de 1 segundo
    Timer(1, open_browser, [port]).start()
    
    # Ejecutar servidor
    app.run_server(debug=False, port=port)