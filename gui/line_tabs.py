# gui/line_tabs.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

class LineTab:
    """Clase para gestionar las pestañas de cada línea"""
    
    def __init__(self, notebook, title, parent_app, enabled=True):
        self.notebook = notebook
        self.title = title
        self.parent_app = parent_app
        self.enabled = enabled
        
        # Variables para rutas y configuración
        self.source_path_var = tk.StringVar()
        self.dest_path_var = tk.StringVar()
        self.f_oc_1_var = tk.StringVar(value="0.1")
        self.f_lb_2_var = tk.StringVar(value="0.05")
        self.analysis_type_var = tk.StringVar(value="CDV")
        
        # Variables para seguimiento de progreso
        self.progress_var = tk.DoubleVar()
        self.status_var = tk.StringVar(value="Listo para procesar")
        
        # Crear el frame principal para la pestaña
        self.frame = ttk.Frame(notebook)
        
        if enabled:
            self.create_widgets()
        else:
            self.create_disabled_widgets()
    
    def create_widgets(self):
        """Crear los widgets de la interfaz para una línea habilitada"""
        # Marco principal
        main_frame = ttk.Frame(self.frame, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Sección de selección de análisis
        analysis_frame = ttk.LabelFrame(main_frame, text="Tipo de Análisis", padding="10")
        analysis_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Radio buttons para seleccionar CDV o ADV
        ttk.Radiobutton(analysis_frame, text="Circuitos de Vía (CDV)", variable=self.analysis_type_var, 
                       value="CDV", command=self.toggle_analysis_type).grid(row=0, column=0, padx=20, pady=5, sticky=tk.W)
        ttk.Radiobutton(analysis_frame, text="Agujas (ADV)", variable=self.analysis_type_var, 
                       value="ADV", command=self.toggle_analysis_type).grid(row=0, column=1, padx=20, pady=5, sticky=tk.W)
        
        # Sección de selección de carpetas
        folder_frame = ttk.LabelFrame(main_frame, text="Rutas de archivos", padding="10")
        folder_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Ruta de origen
        ttk.Label(folder_frame, text="Carpeta de origen:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.source_path_var, width=60).grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(folder_frame, text="Examinar...", command=self.browse_source).grid(row=0, column=2, padx=5, pady=5)
        
        # Ruta de destino
        ttk.Label(folder_frame, text="Carpeta de destino:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(folder_frame, textvariable=self.dest_path_var, width=60).grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(folder_frame, text="Examinar...", command=self.browse_dest).grid(row=1, column=2, padx=5, pady=5)
        
        # Marco para configuración de parámetros CDV
        self.cdv_config_frame = ttk.LabelFrame(main_frame, text="Configuración CDV", padding="10")
        self.cdv_config_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Factor de umbral para ocupación
        ttk.Label(self.cdv_config_frame, text="Factor umbral ocupación (f_oc_1):").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.cdv_config_frame, textvariable=self.f_oc_1_var, width=10).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(self.cdv_config_frame, 
                 text="Valor entre 0 y 1. Menor valor = más sensible en detección de fallos de ocupación").grid(
            row=0, column=2, sticky=tk.W, padx=10)
        
        # Factor de umbral para liberación
        ttk.Label(self.cdv_config_frame, text="Factor umbral liberación (f_lb_2):").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Entry(self.cdv_config_frame, textvariable=self.f_lb_2_var, width=10).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(self.cdv_config_frame, 
                 text="Valor entre 0 y 1. Menor valor = más sensible en detección de fallos de liberación").grid(
            row=1, column=2, sticky=tk.W, padx=10)
        
        # Sección de control
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Barra de progreso
        self.progress_bar = ttk.Progressbar(control_frame, variable=self.progress_var, length=600, mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        # Etiqueta de estado
        status_label = ttk.Label(control_frame, textvariable=self.status_var, wraplength=900)
        status_label.pack(fill=tk.X, pady=5)
        
        # Área de log
        log_frame = ttk.LabelFrame(main_frame, text="Registro de actividad", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Área de texto con scroll para el log
        self.log_text = tk.Text(log_frame, height=10, width=80, wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Botones de acción
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Analizar datos", command=self.start_processing).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Limpiar log", command=self.clear_log).pack(side=tk.RIGHT, padx=5)
        
        # Área de visualización de resultados
        self.results_frame = ttk.LabelFrame(main_frame, text="Visualización de resultados", padding="10")
        
        # Inicialmente oculto hasta que haya resultados
        self.results_frame.pack_forget()
    
    def create_disabled_widgets(self):
        """Crear widgets para pestañas deshabilitadas"""
        ttk.Label(self.frame, text=f"Análisis de {self.title} en desarrollo...", font=("Helvetica", 14)).pack(pady=100)
        ttk.Button(self.frame, text="Volver a Línea 5", command=lambda: self.notebook.select(4)).pack()
    
    def toggle_analysis_type(self):
        """Cambiar configuración según el tipo de análisis seleccionado"""
        analysis_type = self.analysis_type_var.get()
        
        if analysis_type == "CDV":
            self.cdv_config_frame.pack(fill=tk.X, padx=5, pady=5)
            self.log(f"Tipo de análisis seleccionado: Circuitos de Vía (CDV)")
        else:
            self.cdv_config_frame.pack_forget()
            self.log(f"Tipo de análisis seleccionado: Agujas (ADV)")
    
    def browse_source(self):
        """Abrir diálogo para seleccionar carpeta de origen"""
        folder_path = filedialog.askdirectory(title="Seleccionar carpeta de origen")
        if folder_path:
            self.source_path_var.set(folder_path)
            self.log(f"Carpeta de origen seleccionada: {folder_path}")
    
    def browse_dest(self):
        """Abrir diálogo para seleccionar carpeta de destino"""
        folder_path = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if folder_path:
            self.dest_path_var.set(folder_path)
            self.log(f"Carpeta de destino seleccionada: {folder_path}")
    
    def log(self, message):
        """Añadir mensaje al área de log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
    
    def clear_log(self):
        """Limpiar el área de log"""
        self.log_text.delete(1.0, tk.END)
        self.log("Log limpiado")
    
    def update_progress(self, analysis_type, progress, message):
        """Actualizar barra de progreso y mensaje de estado"""
        current_analysis_type = self.analysis_type_var.get()
        
        # Solo actualizar si corresponde al tipo de análisis actual
        if analysis_type == current_analysis_type:
            if progress is not None:
                self.progress_var.set(progress)
            
            if message:
                self.status_var.set(message)
                self.log(message)
    
    def start_processing(self):
        """Iniciar procesamiento de datos"""
        # Verificar que se hayan seleccionado las carpetas
        source_path = self.source_path_var.get()
        dest_path = self.dest_path_var.get()
        
        if not source_path or not os.path.exists(source_path):
            messagebox.showerror("Error", "Seleccione una carpeta de origen válida")
            return
        
        if not dest_path or not os.path.exists(dest_path):
            messagebox.showerror("Error", "Seleccione una carpeta de destino válida")
            return
        
        # Obtener datos para procesamiento
        line = self.title.replace("Línea ", "L")
        analysis_type = self.analysis_type_var.get()
        
        # Verificar umbrales para CDV
        parameters = {}
        if analysis_type == "CDV":
            try:
                f_oc_1 = float(self.f_oc_1_var.get())
                f_lb_2 = float(self.f_lb_2_var.get())
                
                if not (0 < f_oc_1 <= 1) or not (0 < f_lb_2 <= 1):
                    messagebox.showerror("Error", "Los factores de umbral deben estar entre 0 y 1")
                    return
                
                parameters = {
                    'f_oc_1': f_oc_1,
                    'f_lb_2': f_lb_2
                }
            except ValueError:
                messagebox.showerror("Error", "Los factores de umbral deben ser valores numéricos")
                return
        
        # Reiniciar la barra de progreso
        self.progress_var.set(0)
        self.status_var.set(f"Iniciando procesamiento para {analysis_type}...")
        
        # Iniciar procesamiento
        success = self.parent_app.start_processing(line, analysis_type, source_path, dest_path, parameters)
        
        if not success:
            self.log("Error al iniciar el procesamiento")