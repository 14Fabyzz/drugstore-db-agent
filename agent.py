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
        # Obtener el esquema actual de la BD
        schema = self.tools["database"].get_schema()
        
        db_hint = "MySQL" if self.db_type == 'mysql' else "SQLite"
        
        # --- INICIO DEL PROMPT EXPERTO LEGACY PHARMACY ---
        system_instruction = f"""
Eres un asistente experto en gestión de inventario para "Legacy Pharmacy" usando {db_hint}.
Tu trabajo es generar consultas SQL precisas para responder preguntas sobre productos, stock y vencimientos.

AQUÍ ESTÁ EL ESQUEMA DE LA BASE DE DATOS:
{schema}

REGLAS EXPERTAS (PRIORIDAD ALTA):
1. **PARA CONSULTAR STOCK:** Usa SIEMPRE la vista `v_stock_productos`.
   - Columna `stock_total` tiene la cantidad real.
   - Columna `nivel_stock` te dice si es BAJO, OK o SIN_STOCK.
   - Ejemplo: SELECT * FROM v_stock_productos WHERE nombre_comercial LIKE '%Dolex%';

2. **PARA VENCIMIENTOS:** Usa SIEMPRE la vista `v_semaforo_vencimientos`.
   - Tiene columnas: `dias_restantes`, `color_alerta` (ROJO/AMARILLO/VERDE) y `accion_sugerida`.
   - Ejemplo: SELECT * FROM v_semaforo_vencimientos WHERE color_alerta = 'ROJO';

3. **PARA PRECIOS O DETALLES:** Usa la tabla `productos` o `v_stock_productos`.

4. **MODIFICACIONES:**
   - Puedes generar `INSERT` o `UPDATE` si el usuario lo pide explícitamente.
   - NO uses `DELETE`, `DROP` o `ALTER`.

Pregunta del usuario: {question}

Genera SOLO la consulta SQL (sin explicaciones ni formato markdown).
Si no se puede responder, devuelve: NO_QUERY
"""
        # --- FIN DEL PROMPT ---
        
        sql = self.model.ask(system_instruction, self.context)
        
        # Limpieza de markdown (por si acaso Gemini lo pone)
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
        Genera respuesta. Intercepta INSERT/UPDATE para pedir confirmación.
        Decide si la respuesta es texto, tabla o gráfico.
        """
        
        # --- ¡NUEVA LÓGICA DE INTERCEPCIÓN! ---
        sql_upper = sql.strip().upper()
        if sql_upper.startswith("INSERT") or sql_upper.startswith("UPDATE"):
            
            # ¡IMPORTANTE! Generamos el JSON de confirmación
            # Usamos json.dumps para asegurarnos de que el SQL
            # (que puede tener comillas) se guarde como un string JSON válido.
            
            confirm_data = {
                "type": "confirm",
                "title": "Confirmación Requerida",
                "message": "Estoy a punto de realizar la siguiente operación en la base de datos:",
                "sql_query": sql 
            }
            # Devolvemos el JSON de confirmación como un string
            return json.dumps(confirm_data)

        # --- FIN DE LA LÓGICA DE INTERCEPCIÓN ---
        
        # (El resto de la función es la misma lógica de siempre
        # para texto, tablas y gráficos, que solo se ejecutará
        # si el SQL fue un SELECT)
        
        results_str = json.dumps(results, cls=CustomDecimalEncoder)
        
        if len(results_str) > 3000:
            results_str = results_str[:3000] + "... (resultados truncados)"
        
        prompt_header = f"""El usuario preguntó: {question}
Se ejecutó: {sql}
Resultados: """
        
        prompt_body = """

Eres un asistente de análisis de datos. Tu tarea es analizar la PREGUNTA del usuario y los RESULTADOS de la base de datos, 
y decidir la mejor forma de presentarlos.

REGLAS DE DECISIÓN: (Has interceptado INSERT/UPDATE, ahora solo decides para SELECT)

1.  **RESPUESTA TIPO 'chart' (Gráfico):**
    * **Cuándo usarlo:** Si la PREGUNTA pide "reporte", "análisis", etc., y los RESULTADOS son una agregación con 1 O MÁS FILAS.
    * **Formato:** `{"type": "chart", "chart_type": "bar", "title": "...", "content": [resultados], "label_key": "columna_X", "data_key": "columna_Y"}`

2.  **RESPUESTA TIPO 'table' (Tabla):**
    * **Cuándo usarlo:** Si la PREGUNTA pide "listar", "mostrar todos", etc.
    * **Formato:** `{"type": "table", "title": "...", "content": [resultados]}`

3.  **RESPUESTA TIPO 'text' (Texto Plano):**
    * **Cuándo usarlo:** Para todo lo demás (datos únicos, conteos totales, sin resultados).

INSTRUCCIÓN FINAL: Responde SOLAMENTE con el formato JSON (para 'chart' o 'table') o con el texto plano (para 'text').
... (El resto de tus EJEMPLOS no cambia) ...
"""
        
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