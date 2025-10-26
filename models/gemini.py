"""
Modelo Gemini simplificado
"""
import google.generativeai as genai
from typing import List, Dict


class GeminiModel:
    """Wrapper simple para Gemini"""
    
    def __init__(self, api_key: str, model_name: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)
    
    def ask(self, prompt: str, context: List[Dict] = None) -> str:
        """
        Pregunta al modelo
        
        Args:
            prompt: La pregunta
            context: Historial opcional [{"role": "user/assistant", "content": "..."}]
        
        Returns:
            La respuesta del modelo
        """
        # Si hay contexto, incluirlo
        if context:
            full_prompt = self._build_with_context(prompt, context)
        else:
            full_prompt = prompt
        
        response = self.model.generate_content(full_prompt)
        return response.text.strip()
    
    def _build_with_context(self, prompt: str, context: List[Dict]) -> str:
        """Construye el prompt con contexto"""
        history = "\n".join([
            f"{'Usuario' if m['role']=='user' else 'Asistente'}: {m['content']}"
            for m in context[-3:]  # Últimos 3 mensajes
        ])
        return f"Conversación previa:\n{history}\n\nPregunta actual:\n{prompt}"