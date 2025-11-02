# FarmaChat - Asistente de IA para Droguería

Un asistente de IA que te permite "hablar" con tu base de datos MySQL en lenguaje natural. Convierte preguntas como "¿Cuál fue el total de ventas de ayer?" en consultas SQL, obtiene los datos y te los presenta en un dashboard interactivo.

![FarmaChat Dashboard]<img width="1887" height="896" alt="image" src="https://github.com/user-attachments/assets/b5ffd395-bc21-4f4c-83ba-afa31d1ee90c" />


---

## 🚀 Sobre el Proyecto

Este proyecto es un "dashboard de análisis" inteligente. Consiste en:

* **Un Backend de IA (Python/FastAPI):** Un agente que utiliza la API de Gemini para entender el lenguaje natural y generar consultas SQL.
* **Un Frontend de Dashboard (HTML/JS):** Una interfaz de usuario web con un panel de chat a la izquierda y un gran panel de visualización a la derecha, donde se renderizan tablas y gráficos.

El agente no solo responde preguntas simples, sino que también entiende el contexto, se auto-corrige de errores y decide de forma inteligente la mejor manera de presentar la información (texto, tabla o gráfico).

## ✨ Características Principales

* **Traducción de Lenguaje Natural a SQL:** El corazón del agente. Entiende el esquema de la base de datos `drogueria4` para generar consultas `SELECT` complejas.
* **Layout de Dashboard:** Interfaz limpia con un panel de chat (`.chat-panel`) y un panel de visualización (`.results-panel`) para una experiencia de análisis profesional.
* **🧠 Memoria Conversacional:** El agente recuerda el historial de la conversación para entender preguntas de seguimiento (ej: "Lístalos" después de preguntar por productos).
* **🔄 Auto-Corrección de SQL:** Si el agente genera un SQL que falla, analiza el error de MySQL y lo reintenta con una consulta corregida.
* **📊 Respuestas Enriquecidas (Multimodales):**
    * **Gráficos:** Genera gráficos de barras o de líneas (usando Chart.js) para preguntas de "análisis" o "reportes".
    * **Tablas:** Muestra tablas HTML bien formateadas para preguntas de "lista".
    * **Texto:** Proporciona respuestas de texto simples para conteos, promedios o datos únicos.
* **Manejo de Tipos de Datos:** Soluciona errores de serialización `JSON` para tipos de datos complejos de MySQL como `Decimal` y `date`.

---

## 🛠️ Tecnologías Utilizadas

* **Backend:**
    * Python 3.10+
    * FastAPI (para el servidor API)
    * Uvicorn (para correr el servidor)
    * Google Generative AI (`google-generativeai` para Gemini)
    * MySQL Connector (`mysql-connector-python`)
* **Frontend:**
    * HTML5
    * CSS3 (Moderno, con variables y layout Flexbox)
    * JavaScript (Vanilla JS, Fetch API)
* **Visualización:**
    * Chart.js

---

## 📖 Cómo Funciona

El flujo de una pregunta es el siguiente:

1.  **Usuario:** Escribe una pregunta en el chat (`index.html`).
2.  **Frontend (JS):** Envía la pregunta al *endpoint* `/ask` del servidor FastAPI.
3.  **Backend (API):** Recibe la solicitud y llama a `agent.ask(pregunta)`.
4.  **Agente (Paso 1: SQL):** El agente usa Gemini y el esquema de la BD para generar una consulta SQL.
5.  **Agente (Paso 2: Ejecución):** El `MySQLTool` ejecuta la consulta en la BD `drogueria5`.
    * *(Si falla, el Agente entra en modo de auto-corrección y repite el paso 4 y 5).*
6.  **Agente (Paso 3: Respuesta):** El agente analiza la pregunta y los resultados (la data) para decidir el formato (texto, tabla o gráfico).
7.  **Backend (API):** Devuelve la respuesta final (texto plano o un JSON de visualización) al frontend.
8.  **Frontend (JS):** Recibe la respuesta:
    * Si es texto, lo muestra en el chat.
    * Si es JSON (`{"type": "table"}` o `{"type": "chart"}`), renderiza la tabla o el gráfico en el `.results-panel`.

---

## 📦 Instalación y Ejecución

Sigue estos pasos para ejecutar el proyecto en tu máquina local.

### Prerrequisitos
* Python 3.10+
* Un servidor MySQL corriendo (ej: XAMPP, WAMP, Docker) con tu base de datos `drogueria4` creada.
