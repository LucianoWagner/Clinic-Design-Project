# Consultorio Agent MVP

MVP web premium para la gestión de turnos médicos asistido por Inteligencia Artificial. Soporta chat interactivo (REST) y llamadas de voz en tiempo real (WebSockets) desde el navegador, portal para el personal médico, notificaciones de email estructuradas a través de n8n, y validación de asistencia física mediante códigos QR con hand-off móvil.

---

## 🛠️ Stack Tecnológico

*   **Backend:** Python 3.12, FastAPI (Async WebSockets / Event Streaming).
*   **Orquestación de IA:** LangGraph (ReAct agent) y Groq (`llama-3.3-70b-versatile`).
*   **Base de Datos y Caché:** PostgreSQL (con extensión `unaccent` para búsquedas tolerantes a acentos) y Redis (para Rate Limiting de APIs).
*   **Motor de Voz:** ElevenLabs API (TTS) y Web Speech API nativa del navegador (STT).
*   **Notificaciones:** n8n (flujo con SMTP y Gmail App Passwords) utilizando el patrón transactional outbox.
*   **Entorno:** Contenedores Docker coordinados mediante Docker Compose.

---

## 🔑 Credenciales de Prueba (Seed Automático)

Al levantar el proyecto, la base de datos se siembra automáticamente de forma idempotente con los siguientes accesos:

| Rol | Correo Electrónico | Contraseña | Detalle |
|---|---|---|---|
| **Admin** | `admin@consultorio.com` | `admin1234` | Gestión global |
| **Paciente** | `paciente@consultorio.com` | `paciente1234` | Usuario para chatear y reservar |
| **Médico (Cardiología)** | `ana@consultorio.com` | `doctor1234` | Dra. Ana Pérez (MN1001) |
| **Médico (Clínica)** | `juan@consultorio.com` | `doctor1234` | Dr. Juan Gómez (MN1002) |
| **Médico (Dermatología)** | `laura@consultorio.com` | `doctor1234` | Dra. Laura Díaz (MN1003) |
| **Médico (Pediatría)** | `maria@consultorio.com` | `doctor1234` | Dra. María Torres (MN1004) |

---

## 🚀 Configuración y Ejecución Local

### Requisitos Previos
*   Docker y Docker Compose instalados.
*   Una API Key de Groq (gratuita en [console.groq.com](https://console.groq.com)).
*   *(Opcional)* API Key de ElevenLabs para habilitar la síntesis de voz premium.

### Pasos para Iniciar
1.  **Configurar Variables de Entorno:**
    Copia el archivo de ejemplo y edita el archivo `.env`:
    ```powershell
    copy .env.example .env
    ```
    Asegúrate de completar `GROQ_API_KEY`, y si deseas habilitar los correos o voz, configura las variables `EMAIL_ENABLED=true`, `EMAIL_PROVIDER=n8n` y las claves de ElevenLabs.

2.  **Levantar el Entorno con Docker Compose:**
    ```powershell
    docker compose up -d --build
    ```
    Este comando levantará todos los servicios (API, PostgreSQL, Redis y n8n) y aplicará automáticamente las migraciones de Alembic junto con el sembrado de datos iniciales.

3.  **Forzar Reset de la Base de Datos:**
    Si deseas limpiar completamente la base de datos y volver a sembrarla de cero:
    ```powershell
    docker compose exec api env PYTHONPATH=/app python /app/app/seed.py --force
    ```

---

## 📁 Direcciones de Acceso y Puertos

*   **Aplicación Web (Portal de Pacientes/Médicos):** [http://localhost:8000](http://localhost:8000)
*   **Documentación Interactiva de la API (Swagger):** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Workflow Automation (n8n):** [http://localhost:5678](http://localhost:5678) (Escucha localmente por defecto).

---

## 🧠 Detalles Clave de la Arquitectura

### 1. Gestión de Memoria Separada (Dual Memory)
El sistema divide la memoria en dos capas en PostgreSQL:
*   **Memoria de Negocio (`interaction_sessions`):** Guarda el estado real estructurado (ID de usuario, ID de slot temporal reservado y estado de la cita).
*   **Memoria Conversacional de IA (`checkpoints`):** Manejada automáticamente por el `AsyncPostgresSaver` de LangGraph. Guarda el historial completo de mensajes y ejecuciones de herramientas utilizando el ID de sesión como `thread_id`.

### 2. Historial de Chat y Auditoría Separados
*   **`conversation_messages`:** Es la única tabla que lee el frontend para renderizar el chat de forma instantánea.
*   **`interaction_logs`:** Registro técnico detallado de todas las iteraciones y ejecuciones internas del agente. Si el LLM genera respuestas no deseadas (como código JSON interno), el componente `response_sanitizer` las limpia en el backend, dejando una marca de sanitización en el log de auditoría y enviando la respuesta limpia al frontend.

### 3. Canal de Voz Optimizado (Doble Capa)
Para evitar que el bot fatigue al usuario leyendo en voz alta listas largas de horarios disponibles:
1.  **Vía Chat:** Se renderiza todo el texto detallado en formato markdown.
2.  **Vía WebSocket (Voz):** El WebSocket filtra el texto de salida (`extract_spoken_text`), omitiendo tablas o listas y reproduciendo mediante ElevenLabs únicamente una introducción conversacional corta (máximo 2 oraciones).

### 4. Transacciones e Integración con n8n (Patrón Outbox)
Para garantizar la resiliencia en el envío de correos:
*   Al confirmar un turno, el backend guarda un registro en la tabla `email_outbox` dentro de la misma transacción de SQLModel.
*   Una vez que el commit en la base de datos es exitoso, se despacha asíncronamente el payload JSON estructurado al webhook local de n8n para enviar el correo HTML vía SMTP, evitando que fallos de red bloqueen la reserva del turno.

### 5. Check-in con Escáner Móvil (Mobile Hand-off & Fallback)
El portal médico de escritorio permite verificar la asistencia mediante un código QR:
*   Genera un QR de vinculación móvil seguro con tokens JWT temporales.
*   El médico lo escanea desde su celular y abre una aplicación web responsiva (`mobile-scanner.html`).
*   **Fallback Insecure Context:** Si el navegador del celular bloquea el acceso a la cámara debido a la falta de certificado HTTPS local (puerto HTTP), se habilita un botón que permite al médico tomar una fotografía nativa del QR del paciente. El backend procesa esta imagen, decodifica el token QR de forma robusta con la librería **`zxing-cpp`**, y finaliza el turno en tiempo real.
