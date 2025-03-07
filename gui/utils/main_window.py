# gui/main_window.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
from datetime import datetime
from ttkthemes import ThemedTk

from processors.cdv_processor_l5 import CDVProcessorL5
from processors.adv_processor_l5 import ADVProcessorL5
from processors.cdv_processor_l1 import CDVProcessorL1
from processors.adv_processor_l1 import ADVProcessorL1
from gui.line_tabs import LineTab
from utils.config import Config

class MetroAnalyzerApp:
    """Aplicación principal para análisis de datos del Metro"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Metro de Santiago - Analizador SCADA")
        self.root.geometry("1000x700")
        self.root.minsize(900, 600)
        
        # Cargar configuración
        self.config = Config()
        
        # Variables para seguimiento de progreso
        self.message_queue = queue.Queue()
        self.processing_thread = None
        
        # Procesdores para cada línea y tipo de análisis
        self.processors = {
            "L1": {
                "CDV": CDVProcessorL1(),
                "ADV": ADVProcessorL1()
            },
            "L5": {
                "CDV": CDVProcessorL5(),
                "ADV": ADVProcessorL5()
            }
        }
        
        # Crear interfaz
        self.create_widgets()
        
        # Configurar actualización de mensajes
        self.root.after(100, self.check_message_queue)
    
    def create_widgets(self):
        """Crear los widgets de la interfaz de usuario"""
        # Crear notebook (pestañas)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Crear pestañas para cada línea
        self.tabs = {
            "L1": LineTab(self.notebook, "Línea 1", self),
            "L2": LineTab(self.notebook, "Línea 2", self, enabled=False),
            "L4": LineTab(self.notebook, "Línea 4", self, enabled=False),
            "L4A": LineTab(self.notebook, "Línea 4A", self, enabled=False),
            "L5": LineTab(self.notebook, "Línea 5", self)
        }
        
        # Añadir pestañas al notebook
        for line, tab in self.tabs.items():
            self.notebook.add(tab.frame, text=tab.title)
    
    def check_message_queue(self):
        """Verificar mensajes en la cola y actualizar la UI"""
        try:
            while not self.message_queue.empty():
                line, analysis_type, progress, message = self.message_queue.get_nowait()
                
                # Actualizar UI en la pestaña correspondiente
                if line in self.tabs:
                    self.tabs[line].update_progress(analysis_type, progress, message)
                
                # Marcar mensaje como procesado
                self.message_queue.task_done()
        except Exception as e:
            print(f"Error al procesar mensajes: {str(e)}")
        
        # Programar próxima verificación
        self.root.after(100, self.check_message_queue)
    
    def start_processing(self, line, analysis_type, source_path, dest_path, parameters=None):
        """Iniciar procesamiento para una línea y tipo de análisis específico"""
        # Verificar si existe el procesador para la combinación
        if line not in self.processors or analysis_type not in self.processors[line]:
            messagebox.showerror("Error", f"No se encontró un procesador para Línea {line}, tipo {analysis_type}")
            return False
        
        # Obtener el procesador adecuado
        processor = self.processors[line][analysis_type]
        
        # Configurar rutas
        processor.set_paths(source_path, dest_path)
        
        # Configurar parámetros adicionales si existen
        if parameters:
            for param, value in parameters.items():
                if hasattr(processor, param):
                    setattr(processor, param, value)
        
        # Iniciar procesamiento en un hilo separado
        self.processing_thread = threading.Thread(
            target=self.run_processing,
            args=(line, analysis_type, processor)
        )
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        return True
    
    def run_processing(self, line, analysis_type, processor):
        """Ejecutar procesamiento en segundo plano"""
        try:
            # Función anónima para retransmitir actualizaciones de progreso
            progress_callback = lambda progress, message: self.message_queue.put((line, analysis_type, progress, message))
            
            # Ejecutar procesamiento
            success = processor.process_data(progress_callback)
            
            if success:
                progress_callback(100, f"Procesamiento de {analysis_type} completado con éxito")
            else:
                progress_callback(0, "Error en el procesamiento")
        except Exception as e:
            self.message_queue.put((line, analysis_type, 0, f"Error: {str(e)}"))