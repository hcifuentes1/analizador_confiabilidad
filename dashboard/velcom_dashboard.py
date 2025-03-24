# dashboard/velcom_dashboard.py
import os
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
import webbrowser
from threading import Timer
import plotly.graph_objs as go

def load_data(data_path):
    """Cargar datos procesados de Velcom y preparar para visualización 3D"""
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
    
    # 2.7 Crear mapeo numérico de estaciones para visualización 3D
    all_stations = sorted(df_3d_processed['station'].unique())
    station_mapping = {station: i for i, station in enumerate(all_stations)}
    df_3d_processed['station_num'] = df_3d_processed['station'].map(station_mapping)
    
    # 2.8 Llenar valores NaN en datos críticos
    for col in ['time_diff', 'stay_time', 'speed']:
        df_3d_processed[col] = df_3d_processed[col].fillna(0)
    
    # 3. Guardar los datos procesados
    data['velcom_data_3d'] = df_3d_processed
    data['station_mapping'] = station_mapping
    
    return data

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
                        dcc.Graph(id='train-3d-graph', style={'height': '700px'})
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
    
    # Callback para actualizar gráfico 3D de trayectos de trenes
    @app.callback(
        Output('train-3d-graph', 'figure'),
        [Input('train-dropdown', 'value'),
         Input('material-dropdown', 'value'),
         Input('station-dropdown', 'value'),
         Input('z-axis-variable', 'value')]
    )
    def update_train_3d_journey(train_number, material, station, z_variable):
        df = data['velcom_data'].copy()
        
        # Aplicar filtros
        if train_number:
            df = df[df['train_number'] == train_number]
        if material:
            df = df[df['material'] == material]
        if station:
            df = df[df['station'] == station]
        
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
        
        # Convertir estaciones a valores numéricos para el eje Y
        all_stations = sorted(df['station'].unique())
        station_mapping = {station: i for i, station in enumerate(all_stations)}
        df['station_num'] = df['station'].map(station_mapping)
        
        # Calcular tiempo desde el inicio del día para cada evento (en horas)
        df['time_hours'] = df['arrival_time'].dt.hour + df['arrival_time'].dt.minute/60
        
        # Calcular diferencia en tiempo con el registro anterior para el mismo tren
        df = df.sort_values(['train_number', 'arrival_time'])
        df['prev_time'] = df.groupby('train_number')['arrival_time'].shift(1)
        df['time_diff'] = (df['arrival_time'] - df['prev_time']).dt.total_seconds() / 60  # en minutos
        
        # Calcular tiempo de permanencia en cada estación
        df['stay_time'] = (df['departure_time'] - df['arrival_time']).dt.total_seconds() / 60  # en minutos
        
        # Crear gráfico 3D
        fig = go.Figure()
        
        # Crear una línea 3D para cada tren
        for train in df['train_number'].unique():
            train_data = df[df['train_number'] == train].copy()
            material_id = train_data['material'].iloc[0]
            
            # Rellenar NaN con 0 para el primer registro de cada tren
            train_data['time_diff'] = train_data['time_diff'].fillna(0)
            train_data['stay_time'] = train_data['stay_time'].fillna(0)
            
            # Calcular velocidad "relativa"
            if len(train_data) > 1:
                max_time = train_data['time_diff'].max()
                if max_time > 0:
                    train_data['speed'] = 10 * (1 - train_data['time_diff'] / max_time) + 1
                else:
                    train_data['speed'] = 1
            else:
                train_data['speed'] = 1
            
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
                y=train_data['station_num'],      # Estación (convertida a número)
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
        
        # Etiquetas para el eje Y (estaciones)
        y_tickvals = list(station_mapping.values())
        y_ticktext = list(station_mapping.keys())
        
        # Personalizar layout
        fig.update_layout(
            title='Visualización 3D de Trayectos de Trenes',
            scene=dict(
                xaxis_title='Hora del día',
                yaxis_title='Estación',
                zaxis_title=z_title,
                xaxis=dict(
                    range=[min(df['time_hours'])-0.5, max(df['time_hours'])+0.5]
                ),
                yaxis=dict(
                    tickvals=y_tickvals,
                    ticktext=y_ticktext
                ),
                camera=dict(
                    eye=dict(x=1.5, y=-1.5, z=1.2)
                )
            ),
            legend_title='Trenes',
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