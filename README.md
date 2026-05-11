# Smart Inspection Backend

Backend del sistema web inteligente para la generación automatizada de informes de inspección.

Este proyecto implementa la API y la lógica principal para registrar inspecciones, capturar datos estructurados, adjuntar evidencias, ejecutar OCR, transcribir observaciones, generar borradores de informe, exportar documentos y dar seguimiento al estado del informe.

---

## Objetivo

Construir la base backend de un sistema web capaz de apoyar el proceso de inspección técnica mediante:

- registro estructurado de inspecciones
- almacenamiento de campos críticos
- carga de evidencias visuales
- extracción de texto con OCR
- transcripción de audio
- generación automática de borradores de informe
- exportación documental
- trazabilidad y seguimiento de estados

---

## Alcance actual

Actualmente el backend contempla módulos para:

- healthcheck y configuración base
- inspecciones
- campos de inspección
- evidencias
- OCR por evidencia
- transcripciones
- borradores de informe
- generación automática de informe
- exportación
- estados y trazabilidad

---

## Stack tecnológico

- Python 3.12
- FastAPI
- SQLAlchemy
- PostgreSQL
- Pydantic
- Tesseract OCR vía `pytesseract`
- Pillow para preprocesamiento básico de imágenes
- Uvicorn como servidor ASGI

---

## Estructura general

```text
app/
├── api/
│   └── routes/
│       ├── health.py
│       ├── inspections.py
│       ├── inspection_fields.py
│       ├── evidences.py
│       ├── ocr.py
│       ├── transcription.py
│       ├── report_draft.py
│       ├── llm_report.py
│       ├── report_export.py
│       └── report_status.py
├── core/
│   └── config.py
├── db/
│   ├── base.py
│   ├── session.py
│   └── models/
├── schemas/
├── services/
│   ├── evidence_service.py
│   ├── evidence_ocr_service.py
│   ├── storage_service.py
│   └── report_template_service.py
└── main.py

uploads/
└── inspections/
```

---

## Funcionalidades principales

### 1. Inspecciones
Permite registrar inspecciones con datos base como código, cliente, equipo, tipo de inspección, fecha, ubicación y responsable.

### 2. Captura estructurada
Permite asociar campos de inspección y valores críticos al registro, para alimentar validaciones y generación de informes.

### 3. Evidencias
Permite subir imágenes asociadas a una inspección usando `multipart/form-data`, almacenarlas físicamente y listarlas posteriormente.

### 4. OCR
Permite procesar una evidencia específica para extraer texto, guardar confianza estimada y registrar si ya fue procesada.

### 5. Transcripción
Permite asociar observaciones de audio transcritas al flujo de inspección.

### 6. Informe automático
Permite construir el contexto de informe a partir de:
- datos estructurados
- evidencias
- resultados OCR
- transcripciones
- borrador generado o editado

### 7. Exportación
Permite generar salida documental del informe final.

### 8. Estados y trazabilidad
Permite gestionar el estado del informe y preparar trazabilidad de acciones relevantes.

---

## Requisitos previos

Antes de ejecutar el proyecto debes tener instalado:

- Python 3.12 o superior
- PostgreSQL
- Tesseract OCR instalado en el sistema operativo
- Git

### Verificar Tesseract

```bash
tesseract --version
```

Si el comando no responde, instala Tesseract y agrégalo al PATH del sistema.

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/smart-inspection/backend.git
cd backend
```

### 2. Crear y activar entorno virtual

#### Windows PowerShell
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

#### Linux / macOS
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto.

Ejemplo:

```env
APP_NAME=Smart Inspection Backend
APP_ENV=development
DEBUG=true
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+psycopg://postgres:admin@localhost:5432/postgres
```

> Ajusta el valor de `DATABASE_URL` según tu entorno local.

### 5. Ejecutar el servidor

```bash
python run.py
```

O con Uvicorn directamente:

```bash
uvicorn app.main:app --reload
```

---

## Archivos subidos

Las evidencias se almacenan localmente en:

```text
uploads/inspections/{inspection_id}/
```

Y se exponen mediante:

```text
/uploads/...
```

Ejemplo de URL devuelta por la API:

```text
/uploads/inspections/1/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.png
```

---

## Endpoints principales

## Health
- `GET /`
- `GET /health`

## Inspecciones
- `POST /api/v1/inspections`
- `GET /api/v1/inspections`
- `GET /api/v1/inspections/{inspection_id}`

## Campos de inspección
- endpoints para registrar y consultar campos asociados a la inspección

## Evidencias
- `POST /api/v1/inspections/{inspection_id}/evidences`
- `GET /api/v1/inspections/{inspection_id}/evidences`

## OCR
- `POST /api/v1/evidences/{evidence_id}/ocr`

## Transcripción
- rutas de carga, procesamiento y edición de transcripciones

## Informe
- rutas para crear borrador
- rutas para generar informe automático
- rutas para editar y exportar informe

## Estado y trazabilidad
- rutas para consultar y actualizar estado del informe
- rutas para historial y trazabilidad

---

## Prueba rápida del flujo de evidencias

### 1. Subir imagen

Desde Swagger o desde frontend, enviar un `multipart/form-data` a:

```http
POST /api/v1/inspections/{inspection_id}/evidences
```

Campos esperados:

- `file`
- `evidence_category`
- `caption`

### 2. Listar evidencias

```http
GET /api/v1/inspections/{inspection_id}/evidences
```

### 3. Procesar OCR de una evidencia

```http
POST /api/v1/evidences/{evidence_id}/ocr
```

---

## Ejemplo de respuesta de evidencia

```json
{
  "id": 1,
  "inspection_id": 1,
  "file_path": "uploads/inspections/1/abc123.png",
  "file_url": "/uploads/inspections/1/abc123.png",
  "file_type": "image/png",
  "evidence_category": "placa",
  "caption": "Foto de placa",
  "ocr_extracted_text": null,
  "ocr_confidence": null,
  "ocr_processed": false,
  "ocr_last_processed_at": null,
  "uploaded_at": "2026-05-10T19:00:00Z"
}
```

---

## Documentación interactiva

Una vez levantado el backend, puedes usar:

- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Notas técnicas

- El proyecto usa `StaticFiles` para exponer el directorio `uploads`.
- El OCR está desacoplado del upload de evidencias.
- La evidencia se registra primero y luego puede procesarse por OCR.
- El generador de contexto del informe usa evidencias, OCR y transcripciones como insumos del documento final.
- El sistema está preparado para crecimiento incremental del frontend y del pipeline de IA.

---

## Estado del proyecto

Backend en desarrollo activo, orientado a cubrir el MVP funcional del sistema de inspección inteligente y servir como base para la integración del frontend web.

---

## Próximos pasos

- inicializar repositorio frontend
- construir flujo visual de inspecciones
- crear módulo de carga y previsualización de evidencias
- mostrar resultados OCR en interfaz
- integrar transcripción y generación de informe
- mejorar trazabilidad y dashboard

---

## Equipo

Proyecto académico/técnico orientado a la automatización del proceso de inspección y generación de informes mediante captura estructurada, OCR, transcripción y asistencia de IA.