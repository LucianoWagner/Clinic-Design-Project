# Consultorio Agent MVP

MVP web para gestión de turnos médicos con chat escrito y voz desde navegador, potenciado por Groq y LangGraph.

## Requisitos Previos

- Python 3.12+
- Docker y Docker Compose
- Una API Key de Groq (gratuita en [console.groq.com](https://console.groq.com))

## Configuración del Entorno Local (.venv)

Para no instalar las librerías globalmente, te recomendamos crear un entorno virtual de Python. Esto también habilita que el IDE (VSCode/Cursor) te tome el tipado correcto.

Abrí **PowerShell** en la carpeta del proyecto y ejecutá:

```powershell
# 1. Crear el entorno virtual
python -m venv .venv

# 2. Activar el entorno virtual (PowerShell)
.\.venv\Scripts\Activate.ps1

# 3. Instalar las dependencias
pip install -e ".[dev]"
```

*Nota: Si PowerShell te da un error de "ExecutionPolicy", ejecutá esto como Administrador y volvé a intentar: `Set-ExecutionPolicy Unrestricted -Scope CurrentUser`*

## Configuración de Variables de Entorno

Creá el archivo de configuración a partir del ejemplo:

```powershell
copy .env.example .env
```

Abrí el archivo `.env` y asegurate de tener Groq configurado:

```env
GROQ_API_KEY=tu_api_key_aca
GROQ_MODEL=llama-3.3-70b-versatile
```

## Levantar el Proyecto (Docker)

El proyecto entero (Base de Datos PostgreSQL + API FastAPI + Frontend HTML/JS) se levanta con Docker. LangGraph automáticamente creará sus tablas de memoria en el arranque.

```powershell
docker compose up --build
```

El contenedor `api` aplicará las migraciones y cargará los médicos de prueba y turnos automáticamente antes de iniciar el servidor.

**Para probarlo:**
Abrí tu navegador en `http://localhost:8000`.

## ¿Cómo funciona?

El usuario escribe o habla en lenguaje natural. El modelo (Groq) decide si necesita usar herramientas como `search_availability`, `hold_slot` o `confirm_appointment`. 

El **Orquestador (LangGraph)** intercepta estos pedidos, valida contra la Base de Datos y gestiona el historial de la conversación (memoria) sin mezclarlo con la información estricta de negocio (SQLModel).
