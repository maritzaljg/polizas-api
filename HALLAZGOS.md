# Hallazgos — Parte A

**Grupo:** individual · **Integrante:** Maritza Liliana Jiménez Gómez

Este documento reúne los catorce defectos encontrados en el servicio polizas-api-v0 antes
de las correcciones, con la evidencia reproducible de cada uno sobre el commit `v0-semilla`.
La segunda parte interpreta el conteo de consultas SQL de los cuatro endpoints que devuelven
datos relacionados.

Las filas están ordenadas de modo que el comando de H14 —el número de póliza duplicado— se
ejecute al final: ese defecto deja la sesión del servicio inservible, y cualquier petición
posterior responde 500 aunque sea correcta.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | Dos credenciales en texto plano dentro del código fuente | `config.py` define `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` como literales en vez de leerlos del entorno | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `sed -n '4,5p' config.py` | `SECRETO_FIRMA = "aseguradora-santo-tomas-2026-firma-7c1e"`<br>`CLAVE_API_REASEGURO = "rk-polizas-2026-4b9f0a3d"` | La configuración pasa a `BaseSettings` leída de `.env`, con `.env.example` versionado y `.env` ignorado |
| H2 | Ninguna dependencia tiene versión fijada | `requirements.txt` lista los paquetes solo por nombre, así que dos instalaciones pueden traer versiones distintas | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `grep -c "==" requirements.txt` | `0` | Se fija la versión exacta de cada dependencia con `==` |
| H3 | Una única sesión de base de datos compartida por todo el servicio | `database.py` crea la sesión al importar el módulo y la reutiliza en todas las peticiones | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `grep -n "sesion = SessionLocal()" database.py` | `16:sesion = SessionLocal()` | Se reemplaza por `get_db`, un generador con `yield` que abre y cierra la sesión en cada petición |
| H4 | El esquema se crea al arrancar, sin migraciones | `main.py` llama a `Base.metadata.create_all(engine)` en el import, de modo que el esquema no tiene historial de cambios | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `grep -n "create_all" main.py` | `17:Base.metadata.create_all(engine)` | Se retira `create_all` y el esquema pasa a crearse con una revisión de Alembic |
| H5 | No existe la ruta de salud del servicio | `main.py` no declara ningún endpoint `/health` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health` | `404` | Se añade `GET /health`, que responde 200 e indica si la base de datos responde |
| H6 | Crear una póliza responde 200 en vez de 201 | El handler de `POST /polizas` no declara `status_code`, así que FastAPI usa el 200 por defecto | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90001","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}'` | `200` | Se declara `status_code=201` en la creación |
| H7 | La respuesta expone `token_firma`, un campo interno derivado del secreto de firma | Ninguna ruta declara `response_model`, así que se serializa el objeto completo de la base | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| grep -c token_firma` | `1` | Cada ruta declara un `response_model` de salida que no incluye los campos internos |
| H8 | Pedir una póliza inexistente responde 200 con el error en el cuerpo | El handler devuelve un diccionario `{"error": ...}` en lugar de lanzar `HTTPException` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w "\nHTTP:%{http_code}\n" localhost:8000/polizas/999999` | `{"error":"no existe la póliza 999999"}`<br>`HTTP:200` | Se lanza `HTTPException(status_code=404)` y el error viaja en el código de estado |
| H9 | Se acepta declarar un siniestro sobre una póliza que no existe | El handler no comprueba la póliza y SQLite no aplica las claves foráneas, de modo que la fila queda huérfana | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d '{"fecha":"2026-03-01","monto":500,"descripcion":"choque simple","estado":"abierto"}'` | `200` | Se comprueba la póliza y se devuelve 404 si no existe; se activa `PRAGMA foreign_keys` en cada conexión |
| H10 | El nombre del asegurado se guarda nulo | El validador `normalizar_asegurado` calcula el valor normalizado pero no lo devuelve, y en Pydantic v2 el valor final del campo es lo que retorna el validador | M7 · 4. Validadores de campo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90002","asegurado":"  juan  perez  ","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}' \| grep -o '"asegurado":[^,]*'` | `"asegurado":null` | El validador devuelve el valor normalizado con `return` |
| H11 | Se acepta una póliza cuya vigencia termina antes de empezar | Ningún validador compara `fecha_fin` con `fecha_inicio`: cada fecha se valida por separado | M7 · 6. Manejo integral del error 422 | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90003","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-12-31","fecha_fin":"2026-01-01","siniestros":[]}'` | `200` | Se añade un `model_validator` que exige `fecha_fin` posterior a `fecha_inicio` y responde 422 |
| H12 | Un siniestro anidado con monto negativo entra sin validarse | `PolizaEntrada` tipa la lista como `list[dict]`, así que Pydantic no aplica las restricciones de `SiniestroEntrada` | M7 · 5. Modelos anidados y topología jerárquica | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90004","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[{"fecha":"2026-02-01","monto":-500,"descripcion":"monto negativo","estado":"abierto"}]}'` | `200` | La lista se tipa como `list[SiniestroEntrada]` y el monto negativo produce 422 |
| H13 | Actualizar solo la prima borra el tipo de la póliza | El PUT aplica `datos.model_dump()` completo, de modo que los campos no enviados llegan como `None` y sobrescriben lo guardado | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/2 \| grep -o '"tipo":[^,]*'; curl -s -X PUT localhost:8000/polizas/2 -H "Content-Type: application/json" -d '{"prima":999}' \| grep -o '"tipo":[^,]*'` | `"tipo":"hogar"`<br>`"tipo":null` | El PUT usa `model_dump(exclude_unset=True)` y solo toca los campos enviados |
| H14 | Un número de póliza repetido responde 500 y deja el servicio inservible | La restricción `unique` de la base falla y, como la sesión es única y nadie hace `rollback`, queda en estado de error para todas las peticiones siguientes | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-00001","asegurado":"Otro Nombre","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}'; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/polizas` | `500`<br>`500` | Se comprueba el número antes de insertar y se devuelve 409; con sesión por petición, un fallo deja de afectar a las peticiones siguientes |

---

# Parte C — Interpretación de las consultas

## `/polizas`

## `/polizas/{id}`

## `/siniestros`

## `/resumen`
