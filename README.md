# Consultorio Agent MVP

MVP web para gestión de turnos médicos con chat escrito y voz desde navegador, potenciado por Groq y LangGraph.

## Requisitos Previos

- Docker y Docker Compose
- Una API Key de Groq (gratuita en [console.groq.com](https://console.groq.com))
- Una App Password de Gmail (si vas a usar el envío de emails con n8n)

## Configuración Inicial

1. **Configuración de Variables de Entorno:**
   Creá tu archivo `.env` copiando el archivo de ejemplo:
   ```powershell
   copy .env.example .env
   ```
   Abrí el archivo `.env` y asegurate de completar tus credenciales (especialmente `GROQ_API_KEY` y las configuraciones de n8n o ElevenLabs si usás voz/correo).

2. **(Opcional) Configuración del Entorno Local para Autocompletado del IDE (.venv):**
   Si querés tener ayuda de tipado y linting en VSCode/Cursor, podés crear el entorno virtual localmente:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   ```

## Levantar el Proyecto

Todo el stack (Base de Datos PostgreSQL + Redis + API FastAPI + Frontend HTML/JS + n8n) se levanta y corre directamente en contenedores de Docker:

```powershell
# Levantar en segundo plano
docker compose up -d
```

El contenedor `api` aplicará las migraciones de base de datos de Alembic y sembrará los usuarios y médicos de prueba de forma idempotente en el arranque.

## Direcciones de Acceso Local

Una vez levantados los contenedores, podés acceder a los servicios en las siguientes direcciones:

*   **Aplicación Web (Chatbot y Portal Médico):** [http://localhost:8000](http://localhost:8000)
*   **Workflow Automation (n8n):** [http://localhost:5678](http://localhost:5678)
*   **Documentación de la API (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)

## ¿Cómo funciona?

1. **Frontend:** Ofrece el Chatbot con IA (REST/WebSockets con Push-To-Talk) para pacientes, y el Portal de gestión de agendas para médicos.
2. **Orquestador (LangGraph):** Decide dinámicamente si usar herramientas como `search_availability`, `hold_slot` o `confirm_appointment` según lo que el usuario pida en lenguaje natural.
3. **Notificaciones (n8n + Outbox):** Al confirmar un turno, el backend registra el correo en la tabla outbox de PostgreSQL. Post-commit, se envía al webhook de n8n, el cual despacha un correo HTML profesional vía Gmail SMTP.

## Despliegue en Producción (CI/CD)

El proyecto está configurado para un despliegue continuo automatizado en **Oracle Cloud Always Free** (instancia Ubuntu 24.04 con Docker):

* **CI/CD**: Cada push a `main` dispara un workflow en GitHub Actions que sincroniza incrementalmente los archivos con el servidor usando `rsync` y reinicia los contenedores.
* **Seguridad**: Las claves de producción no se commitean y residen de forma segura en `/home/ubuntu/app/.env` dentro del servidor.
* **Acceso**: La aplicación es accesible temporalmente por IP en el puerto 8000: `http://146.235.32.199:8000`.
