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
        Pregunta principal del agente
        
        Args:
            question: Pregunta del usuario
        
        Returns:
            Respuesta del agente
        """
        print(f"\n🤔 Pregunta: {question}")
        
        # 1. Agregar pregunta al contexto
        self._add_to_context("user", question)
        
        # 2. Generar SQL con el modelo
        print("⚙️  Generando consulta SQL...")
        sql = self._generate_sql(question)
        
        if sql == "NO_QUERY":
            response = "No puedo responder esa pregunta con los datos disponibles."
            self._add_to_context("assistant", response)
            return response
        
        print(f"📊 SQL: {sql}")
        
        # 3. Ejecutar en la BD
        results = self.tools["database"].execute(sql)
        
        if results and "error" in results[0]:
            response = f"Error: {results[0]['error']}"
            self._add_to_context("assistant", response)
            return response
        
        print(f"✅ Resultados: {len(results)} filas")
        
        # 4. Generar respuesta natural
        response = self._generate_response(question, sql, results)
        
        # 5. Agregar respuesta al contexto
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
        
        sql = self.model.ask(prompt, self.context[-3:] if len(self.context) > 3 else None)
        
        # Limpiar
        if sql.startswith("```sql"):
            sql = sql.replace("```sql", "").replace("```", "").strip()
        elif sql.startswith("```"):
            sql = sql.replace("```", "").strip()
        
        return sql
    
    def _generate_response(self, question: str, sql: str, results: List[Dict]) -> str:
        """Genera respuesta en lenguaje natural"""
        prompt = f"""El usuario preguntó: {question}

Se ejecutó: {sql}

Resultados: {results}

Genera una respuesta clara y concisa en español.
Si no hay resultados, dilo amablemente.

IMPORTANTE: No uses NUNCA formato markdown (como ** o *).
Responde solo con texto plano.

Cuando presentes listas (como proveedores o productos), 
usa guiones (-) y saltos de línea (nuevas líneas) para ordenar la información.
Por ejemplo:
Aquí tienes los proveedores:
- Proveedor 1
- Proveedor 2
"""
        
        return self.model.ask(prompt, self.context[-3:] if len(self.context) > 3 else None)
    
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