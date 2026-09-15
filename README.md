Sí. El problema principal es que tu bloque de **arquitectura no está cerrado correctamente**: abres un bloque ````text`, pero falta el ` ``` `antes de`---`. Además, en la última tabla tienes saltos de línea y backticks que rompen la sintaxis Markdown.

Te dejo el `README.md` corregido y listo para copiar:

````markdown
# Smart Inspection — Backend API

Backend del sistema web inteligente de inspecciones técnicas vehiculares e industriales. Desarrollado con FastAPI, SQLAlchemy y PostgreSQL, incorpora pipelines de inteligencia artificial local para extracción de texto (OCR con PaddleOCR y Tesseract), transcripción de voz (Whisper), asistencia en redacción de informes técnicos (LLaMA 3 vía Ollama y LangChain), importación de reportes DOCX históricos y medición automatizada de productividad operativa.

---

## Características Principales

- **Gestión de Inspecciones:** Registro integral de fichas técnicas, equipos, asignación de inspectores y control del ciclo de vida (`draft`, `in_review`, `observed`, `finalized`).
- **Campos Estructurados y Reglas de Dominio:** Captura de datos técnicos con validadores de formato para patentes/placas, VIN, números de serie y valores numéricos.
- **Evidencias Multimedia:** Subida clasificada de imágenes y audio a almacenamiento local bajo `/uploads`.
- **Pipeline OCR Dual:** Preprocesamiento de imágenes con Pillow/OpenCV y extracción de texto mediante PaddleOCR y Tesseract, con cálculo de confianza y cruce automático contra campos técnicos.
- **Transcripción de Voz (ASR):** Conversión de audios de campo a texto mediante modelos Whisper para registrar observaciones en tiempo real.
- **Generación de Informes con IA:** Orquestación con LangChain y modelos LLaMA 3 sobre Ollama para consolidar campos, transcripciones y OCR en borradores estructurados.
- **Importación Histórica DOCX:** Módulo de previsualización y procesamiento por lotes de informes antiguos en `.docx` para poblar la base de datos y generar borradores.
- **Exportación Documental:** Descarga de reportes técnicos generados en formatos DOCX y PDF con logotipos y firmas de conformidad.
- **Productividad Operativa y Dashboard:** Medición de tiempos de elaboración (`report_started_at` a `report_finished_at`), evaluación contra meta de 20 minutos y métricas por inspector y estado.
- **Solicitudes de Clientes:** Módulo público para recepción de solicitudes de inspección y conversión directa a inspecciones operativas.
- **Autenticación y Seguridad:** Control de acceso basado en roles (`admin`, `inspector`, `viewer`) mediante tokens JWT.

---

## Arquitectura y Estructura del Proyecto

El backend sigue un diseño modular por capas respetando principios DDD (Domain-Driven Design):

```text
backend/
├── alembic/                         # Migraciones de base de datos
│   └── versions/                    # Scripts versionados de evolución de esquema
├── app/
│   ├── api/
│   │   └── routes/                  # Endpoints REST (FastAPI Routers)
│   │       ├── auth.py
│   │       ├── evidences.py
│   │       ├── health.py
│   │       ├── imports.py
│   │       ├── inspection_enrichment.py
│   │       ├── inspection_fields.py
│   │       ├── inspection_requests.py
│   │       ├── inspections.py
│   │       ├── llm_report.py
│   │       ├── ocr.py
│   │       ├── productivity.py
│   │       ├── report_draft.py
│   │       ├── report_export.py
│   │       ├── report_status.py
│   │       ├── transcription.py
│   │       └── users.py
│   ├── core/                        # Configuración (Pydantic Settings), seguridad y dependencias
│   ├── db/
│   │   ├── base.py                 # Base declarativa de SQLAlchemy
│   │   ├── session.py              # Motor de conexión y SessionLocal
│   │   └── models/                 # Entidades ORM (Inspection, Evidence, User, etc.)
│   ├── domain/                      # Reglas de negocio (placas, VIN, series) y enums
│   ├── integrations/                # Adaptadores de IA (Whisper, Ollama/LangChain, PaddleOCR)
│   ├── schemas/                     # Modelos Pydantic de entrada, salida y validación
│   ├── services/                    # Lógica de negocio y orquestación entre módulos
│   ├── static/                      # Recursos visuales (firmas, membretes y logos)
│   ├── tests/                       # Suite de pruebas unitarias e integración
│   │   ├── integration/             # Pruebas de ciclo E2E y concurrencia
│   │   └── unit/                    # Pruebas unitarias por módulo
│   └── main.py                      # Punto de entrada de la aplicación FastAPI y CORS
├── docs/                            # Documentación arquitectural en PlantUML (TDDR y UML)
├── uploads/                         # Directorio de persistencia física de archivos subidos
├── alembic.ini                      # Configuración del CLI de Alembic
├── docker-compose.yml               # Orquestación de contenedores
└── requirements.txt                 # Dependencias del proyecto
````

---

## Requisitos del Sistema

* **Python:** 3.12 o superior.
* **Base de Datos:** PostgreSQL 15+ (producción/desarrollo local).
* **Motor OCR Complementario:** Tesseract OCR con paquetes de idioma español e inglés (`tesseract-ocr`, `tesseract-ocr-spa`).
* **FFmpeg:** Requerido para procesamiento de audio y transcripción.
* **Ollama:** Requerido para ejecutar localmente los modelos LLaMA 3.

### Librerías del Sistema Operativo (Linux/Debian/Ubuntu)

```bash
sudo apt update && sudo apt install -y \
    tesseract-ocr \
    tesseract-ocr-spa \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    poppler-utils
```

---

## Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/smart-inspection/backend.git
cd backend
```

### 2. Configurar el entorno virtual

#### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Instalar dependencias

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### 4. Variables de entorno

Crea un archivo `.env` en la raíz del backend tomando como referencia la siguiente estructura:

```env
APP_NAME="Smart Inspection API"
APP_ENV=development
DEBUG=true
API_V1_PREFIX=/api/v1

# Conexión a Base de Datos (PostgreSQL)
DATABASE_URL=postgresql+psycopg://usuario:password@localhost:5432/smart_inspection_db

# Seguridad y Autenticación JWT
SECRET_KEY=tu_clave_secreta_super_segura_de_al_menos_32_caracteres
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=480

# Parámetros de OCR e IA
PADDLE_MAX_IMAGE_WIDTH=4000
PADDLE_MAX_IMAGE_HEIGHT=4000

# Configuración del LLM
LLM_PROVIDER=ollama
LLM_MODEL=llama3
LLM_BASE_URL=http://localhost:11434
LLM_TIMEOUT=120
LLM_TEMPERATURE=0.2
```

### 5. Base de datos y migraciones

Asegúrate de que el servicio PostgreSQL esté activo y la base de datos creada. Luego ejecuta las migraciones:

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Verificar el estado actual del esquema
alembic current
```

---

## Ejecución del Servidor

Inicia el servidor ASGI con recarga automática para desarrollo:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Una vez en marcha, la documentación interactiva estará disponible en:

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **Healthcheck:** [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

---

## Pruebas de Software

La suite de pruebas está construida con `pytest` y configurada para ejecutarse sobre una base de datos SQLite en memoria (`sqlite://` con `StaticPool`), garantizando aislamiento sin afectar la base de datos de desarrollo o producción.

```bash
# Ejecutar todas las pruebas (unitarias e integración)
pytest -v

# Ejecutar únicamente pruebas unitarias
pytest app/tests/unit/ -v

# Ejecutar únicamente pruebas de integración
pytest app/tests/integration/ -v

# Generar reporte HTML detallado de ejecución
pytest --html=reports/test_report.html --self-contained-html
```

---

## Módulos Principales del API

Todos los endpoints se encuentran bajo el prefijo `/api/v1`.

| Prefijo                       | Responsabilidad                                                         |
| ----------------------------- | ----------------------------------------------------------------------- |
| `/auth`                       | Inicio de sesión, emisión y renovación de tokens JWT.                   |
| `/users`                      | Administración y consulta de usuarios e inspectores.                    |
| `/inspection-requests`        | Registro público y conversión de solicitudes de clientes.               |
| `/inspections`                | Creación, listado, detalle y gestión de estados de inspecciones.        |
| `/inspections/{id}/fields`    | Gestión de campos técnicos normalizados y su estado de validación.      |
| `/inspections/{id}/evidences` | Carga, consulta y actualización de metadatos de imágenes y audios.      |
| `/ocr`                        | Extracción de texto sobre imágenes y validación contra campos técnicos. |
| `/transcription`              | Procesamiento de notas de voz a texto mediante Whisper.                 |
| `/report-drafts`              | Creación, edición y persistencia de versiones de borrador.              |
| `/llm-report`                 | Generación asistida de informes mediante LLaMA 3 y LangChain.           |
| `/reports`                    | Transiciones de estado del informe técnico y registro de auditoría.     |
| `/report-export`              | Compilación y exportación de archivos `.docx` y `.pdf`.                 |
| `/productivity`               | Medición de tiempos de reporte, cálculo de meta (≤20 min) y KPIs.       |
| `/imports`                    | Previsualización y carga por lotes de informes históricos en DOCX.      |

---

## Documentación de la API

Con el servidor ejecutándose, puedes acceder a la documentación generada automáticamente por FastAPI:

* **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
* **OpenAPI JSON:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
