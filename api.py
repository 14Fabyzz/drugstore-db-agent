"""
API para el Agente de Base de Datos de la Droguería
Basado en FastAPI
"""
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

# Importar la lógica de tu agente
from agent import MCPAgent
from config import (
    GEMINI_API_KEY, 
    GEMINI_MODEL, 
    MYSQL_CONFIG,
    DATABASE_TYPE
)

# --- Modelos de Datos (Pydantic) ---
# Esto define qué JSON debe enviarte el cliente
class QuestionRequest(BaseModel):
    question: str

# Esto define qué JSON les vas a devolver
class AnswerResponse(BaseModel):
    answer: str

# --- Variable Global para el Agente ---
# Aquí guardaremos la instancia de tu agente para no tener que
# crearla con cada pregunta (lo cual sería lento).
agente_global = None

# --- Eventos de Inicio y Cierre (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Código que se ejecuta AL INICIAR la API ---
    global agente_global
    print("=" * 80)
    print("🤖 Iniciando Agente MCP para la API...")
    print(f"📊 Conectando a: {MYSQL_CONFIG['database']}...")
    try:
        agente_global = MCPAgent(
            api_key=GEMINI_API_KEY,
            model_name=GEMINI_MODEL,
            db_type=DATABASE_TYPE, # Usará 'mysql' de tu config
            mysql_config=MYSQL_CONFIG
        )
        print("✅ AGENTE CONECTADO Y LISTO")
        print("=" * 80)
    except Exception as e:
        print(f"❌❌ ERROR CRÍTICO AL INICIAR AGENTE ❌❌")
        print(f"Error: {e}")
        agente_global = None # El agente falló al iniciar
    
    yield # Aquí es donde la API vive y recibe peticiones
    
    # --- Código que se ejecuta AL CERRAR la API ---
    if agente_global:
        print("\n🔌 Cerrando conexión del agente...")
        agente_global.close()
    print("👋 API detenida.")

# --- Creación de la App FastAPI ---
app = FastAPI(
    title="Agente de Droguería API",
    description="Una API para hacer preguntas en lenguaje natural a la base de datos 'drogueria4'.",
    version="1.0.0",
    lifespan=lifespan # Gestiona el inicio y cierre
)

origins = [
    "*", # Permite todas las fuentes (para pruebas)
    # En producción, deberías ser más específico:
    # "http://localhost",
    # "http://127.0.0.1",
    # "null" # Permite solicitudes de 'file://' (abrir el HTML localmente)
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos los métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos los encabezados
)

# --- Definición de Endpoints (las "URLs" de tu API) ---

@app.get("/", summary="Endpoint de saludo")
def read_root():
    """
    Un endpoint simple para verificar que la API está funcionando.
    """
    return {"message": "¡Bienvenido a la API del Agente de Droguería! Usa el endpoint /ask."}

@app.post("/ask", response_model=AnswerResponse, summary="Hacer una pregunta al agente")
async def ask_agent(request: QuestionRequest):
    """
    Envía una pregunta en lenguaje natural al agente.
    
    - **Request body (JSON)**: `{"question": "Tu pregunta aquí"}`
    - **Response body (JSON)**: `{"answer": "La respuesta del agente"}`
    """
    if agente_global is None:
        # Esto pasa si el agente falló al iniciar (ej: mala contraseña de BD)
        raise HTTPException(status_code=503, detail="Servicio no disponible: El agente no pudo inicializarse.")
    
    try:
        print(f"\n🤔 Pregunta recibida por API: {request.question}")
        
        # ¡Aquí ocurre la magia!
        # Llamamos al método .ask() de la instancia de tu agente
        respuesta_agente = agente_global.ask(request.question)
        
        print(f"🤖 Respuesta generada: {respuesta_agente}")
        
        # Devolvemos la respuesta en el formato JSON definido
        return AnswerResponse(answer=respuesta_agente)
    
    except Exception as e:
        print(f"❌ Error durante la ejecución de /ask: {e}")
        # Si algo sale mal, envía un error 500
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {e}")

# --- Ejecución de la API ---
if __name__ == "__main__":
    # Esto te permite ejecutar la API con: python api.py
    # --reload hace que el servidor se reinicie solo cada vez que guardas cambios
    print("Iniciando servidor API en http://127.0.0.1:8000")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)