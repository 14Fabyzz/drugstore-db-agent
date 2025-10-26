El proyecto incluye:
- Backend: API con FastAPI (api.py) que gestiona la conexión del agente y usa 'lifespan' para una única instancia.
- Frontend: Interfaz de chat en index.html (HTML/CSS/JS) que consume la API.
- Agente: Lógica central (agent.py) que usa Gemini para traducir lenguaje natural a SQL.
- Herramientas: Conector de MySQL (mysql_tool.py) y wrapper de Gemini (gemini.py).
- Configuración: Manejo de API Key y credenciales de BD (config.py).

Funcionalidades clave:
- Traducción de lenguaje natural a consultas SQL.
- Conexión a base de datos real de MySQL (drogueria4).
- Solución de CORS para la comunicación API-Frontend.
- Formato de respuesta limpio (texto plano con saltos de línea)."
