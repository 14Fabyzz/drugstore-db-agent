"""
API para el Agente de Base de Datos de la Droguería
Basado en FastAPI
"""
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
import json

# Importar la lógica de tu agente
from agent import MCPAgent
from config import (
    GEMINI_API_KEY, 
    GEMINI_MODEL, 
    MYSQL_CONFIG,
    DATABASE_TYPE
)

# --- Modelos de Datos (Pydantic) ---

# 1. Para hacer preguntas normales
class QuestionRequest(BaseModel):
    question: str

# 2. (NUEVO) Para confirmar una operación de escritura (INSERT/UPDATE)
class ConfirmRequest(BaseModel):
    sql_query: str

# 3. Lo que devolvemos al frontend
class AnswerResponse(BaseModel):
    answer: str

# --- Variable Global para el Agente ---
agente_global = None

# --- Eventos de Inicio y Cierre (Lifespan) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global agente_global
    print("=" * 80)
    print("🤖 Iniciando Agente MCP para la API...")
    print(f"📊 Conectando a: {MYSQL_CONFIG['database']}...")
    try:
        agente_global = MCPAgent(
            api_key=GEMINI_API_KEY,
            model_name=GEMINI_MODEL,
            db_type=DATABASE_TYPE, 
            mysql_config=MYSQL_CONFIG
        )
        print("✅ AGENTE CONECTADO Y LISTO")
        print("=" * 80)
    except Exception as e:
        print(f"❌❌ ERROR CRÍTICO AL INICIAR AGENTE ❌❌")
        print(f"Error: {e}")
        agente_global = None 
    
    yield 
    
    if agente_global:
        print("\n🔌 Cerrando conexión del agente...")
        agente_global.close()
    print("👋 API detenida.")

# --- Creación de la App FastAPI ---
app = FastAPI(
    title="Agente de Droguería API",
    description="API con soporte para consultas y escritura confirmada.",
    version="2.0.0", # Actualizamos versión
    lifespan=lifespan
)

origins = ["*"] # Configura esto mejor para producción

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Endpoints ---

@app.get("/", summary="Endpoint de saludo")
def read_root():
    return {"message": "API del Agente activa. Usa /ask para preguntar o /confirm para ejecutar cambios."}

@app.post("/ask", response_model=AnswerResponse, summary="Hacer una pregunta")
async def ask_agent(request: QuestionRequest):
    """
    Envía una pregunta. Si es un INSERT/UPDATE, el agente devolverá 
    un JSON de confirmación en texto, que el frontend debe interpretar.
    """
    if agente_global is None:
        raise HTTPException(status_code=503, detail="El agente no está disponible.")
    
    try:
        print(f"\n🤔 Pregunta recibida: {request.question}")
        respuesta_agente = agente_global.ask(request.question)
        print(f"🤖 Respuesta enviada (puede ser texto o JSON): {respuesta_agente[:100]}...") 
        return AnswerResponse(answer=respuesta_agente)
    
    except Exception as e:
        print(f"❌ Error en /ask: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- (NUEVO) ENDPOINT DE CONFIRMACIÓN ---
@app.post("/confirm", summary="Ejecutar SQL confirmado por usuario")
async def confirm_action(request: ConfirmRequest):
    """
    Recibe un SQL de escritura (INSERT/UPDATE) que el usuario ya aprobó
    en el frontend y lo ejecuta directamente en la base de datos.
    """
    if agente_global is None:
        raise HTTPException(status_code=503, detail="El agente no está disponible.")

    try:
        sql_to_run = request.sql_query
        print(f"\n⚠️ EJECUTANDO SQL CONFIRMADO: {sql_to_run}")

        # 1. Accedemos directamente a la herramienta de base de datos del agente
        #    Asumimos que la key se llama "database" (como pusimos en agent.py)
        db_tool = agente_global.tools.get("database")
        
        if not db_tool:
             raise HTTPException(status_code=500, detail="Herramienta de base de datos no encontrada.")

        # 2. Llamamos a la función execute_write que creamos en mysql_tool.py
        #    Nota: execute_write devuelve un diccionario, ej: {"success": True, "message": "..."}
        resultado = db_tool.execute_write(sql_to_run)
        
        # 3. Convertimos el diccionario a JSON string para devolverlo
        return {"answer": json.dumps(resultado)}

    except Exception as e:
        print(f"❌ Error en /confirm: {e}")
        raise HTTPException(status_code=500, detail=f"Error ejecutando SQL: {str(e)}")

if __name__ == "__main__":
    print("Iniciando servidor API en http://127.0.0.1:8000")
    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)