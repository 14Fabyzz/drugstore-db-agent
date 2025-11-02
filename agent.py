"""
Agente MCP - Model Context Protocol
Soporta SQLite y MySQL
"""
from typing import List, Dict, Any, Optional
from models.gemini import GeminiModel
from tools.database import DatabaseTool
from tools.mysql_tool import MySQLTool
import json
from decimal import Decimal
from datetime import date, datetime # <-- 1. IMPORTAR DATE/DATETIME

# 2. CLASE DE CODIFICADOR MEJORADA
class CustomDecimalEncoder(json.JSONEncoder):
    """
    Codificador de JSON personalizado para manejar objetos Decimal y Date/Datetime.
    """
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat() # Convierte la fecha a un string estándar
        return super().default(obj)

class MCPAgent:
    """
    Agente con arquitectura MCP simplificada
    ...
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: str,
        db_type: str = 'sqlite',
        db_path: Optional[str] = None,
        mysql_config: Optional[Dict] = None
    ):
        # ... (El resto de __init__ está bien, no hay cambios) ...
        # Modelo de IA
        self.model = GeminiModel(api_key, model_name)
        
        # Herramientas disponibles
        self.tools = {}
        self.db_type = db_type
        
        # Configurar la herramienta de base de datos según el tipo
        if db_type == 'sqlite':
            if not db_path:
                raise ValueError("db_path es requerido para SQLite")
            self.tools["database"] = DatabaseTool(db_path)
            print(f"📊 Usando SQLite: {db_path}")
        
        elif db_type == 'mysql':
            if not mysql_config:
                raise ValueError("mysql_config es requerido para MySQL")
            self.tools["database"] = MySQLTool(**mysql_config)
            print(f"📊 Usando MySQL: {mysql_config['database']}")
        
        else:
            raise ValueError(f"Tipo de BD no soportado: {db_type}")
        
        # Contexto de la conversación
        self.context: List[Dict[str, str]] = []
        self.max_context = 10
    
    # --- 3. FUNCIÓN ASK() REESTRUCTURADA Y CORREGIDA ---
    def ask(self, question: str) -> str:
        """
        Pregunta principal del agente (con auto-corrección y manejo de errores)
        """
        print(f"\n🤔 Pregunta: {question}")
        self._add_to_context("user", question)
        
        response_text = "" # Inicializar la variable de respuesta

        try:
            # --- 2. Generar SQL (Intento 1) ---
            print("⚙️  Generando consulta SQL (Intento 1)...")
            sql = self._generate_sql(question)
            
            if sql == "NO_QUERY":
                response_text = "No puedo responder esa pregunta con los datos disponibles."
            else:
                print(f"📊 SQL (Intento 1): {sql}")
                results = self.tools["database"].execute(sql)
                
                # --- 4. Lógica de Auto-Corrección ---
                if results and "error" in results[0]:
                    original_error = results[0]['error']
                    print(f"⚠️ Error en SQL (Intento 1): {original_error}")
                    print("⚙️  Generando consulta SQL (Intento 2: Corrección)...")

                    correction_prompt = self._generate_sql_correction_prompt(question, sql, original_error)
                    corrected_sql = self.model.ask(correction_prompt, self.context)
                    
                    if corrected_sql.startswith("```sql"):
                        corrected_sql = corrected_sql.replace("```sql", "").replace("```", "").strip()
                    elif corrected_sql.startswith("```"):
                        corrected_sql = corrected_sql.replace("```", "").strip()

                    if corrected_sql == "NO_QUERY":
                        response_text = f"Intenté corregir un error, pero no pude encontrar una respuesta ({original_error})."
                    else:
                        print(f"📊 SQL (Intento 2): {corrected_sql}")
                        results = self.tools["database"].execute(corrected_sql)
                        sql = corrected_sql

                        if results and "error" in results[0]:
                            final_error = results[0]['error']
                            print(f"❌ Error en SQL (Intento 2): {final_error}")
                            response_text = f"Error al ejecutar la consulta corregida: {final_error}"
                
                # --- 6. Generar Respuesta Natural (si no hubo error) ---
                if not response_text: # Si no hemos asignado un error
                    print(f"✅ Resultados: {len(results)} filas")
                    response_text = self._generate_response(question, sql, results)

        except Exception as e:
            # Captura cualquier error inesperado (como los de JSON)
            print(f"❌ Ocurrió una excepción inesperada en 'ask': {e}")
            response_text = "Lo siento, ocurrió un error interno al procesar tu solicitud."

        # --- 7. Limpieza y Contexto (Ahora en un lugar seguro) ---
        
        # Limpiar el ````json````
        if response_text.strip().startswith("```json"):
            print("Limpiando JSON envuelto en markdown...")
            response_text = response_text.strip().replace("```json", "").replace("```", "").strip()
        
        self._add_to_context("assistant", response_text)
        return response_text
    
    def _generate_sql(self, question: str) -> str:
        # ... (Esta función está bien, no hay cambios) ...
        schema = self.tools["database"].get_schema()
        
        db_hint = "MySQL" if self.db_type == 'mysql' else "SQLite"
        
        prompt = f"""Eres un experto en SQL para {db_hint}. 

{schema}

Pregunta: {question}

Genera SOLO la consulta SQL (sin explicaciones). 
Si no se puede responder, devuelve: NO_QUERY
Solo usa SELECT (no DELETE, UPDATE, DROP).
"""
        
        sql = self.model.ask(prompt, self.context)
        
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        
        return sql
    
    def _generate_sql_correction_prompt(self, question: str, bad_sql: str, error: str) -> str:
        # ... (Esta función está bien, no hay cambios) ...
        schema = self.tools["database"].get_schema()
        db_hint = "MySQL" if self.db_type == 'mysql' else "SQLite"

        return f"""Eres un experto en SQL para {db_hint}.
{schema}

El usuario preguntó: {question}

Se intentó ejecutar la siguiente consulta:
{bad_sql}

Pero falló con este error:
{error}

Por favor, corrige la consulta SQL. Genera SOLO la consulta SQL corregida (sin explicaciones).
Si no se puede responder, devuelve: NO_QUERY
"""

    # --- 4. FUNCIÓN _generate_response() CORREGIDA ---
    def _generate_response(self, question: str, sql: str, results: List[Dict]) -> str:
        """
        Genera respuesta en lenguaje natural.
        Decide si la respuesta es texto, tabla o gráfico.
        """
        
        # Usamos json.dumps() CON EL CODIFICADOR PERSONALIZADO
        results_str = json.dumps(results, cls=CustomDecimalEncoder)
        
        if len(results_str) > 3000:
            results_str = results_str[:3000] + "... (resultados truncados)"
        
        prompt_header = f"""El usuario preguntó: {question}
Se ejecutó: {sql}
Resultados: """
        
        # --- INICIO DE LA LÓGICA MODIFICADA ---
        # "Relajamos" la regla: ahora permitimos gráficos con 1 o más filas.
        prompt_body = """

Eres un asistente de análisis de datos. Tu tarea es analizar la PREGUNTA del usuario y los RESULTADOS de la base de datos, 
y decidir la mejor forma de presentarlos.

REGLAS DE DECISIÓN:

1.  **RESPUESTA TIPO 'chart' (Gráfico):**
    * **Cuándo usarlo:** Úsalo si la PREGUNTA pide explícitamente un "reporte", "análisis", "resumen gráfico", "comparativa", "ventas por día", "cantidad por X", etc.
    * **Y ADEMÁS:** Los RESULTADOS son una agregación (GROUP BY) o una serie de tiempo con **1 O MÁS FILAS**. 
    * **Formato:** `{"type": "chart", "chart_type": "bar", "title": "...", "content": [resultados], "label_key": "columna_X", "data_key": "columna_Y"}`
    * (Usa "line" como `chart_type` si son ventas por fecha).

2.  **RESPUESTA TIPO 'table' (Tabla):**
    * **Cuándo usarlo:** Úsalo si la PREGUNTA pide "listar", "mostrar todos", "ver los...", etc.
    * **Y ADEMÁS:** Los RESULTADOS son una lista (múltiples filas) pero la pregunta no pedía un "análisis" (ej. una lista de productos).
    * **Formato:** `{"type": "table", "title": "...", "content": [resultados]}`

3.  **RESPUESTA TIPO 'text' (Texto Plano):**
    * **Cuándo usarlo:** Úsalo para todo lo demás.
    * **Ejemplos:**
        * Si la PREGUNTA es por un dato específico ("¿cuál es el precio de X?").
        * Si los RESULTADOS son un solo número (un `COUNT` o `SUM` total, ej: `[{"count": 5}]`).
        * Si no hay resultados (`[]`).
        * Si la PREGUNTA es "¿cuántos productos hay?" y Resultados es `[{"count": 5}]`.

INSTRUCCIÓN FINAL: Responde SOLAMENTE con el formato JSON (para 'chart' o 'table') o con el texto plano (para 'text').

EJEMPLOS:
-   Pregunta: "¿Cuántos productos hay?" Resultados: [{"count": 5}] -> Respuesta: Hay 5 productos en total.
-   Pregunta: "Lístame los productos" Resultados: [20 filas de productos] -> Respuesta: {"type": "table", "title": "Lista de Productos", "content": [20 filas de productos]}
-   Pregunta: "Dame un reporte de ventas por día" Resultados: [{"fecha": "2025-10-15", "total": 18600.00}] -> (¡AHORA SÍ ES GRÁFICO!) -> Respuesta: {"type": "chart", "chart_type": "bar", "title": "Reporte de Ventas por Día", "content": [{"fecha": "2025-10-15", "total": 18600.00}], "label_key": "fecha", "data_key": "total"}
"""
        # --- FIN DE LA LÓGICA MODIFICADA ---
        
        prompt = prompt_header + results_str + prompt_body
        
        return self.model.ask(prompt, self.context)
    
    def _add_to_context(self, role: str, content: str):
        # ... (Esta función está bien, no hay cambios) ...
        self.context.append({"role": role, "content": content})
        
        if len(self.context) > self.max_context:
            self.context = self.context[-self.max_context:]
    
    def add_tool(self, name: str, tool: Any):
        # ... (Esta función está bien, no hay cambios) ...
        self.tools[name] = tool
        print(f"✅ Herramienta '{name}' agregada")
    
    def get_context_summary(self) -> Dict:
        # ... (Esta función está bien, no hay cambios) ...
        return {
            "messages": len(self.context),
            "database_type": self.db_type,
            "tools": list(self.tools.keys())
        }
    
    def clear_context(self):
        # ... (Esta función está bien, no hay cambios) ...
        self.context = []
        print("🧹 Contexto limpiado")
    
    def close(self):
        # ... (Esta función está bien, no hay cambios) ...
        for tool in self.tools.values():
            if hasattr(tool, 'close'):
                tool.close()