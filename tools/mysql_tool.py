"""
Herramienta para trabajar con bases de datos MySQL
"""
import mysql.connector
from typing import List, Dict, Any, Optional


class MySQLTool:
    """Herramienta para consultar bases de datos MySQL"""
    
    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str,
        port: int = 3307
    ):
        """
        Inicializa la conexión a MySQL
        
        Args:
            host: Host del servidor MySQL (ej: 'localhost')
            user: Usuario de MySQL
            password: Contraseña
            database: Nombre de la base de datos
            port: Puerto (por defecto 3306)
        """
        self.connection_params = {
            'host': host,
            'user': user,
            'password': password,
            'database': database,
            'port': port
        }
        self.conn = None
        self.cursor = None
        self._connect()
    
    def _connect(self):
        """Establece la conexión con MySQL"""
        try:
            self.conn = mysql.connector.connect(**self.connection_params)
            self.cursor = self.conn.cursor(dictionary=True)
            print(f"✅ Conectado a MySQL: {self.connection_params['database']}")
        except mysql.connector.Error as e:
            print(f"❌ Error al conectar a MySQL: {e}")
            raise
    
    def get_schema(self) -> str:
        """Obtiene el esquema de todas las tablas"""
        try:
            # Obtener todas las tablas
            self.cursor.execute("SHOW TABLES")
            tables = [list(row.values())[0] for row in self.cursor.fetchall()]
            
            schema = "ESQUEMA DE LA BASE DE DATOS MySQL:\n\n"
            
            for table in tables:
                # Información de la tabla
                self.cursor.execute(f"DESCRIBE {table}")
                columns = self.cursor.fetchall()
                
                schema += f"Tabla: {table}\n"
                for col in columns:
                    field = col['Field']
                    col_type = col['Type']
                    null = col['Null']
                    key = col['Key']
                    extra = col['Extra']
                    
                    constraints = []
                    if key == 'PRI':
                        constraints.append('PRIMARY KEY')
                    if null == 'NO':
                        constraints.append('NOT NULL')
                    if extra:
                        constraints.append(extra)
                    
                    constraint_str = f" ({', '.join(constraints)})" if constraints else ""
                    schema += f"  - {field}: {col_type}{constraint_str}\n"
                
                # Contar registros
                self.cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                count = self.cursor.fetchone()['count']
                schema += f"  Total de registros: {count}\n\n"
            
            return schema
        except mysql.connector.Error as e:
            return f"Error al obtener esquema: {e}"
    
    def execute(self, sql: str) -> List[Dict[str, Any]]:
        """
        Ejecuta una consulta SQL y retorna los resultados
        
        Args:
            sql: Consulta SQL a ejecutar
        
        Returns:
            Lista de diccionarios con los resultados
        """
        try:
            # Validar que sea una consulta SELECT
            sql_upper = sql.strip().upper()
            if not sql_upper.startswith('SELECT'):
                return [{"error": "Solo se permiten consultas SELECT"}]
            
            self.cursor.execute(sql)
            results = self.cursor.fetchall()
            
            return results if results else []
            
        except mysql.connector.Error as e:
            return [{"error": str(e)}]
    
    def test_connection(self) -> bool:
        """Prueba la conexión a la base de datos"""
        try:
            self.cursor.execute("SELECT 1")
            return True
        except mysql.connector.Error:
            return False
    
    def close(self):
        """Cierra la conexión"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("🔌 Conexión MySQL cerrada")