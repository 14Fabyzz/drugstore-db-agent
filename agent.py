"""
Agente MCP - Model Context Protocol
Soporta SQLite y MySQL
"""
from typing import List, Dict, Any, Optional
from models.gemini import GeminiModel
from tools.database import DatabaseTool
from tools.mysql_tool import MySQLTool


class MCPAgent:
    """
    Agente con arquitectura MCP simplificada
    - Soporta SQLite y MySQL
    - Mantiene contexto de la conversación
    - Coordina entre el modelo y las herramientas
    - Escalable: fácil agregar nuevas tools
    """
    
    def __init__(
        self,
        api_key: str,
        model_name: str,
        db_type: str = 'sqlite',
        db_path: Optional[str] = None,
        mysql_config: Optional[Dict] = None
    ):
        """
        Inicializa el agente
        
        Args:
            api_key: API key de Gemini
            model_name: Nombre del modelo de Gemini
            db_type: Tipo de BD ('sqlite' o 'mysql')
            db_path: Ruta para SQLite
            mysql_config: Configuración para MySQL
        """
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
    
    def ask(self, question: str) -> str:
        """
        Pregunta principal del agente (con lógica de auto-corrección)
        """
        print(f"\n🤔 Pregunta: {question}")
        
        # 1. Agregar pregunta al contexto
        self._add_to_context("user", question)
        
        # --- 2. Generar SQL (Intento 1) ---
        print("⚙️  Generando consulta SQL (Intento 1)...")
        sql = self._generate_sql(question)
        
        if sql == "NO_QUERY":
            response = "No puedo responder esa pregunta con los datos disponibles."
            self._add_to_context("assistant", response)
            return response
        
        print(f"📊 SQL (Intento 1): {sql}")
        
        # --- 3. Ejecutar en la BD (Intento 1) ---
        results = self.tools["database"].execute(sql)
        
        # --- 4. Lógica de Auto-Corrección ---
        # Si el primer intento falló (devuelve un dict con 'error')
        if results and "error" in results[0]:
            original_error = results[0]['error']
            print(f"⚠️ Error en SQL (Intento 1): {original_error}")
            print("⚙️  Generando consulta SQL (Intento 2: Corrección)...")

            # Crear el prompt de corrección
            correction_prompt = self._generate_sql_correction_prompt(question, sql, original_error)
            
            # Pedir a la IA que corrija el SQL (usando el contexto completo)
            corrected_sql = self.model.ask(correction_prompt, self.context)
            
            # Limpiar el SQL corregido (por si acaso)
            if corrected_sql.startswith("```sql"):
                corrected_sql = corrected_sql.replace("```sql", "").replace("```", "").strip()
            elif corrected_sql.startswith("```"):
                corrected_sql = corrected_sql.replace("```", "").strip()

            if corrected_sql == "NO_QUERY":
                response = f"Intenté corregir un error, pero no pude encontrar una respuesta ({original_error})."
                self._add_to_context("assistant", response)
                return response

            print(f"📊 SQL (Intento 2): {corrected_sql}")
            
            # --- 5. Ejecutar en la BD (Intento 2) ---
            results = self.tools["database"].execute(corrected_sql)
            sql = corrected_sql # Actualizamos el SQL para la respuesta final

            # Si vuelve a fallar, nos rendimos
            if results and "error" in results[0]:
                final_error = results[0]['error']
                print(f"❌ Error en SQL (Intento 2): {final_error}")
                response = f"Error al ejecutar la consulta corregida: {final_error}"
                self._add_to_context("assistant", response)
                return response
        
        # --- 6. Generar Respuesta Natural ---
        print(f"✅ Resultados: {len(results)} filas")
        
        response = self._generate_response(question, sql, results)
        
        # 7. Agregar respuesta al contexto
        self._add_to_context("assistant", response)
        
        return response
    
    def _generate_sql(self, question: str) -> str:
        """Genera SQL usando el modelo"""
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
        
        # Limpiar
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        
        return sql
    
    def _generate_sql_correction_prompt(self, question: str, bad_sql: str, error: str) -> str:
        """Genera un prompt para que la IA corrija un SQL erróneo."""
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

    def _generate_response(self, question: str, sql: str, results: List[Dict]) -> str:
        """
        Genera respuesta en lenguaje natural.
        Si los resultados son tabulares, devuelve un JSON string.
        De lo contrario, devuelve texto plano.
        """
        
        # Convertir resultados a un string para el prompt
        results_str = str(results)
        
        # Si los resultados son muy largos, cortarlos para el prompt
        if len(results_str) > 3000:
            results_str = results_str[:3000] + "... (resultados truncados)"
        
        # --- INICIO DE LA CORRECCIÓN ---
        # NO PODEMOS USAR F-STRINGS (f"...") para el prompt principal
        # porque la variable 'results_str' puede contener llaves {}
        # que rompen el formateador de f-string (Error 500).
        # Usaremos concatenación de strings normal.
        
        # 1. Definir las partes del prompt por separado
        # Esta parte sí puede ser f-string porque question y sql son seguros
        prompt_header = f"""El usuario preguntó: {question}
Se ejecutó: {sql}
Resultados: """
        
        # 2. Esta parte es un string normal (sin 'f' al inicio)
        # Esto evita errores y no necesitamos escapar las llaves {{ }}
        # También corregí el EJEMPLO para que use comillas dobles (JSON válido).
        prompt_body = """

Eres un asistente de base de datos. Tu tarea es analizar los resultados y decidir la mejor forma de presentarlos.

REGLAS:
1.  Si los resultados son una lista de múltiples ítems (ej: una lista de productos, proveedores, ventas), responde SOLAMENTE con un JSON string.
    El JSON debe tener este formato:
    {"type": "table", "title": "Un título descriptivo para la tabla", "content": [aquí van los datos de 'Resultados']}
    NO añadas NADA antes o después del JSON.

2.  Si los resultados son una respuesta simple (ej: un conteo, un promedio, un solo nombre, o si no hay resultados), responde con texto plano.
    NO uses markdown (sin ** o *).
    Si hay listas, usa saltos de línea y guiones (-).

EJEMPLOS:
-   Pregunta: "¿Cuántos productos hay?" Resultados: [{'count': 5}] -> Respuesta: Hay 5 productos en total.
-   Pregunta: "Lístame los productos" Resultados: [{'nombre': 'A', 'precio': 100}, {'nombre': 'B', 'precio': 200}] -> Respuesta: {"type": "table", "title": "Lista de Productos", "content": [{"nombre": "A", "precio": 100}, {"nombre": "B", "precio": 200}]}
-   Pregunta: "¿Quién es el proveedor 1?" Resultados: [{'nombre': 'Drogas del Norte'}] -> Respuesta: El proveedor 1 es Drogas del Norte.
"""
        
        # 3. Construir el prompt final con concatenación simple
        prompt = prompt_header + results_str + prompt_body
        
        # --- FIN DE LA CORRECCIÓN ---
        
        # Le pasamos el contexto completo para que entienda preguntas de seguimiento
        return self.model.ask(prompt, self.context)
    
    def _add_to_context(self, role: str, content: str):
        """Agrega mensaje al contexto"""
        self.context.append({"role": role, "content": content})
        
        # Mantener solo los últimos N mensajes
        if len(self.context) > self.max_context:
            self.context = self.context[-self.max_context:]
    
    def add_tool(self, name: str, tool: Any):
        """
        Agrega una nueva herramienta al agente
        
        Args:
            name: Nombre de la herramienta
            tool: Instancia de la herramienta
        """
        self.tools[name] = tool
        print(f"✅ Herramienta '{name}' agregada")
    
    def get_context_summary(self) -> Dict:
        """Obtiene resumen del contexto"""
        return {
            "messages": len(self.context),
            "database_type": self.db_type,
            "tools": list(self.tools.keys())
        }
    
    def clear_context(self):
        """Limpia el contexto"""
        self.context = []
        print("🧹 Contexto limpiado")
    
    def close(self):
        """Cierra conexiones"""
        for tool in self.tools.values():
            if hasattr(tool, 'close'):
                tool.close()