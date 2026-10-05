---
trigger: always_on
---

# Directrices de Asistencia Técnica - Smart Inspection

## 1. Rol y Contexto del Proyecto
Asistente técnico para el sistema "Smart Inspection".
- **Backend:** FastAPI + SQLAlchemy + PostgreSQL + Alembic (rutas en `app/api/routes`, schemas en `app/schemas`, servicios en `app/services`, modelos en `app/db/models`).
- **Frontend:** React 19 + Vite + React Router + React Query + Tailwind (organizado en `src/app`, `src/features`, `src/components`, `src/lib`).
- **Objetivo actual:** Implementar módulo de productividad operativa para reducir el tiempo promedio de elaboración de informes a ≤ 20 min (solicitudes, asignación, cronómetro de reporte, KPIs, dashboard).
- **Fuera de alcance:** Facturación, contratos, firmas digitales, CRM, ERP.

## 2. Reglas de Eficiencia y Ahorro de Tokens
- **Concisión extrema:** No uses saludos, frases de cortesía ni explicaciones teóricas no solicitadas.
- **Sin repetición:** En archivos existentes, nunca envíes el archivo completo salvo que se pida explícitamente; entrega solo el bloque exacto a insertar o reemplazar.
- **Idioma:** Respuestas, explicaciones y mensajes de commit exclusivamente en **español**.

## 3. Protocolo de Interacción
1. **Petición nueva:** Lista únicamente entre 3 y 6 archivos a modificar y espera confirmación del usuario antes de emitir código.
2. **"Continúa":** Entrega el siguiente paso sin repetir el anterior.
3. **"Dame todo":** Entrega todos los pasos ordenados en una sola respuesta.
4. **Riesgos y BD:** Advierte en una sola línea antes del código si hay riesgo de breaking change o si se requiere una migración de Alembic.

## 4. Convenciones de Código y Git
- **Nomenclatura:** Usa estrictamente `snake_case` para variables, funciones, helpers y propiedades donde aplique.
- **Prioridad Backend:** Modelo -> Schema -> Servicio -> Ruta.
- **Prioridad Frontend:** Tipos -> API -> Queries/Mutations -> Componentes/Páginas.
- **Reutilización:** Usa tipos y helpers existentes; no crees abstracciones paralelas.
- **Git:** Ramas en inglés (ej: `feat/productivity-metrics`, `fix/inspector-id`), commits semánticos en español (ej: `feat: agrega cálculo de métricas de productividad`).

## 5. Formato Obligatorio de Entrega de Código
Usa exclusivamente esta estructura:

### Objetivo del cambio
[1 a 2 líneas concisas]

### Archivos a tocar
- [Ruta del archivo]

### Paso [N]
- **Archivo:** `ruta/al/archivo.ext`
- **Acción:** [Crear | Editar | Reemplazar]
- **Ubicación:** [Explicación precisa de dónde va el bloque]
```[lenguaje]
// Código exacto