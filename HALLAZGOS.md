# Hallazgos — Parte A

**Grupo:** individual · **Integrante:** Maritza Liliana Jiménez Gómez

Este documento reúne los **34 defectos** encontrados en el servicio polizas-api-v0
antes de las correcciones. Cada fila declara el comando que reproduce el defecto y la
salida literal obtenida al ejecutarlo sobre el commit `v0-semilla`, en una copia del
repositorio parada en ese commit y con la base de datos original intacta. Las 34
salidas se volvieron a comprobar una por una, en el orden del documento, antes de entregar.

Los hallazgos están agrupados por el tipo de problema. Dentro de cada grupo, las filas
se ordenan dejando de último el comando de H14 —el número de póliza duplicado—, porque
ese defecto deja la sesión compartida inservible y cualquier petición posterior responde
500 aunque sea correcta: ejecutarlo antes contaminaría la evidencia de los demás.

> **Sobre el número de hallazgos.** El enunciado publicado pedía entre 8 y 14, y
> `verificar_entrega.py` comprueba ese rango, de modo que marcará esta tabla como fuera
> de rango. Se documentan los 34 porque el docente autorizó después documentarlos todos
> y porque el nivel máximo del criterio C3 se describe como «todos los defectos
> hallados». Ninguna fila se incluyó sin un comando que la reproduzca, y se
> descartaron nueve candidatos que no superaban ese criterio.

**Índice**

1. **Configuración, secretos y reproducibilidad** — 5 hallazgos: H1, H2, H15, H16, H17
2. **Persistencia e inyección de dependencias** — 5 hallazgos: H3, H4, H18, H19, H20
3. **Validación de la entrada** — 6 hallazgos: H10, H11, H12, H32, H33, H34
4. **Contrato HTTP** — 9 hallazgos: H5, H6, H7, H8, H9, H13, H21, H22, H14
5. **Pruebas** — 2 hallazgos: H23, H24
6. **Contenedor y documentación de despliegue** — 7 hallazgos: H25, H26, H27, H28, H29, H30, H31

---

## 1 · Configuración, secretos y reproducibilidad

Lo que impide que otra persona levante el servicio igual, o que expone lo que no debe.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H1 | Dos credenciales en texto plano dentro del código fuente | `config.py` define `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` como literales en vez de leerlos del entorno | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `sed -n '4,5p' config.py` | `SECRETO_FIRMA = "aseguradora-santo-tomas-2026-firma-7c1e"`<br>`CLAVE_API_REASEGURO = "rk-polizas-2026-4b9f0a3d"` | La configuración pasa a `BaseSettings` leída de `.env`, con `.env.example` versionado y `.env` ignorado |
| H2 | Ninguna dependencia tiene versión fijada | `requirements.txt` lista los paquetes solo por nombre, así que dos instalaciones pueden traer versiones distintas | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `grep -c "==" requirements.txt` | `0` | Se fija la versión exacta de cada dependencia con `==` |
| H15 | La base de datos de la aplicación viaja dentro del repositorio | `app.db` está en el control de versiones, de modo que cada clon arrastra los datos de otro y el estado de partida deja de ser reproducible | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `git ls-files \| grep -c "\.db$"` | `1` | Sale del índice con `git rm --cached app.db`, `.gitignore` pasa a cubrir `*.db` y el esquema lo crea la migración |
| H16 | No existe la plantilla de configuración | Sin `.env.example` no hay forma de saber qué variables necesita el servicio ni con qué valores arranca | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `git ls-files \| grep -c env.example` | `0` | Se versiona `.env.example` con valores con los que el servicio arranca, y `.env` queda ignorado |
| H17 | El servicio ignora la variable de entorno que indica dónde está la base | `config.py` asigna `DATABASE_URL` como literal, así que apuntar el servicio a otra base exige editar el código | M8 · 3. De lo duro a lo flexible: variables de entorno | `v0-semilla` | `DATABASE_URL="sqlite:///otra.db" python -c "import config; print(config.DATABASE_URL)"` | `sqlite:///app.db` | La configuración pasa a `BaseSettings`, que lee la variable del entorno |

## 2 · Persistencia e inyección de dependencias

Cómo se abre la conexión a la base, cómo se crea el esquema y qué garantías da.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H3 | Una única sesión de base de datos compartida por todo el servicio | `database.py` crea la sesión al importar el módulo y la reutiliza en todas las peticiones | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `grep -n "sesion = SessionLocal()" database.py` | `16:sesion = SessionLocal()` | Se reemplaza por `get_db`, un generador con `yield` que abre y cierra la sesión en cada petición |
| H4 | El esquema se crea al arrancar, sin migraciones | `main.py` llama a `Base.metadata.create_all(engine)` en el import, de modo que el esquema no tiene historial de cambios | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `grep -n "create_all" main.py` | `17:Base.metadata.create_all(engine)` | Se retira `create_all` y el esquema pasa a crearse con una revisión de Alembic |
| H18 | Ninguna ruta recibe la sesión de base de datos como dependencia | Los handlers usan directamente la sesión de módulo en vez de declararla con `Depends`, de modo que no se puede sustituir ni en pruebas ni en despliegue | M8 · 4. Inyección de dependencias con Depends | `v0-semilla` | `grep -c "Depends" main.py` | `0` | Cada ruta que toca la base recibe `db: Session = Depends(get_db)` |
| H19 | El repositorio no contiene ninguna migración | No existe `alembic/`, así que no hay forma registrada de crear el esquema ni de hacerlo evolucionar | M9 · 6. Modelado de BD y migraciones con Alembic | `v0-semilla` | `git ls-files \| grep -c "^alembic"` | `0` | Se añade `alembic/` con una revisión que crea las tres tablas |
| H20 | El motor no activa las claves foráneas | SQLite las ignora salvo que se pidan en cada conexión, y `database.py` no lo hace: la base acepta filas que apuntan a pólizas inexistentes | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `grep -c "foreign_keys" database.py` | `0` | Un listener del motor ejecuta `PRAGMA foreign_keys=ON` en cada conexión |

## 3 · Validación de la entrada

Lo que el servicio acepta y no debería aceptar.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H10 | El nombre del asegurado se guarda nulo | El validador `normalizar_asegurado` calcula el valor normalizado pero no lo devuelve, y en Pydantic v2 el valor final del campo es lo que retorna el validador; las 12 pólizas que vienen en `app.db` tienen el asegurado nulo por este motivo | M7 · 4. Validadores de campo y de modelo | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90002","asegurado":"  juan  perez  ","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}' \| grep -o '"asegurado":[^,]*'` | `"asegurado":null` | El validador devuelve el valor normalizado con `return` |
| H11 | Se acepta una póliza cuya vigencia termina antes de empezar | Ningún validador compara `fecha_fin` con `fecha_inicio`: cada fecha se valida por separado | M7 · 6. Manejo integral del error 422 | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90003","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-12-31","fecha_fin":"2026-01-01","siniestros":[]}'` | `200` | Se añade un `model_validator` que exige `fecha_fin` posterior a `fecha_inicio` y responde 422 |
| H12 | Un siniestro anidado con monto negativo entra sin validarse | `PolizaEntrada` tipa la lista como `list[dict]`, así que Pydantic no aplica las restricciones de `SiniestroEntrada` | M7 · 5. Modelos anidados | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90004","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[{"fecha":"2026-02-01","monto":-500,"descripcion":"monto negativo","estado":"abierto"}]}'` | `200` | La lista se tipa como `list[SiniestroEntrada]` y el monto negativo produce 422 |
| H32 | El tipo de póliza admite cualquier texto | El campo se declara como texto libre con un límite de longitud: la descripción del propio esquema dice «auto, hogar o vida», pero nada restringe los valores, así que entran categorías que ningún informe de cartera reconoce | M7 · 3. Tipos complejos y anotaciones | `v0-semilla` | `curl -s -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-70002","asegurado":"Ana Perez","tipo":"motocicleta","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}' \| grep -o '"tipo":"[^"]*"'` | `"tipo":"motocicleta"` | El campo se tipa como `Literal["auto", "hogar", "vida"]`, de modo que cualquier otro valor produce 422. Esos tres niveles son los únicos que aparecen en el material del taller —descripción del esquema, las 12 pólizas de `app.db`, `sembrar_datos.py` y `tests/test_contrato.py`— y la columna se declara `String(10)`, que no admitiría una palabra más larga. Con el campo cerrado, las 12 pruebas del contrato siguen en verde |
| H33 | El estado del siniestro admite cualquier texto | Mismo problema en el esquema del siniestro: el estado por defecto es «abierto» y el dominio contempla además «pagado» y «rechazado», pero se acepta cualquier palabra y el siniestro deja de aparecer en los informes que filtran por estado | M7 · 3. Tipos complejos y anotaciones | `v0-semilla` | `curl -s -X POST localhost:8000/polizas/1/siniestros -H "Content-Type: application/json" -d '{"fecha":"2026-03-01","monto":500,"descripcion":"Choque leve","estado":"anulado"}' \| grep -o '"estado":"[^"]*"'` | `"estado":"anulado"` | El estado se tipa como `Literal["abierto", "pagado", "rechazado"]`. Mismos tres niveles en `app.db`, en `sembrar_datos.py` y en la columna `String(10)` |
| H34 | El número de póliza no respeta el formato que el propio código documenta | `esquemas.py` describe el campo como «Formato POL-AAAA-NNNNN» pero solo comprueba la longitud, de modo que un número que no identifica nada entra igual y queda como referencia del contrato | M7 · 4. Validadores de campo y de modelo | `v0-semilla` | `grep -n "Formato POL" esquemas.py; curl -s -o /dev/null -w "HTTP %{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"12345678","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}'` | `16:    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")`<br>`HTTP 200` | Se retira la promesa en vez de exigirla. Imponer el patrón `^POL-\d{4}-\d{5}$` hace fallar 5 de las 12 pruebas de `tests/test_contrato.py` —archivo que el enunciado prohíbe modificar— porque esa batería crea pólizas como `POL-CT-003056`; además `test_numero_duplicado_da_409_y_el_servicio_sigue_vivo` pasa a recibir 422 donde el contrato exige 409. La descripción pasa a declarar lo que el campo sí comprueba: «entre 8 y 20 caracteres» |

**Criterio aplicado en H32, H33 y H34.** Los tres son el mismo defecto: el esquema publica en
`/docs` una restricción que el código no aplica. Igualar documentación y comportamiento admite dos
caminos, y la medición decide cuál. En H32 y H33 la restricción se puede exigir sin romper nada
—con el conjunto cerrado puesto, las 12 pruebas de `tests/test_contrato.py` siguen en verde—, así
que se exige. En H34 no se puede: el patrón hace fallar 5 de esas 12, porque la batería del propio
taller crea pólizas como `POL-CT-003056`. Ahí el arreglo es el inverso, retirar la promesa y
documentar solo lo que el campo sí comprueba. En los tres casos el resultado es el mismo: el
servicio deja de documentar reglas que no cumple.

## 4 · Contrato HTTP

Qué código de estado devuelve cada ruta y qué publica en la respuesta. El comando de H14 va de último a propósito: deja la sesión compartida inservible.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H5 | No existe la ruta de salud del servicio | `main.py` no declara ningún endpoint `/health` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/health` | `404` | Se añade `GET /health`, que responde 200 e indica si la base de datos responde |
| H6 | Crear una póliza responde 200 en vez de 201 | El handler de `POST /polizas` no declara `status_code`, así que FastAPI usa el 200 por defecto | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-90001","asegurado":"Ana Perez","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}'` | `200` | Se declara `status_code=201` en la creación |
| H7 | La respuesta expone `token_firma`, un campo interno derivado del secreto de firma | Ninguna ruta declara `response_model`, así que se serializa el objeto completo de la base | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/1 \| grep -c token_firma` | `1` | Cada ruta declara un `response_model` de salida que no incluye los campos internos |
| H8 | Pedir una póliza inexistente responde 200 con el error en el cuerpo | El handler devuelve un diccionario `{"error": ...}` en lugar de lanzar `HTTPException` | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w "\nHTTP:%{http_code}\n" localhost:8000/polizas/999999` | `{"error":"no existe la póliza 999999"}`<br>`HTTP:200` | Se lanza `HTTPException(status_code=404)` y el error viaja en el código de estado |
| H9 | Se acepta declarar un siniestro sobre una póliza que no existe | El handler inserta el siniestro sin comprobar que la póliza exista, de modo que la fila queda huérfana | M9 · 7. SQLite local e integración con FastAPI | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas/999999/siniestros -H "Content-Type: application/json" -d '{"fecha":"2026-03-01","monto":500,"descripcion":"choque simple","estado":"abierto"}'` | `200` | Se comprueba la póliza y se devuelve 404 si no existe |
| H13 | Actualizar solo la prima borra el tipo de la póliza | El PUT aplica `datos.model_dump()` completo, de modo que los campos no enviados llegan como `None` y sobrescriben lo guardado | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s localhost:8000/polizas/2 \| grep -o '"tipo":[^,]*'; curl -s -X PUT localhost:8000/polizas/2 -H "Content-Type: application/json" -d '{"prima":999}' \| grep -o '"tipo":[^,]*'` | `"tipo":"hogar"`<br>`"tipo":null` | El PUT usa `model_dump(exclude_unset=True)` y solo toca los campos enviados |
| H21 | Puntuar una póliza inexistente responde 200 | El handler de `/score` devuelve un diccionario de error en lugar de lanzar `HTTPException`, el mismo patrón de H8 en otra ruta | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w "\nHTTP:%{http_code}\n" -X POST localhost:8000/score -H "Content-Type: application/json" -d '{"numero":"POL-NO-EXISTE"}'` | `{"error":"no existe la póliza POL-NO-EXISTE"}`<br>`HTTP:200` | Se lanza `HTTPException(status_code=404)` |
| H22 | Actualizar una póliza inexistente responde 200 | Mismo patrón en el PUT: el error viaja en el cuerpo y el código de estado afirma que la operación salió bien | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -w "\nHTTP:%{http_code}\n" -X PUT localhost:8000/polizas/999999 -H "Content-Type: application/json" -d '{"prima":999}'` | `{"error":"no existe la póliza 999999"}`<br>`HTTP:200` | Se lanza `HTTPException(status_code=404)` |
| H14 | Un número de póliza repetido responde 500 y deja el servicio inservible | La restricción `unique` de la base falla y, como la sesión es única y nadie hace `rollback`, queda en estado de error para todas las peticiones siguientes | M6 · 5. Routing y CRUD | `v0-semilla` | `curl -s -o /dev/null -w "%{http_code}\n" -X POST localhost:8000/polizas -H "Content-Type: application/json" -d '{"numero":"POL-2026-00001","asegurado":"Otro Nombre","tipo":"auto","prima":1000,"fecha_inicio":"2026-01-01","fecha_fin":"2026-12-31","siniestros":[]}'; curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/polizas` | `500`<br>`500` | Se comprueba el número antes de insertar y se devuelve 409; con sesión por petición, un fallo deja de afectar a las peticiones siguientes |

## 5 · Pruebas

La batería que viene en el repositorio y lo que le hace a los datos.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H23 | Las pruebas del repositorio escriben en la base de datos de la aplicación | `tests/test_api.py` no sustituye la sesión, así que cada corrida añade pólizas a `app.db` y ensucia los datos del servicio | M10 · 6. Fixtures en pytest | `v0-semilla` | `a=$(md5sum app.db); python -m pytest tests/test_api.py -q >/dev/null 2>&1; b=$(md5sum app.db); [ "$a" = "$b" ] && echo IGUAL \|\| echo CAMBIO` | `CAMBIO` | Los tests propios sustituyen la sesión con `app.dependency_overrides` sobre una base temporal |
| H24 | Correr las pruebas dos veces seguidas falla | `tests/test_api.py` crea siempre la póliza `POL-TEST-00001`: la segunda ejecución choca con la restricción de unicidad y, al compartirse la sesión, arrastra al test siguiente | M10 · 4. Framework pytest | `v0-semilla` | `python -m pytest tests/test_api.py -q >/dev/null 2>&1; python -m pytest tests/test_api.py -q 2>&1 \| grep -c "^FAILED"` | `2` | Cada póliza de prueba lleva un número único y la base es temporal, de modo que la batería pasa dos veces seguidas |

## 6 · Contenedor y documentación de despliegue

La imagen y las instrucciones con las que otra persona pondría esto a correr.

| ID | Síntoma observable | Causa | Módulo · Sección | SHA donde se observa | Comando de evidencia | Salida obtenida | Corrección aplicada |
|----|--------------------|-------|------------------|----------------------|----------------------|-----------------|---------------------|
| H25 | La imagen parte de una base que cambia sola | `python:latest` apunta siempre a la última versión publicada, así que dos construcciones separadas en el tiempo no producen la misma imagen | M11 · 7. Imagen base slim-bookworm | `v0-semilla` | `grep -n "^FROM" Dockerfile` | `1:FROM python:latest` | Se fija `python:3.11.9-slim-bookworm` |
| H26 | La imagen se construye en una sola etapa | Todo lo necesario para instalar las dependencias queda dentro de la imagen final, que arrastra herramientas y caché que no se usan al ejecutar | M11 · 9. Multi-stage builds | `v0-semilla` | `grep -c "^FROM" Dockerfile` | `1` | Dos etapas: la primera instala las dependencias y la segunda solo copia el entorno ya armado |
| H27 | El contenedor corre como administrador | El `Dockerfile` no declara ningún usuario, de modo que el proceso queda con todos los privilegios dentro del contenedor | M11 · 12. Conclusión y buenas prácticas | `v0-semilla` | `grep -c "USER" Dockerfile` | `0` | Se crea un usuario sin privilegios y el proceso corre con él |
| H28 | La imagen no declara ningún chequeo de salud | Sin `HEALTHCHECK`, Docker no distingue un contenedor vivo de uno que arrancó y dejó de responder | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `grep -c "HEALTHCHECK" Dockerfile` | `0` | Se añade un `HEALTHCHECK` que consulta `/health` |
| H29 | El contenedor arranca en modo desarrollo y no responde desde fuera | El `CMD` usa `--reload`, que es de desarrollo, y `--host 127.0.0.1`, que hace que el servicio solo se escuche a sí mismo dentro del contenedor | M11 · 6. Estructura de un Dockerfile | `v0-semilla` | `grep -n "CMD" Dockerfile` | `8:CMD ["uvicorn", "main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"]` | El `CMD` aplica la migración y arranca sin `--reload` y con `--host 0.0.0.0` |
| H30 | No existe `.dockerignore` | Con `COPY . .` y sin lista de exclusiones, la imagen se lleva dentro el entorno virtual, la base de datos y el archivo de secretos | M11 · 8. Contexto de construcción | `v0-semilla` | `git ls-files \| grep -c dockerignore` | `0` | Se añade `.dockerignore` que excluye el entorno, `*.db` y `.env` |
| H31 | El README documenta un arranque que no funciona | Indica `--reload` como comando de producción, no menciona ni la configuración ni la migración, y presenta la base versionada como una virtud; siguiéndolo al pie de la letra el servicio arranca sin tablas | M10 · 7. Reproducibilidad sin Docker | `v0-semilla` | `grep -n "uvicorn main:app --reload" README.md; grep -c alembic README.md` | `19:uvicorn main:app --reload --host 127.0.0.1 --port 8000`<br>`0` | Se reescribe con los cinco pasos reales: entorno, dependencias, `.env`, `alembic upgrade head` y `uvicorn` sin `--reload` |

---

## Candidatos descartados, y por qué

Estos se consideraron y **no** entraron en la tabla. Se dejan escritos porque la
decisión de descartarlos forma parte del diagnóstico: el enunciado advierte que una
fila que no corresponda a un defecto real resta la mitad de lo que suma una correcta.

**Por compartir causa con una fila que ya está**

| Candidato | Por qué se descarta |
|---|---|
| Las 12 pólizas de `app.db` tienen el asegurado nulo | Es la **consecuencia** de H10, el validador que no devuelve el valor, no un defecto aparte. Se incorporó como evidencia adicional en la causa de H10 |
| Ninguna ruta declara `response_model` | Es exactamente la causa que ya declara H7. Dos filas para un solo problema |
| El código de firma es adivinable | Se calcula con una fórmula pública a partir de una clave que está en el repositorio: es la consecuencia de H1 y H7 juntos. Vale como explicación, no como fila |
| `--reload` aparece también en el README línea 22 y en `main.py` línea 135 | Es el mismo defecto de H31 en otros dos renglones |

**Por no incumplir ninguna regla del enunciado ni tener respaldo en el material**

| Candidato | Por qué se descarta |
|---|---|
| `/polizas`, `/siniestros` y `/resumen` emiten una consulta por póliza | Es un defecto real —13 consultas con 12 pólizas—, pero ninguna sección de los módulos 6 a 11 trata la carga de relaciones, de modo que la cita sería forzada. Además se califica aparte, en la Parte C, que es donde se documenta |
| Los listados no admiten paginación | Devolver 2000 pólizas en una sola respuesta es discutible, pero el enunciado no lo exige en ninguna regla |
| `creado_en` guarda la hora local del servidor y no una hora universal | Real, pero menor aquí y sin regla ni sección que lo respalde |
| Las columnas que enlazan las tablas no tienen índice | Afecta al rendimiento con muchos registros; mismo motivo que el anterior |

**Por no superar la comprobación**

| Candidato | Qué se midió |
|---|---|
| Los montos se guardan con decimales de coma flotante | La sospecha era que los totales acumularan errores de centavos. Se creó una póliza con siniestros de 5500.10, 3200.20 y 1100.30: la suma interna da `9800.599999999999`, pero `/resumen` redondea a dos decimales y responde `9800.6`, que es correcto. El defecto existe en el cálculo y queda tapado en la respuesta, así que **no se pudo demostrar un resultado incorrecto** y no se documenta |

---

# Parte C — Interpretación de las consultas

Los conteos salen de `contar_consultas.py`, que **no se modificó**. Cada cifra se
reprodujo dos veces con el mismo resultado: el número de consultas es determinista.
Los tiempos solo se citan para interpretar, porque cambian de una máquina a otra.

La medición «antes» corresponde al código tal como quedó al terminar la Parte B, es
decir con todas las relaciones cargándose de forma perezosa.

## Mediciones de respaldo

Los cuatro párrafos siguientes citan tres cosas además de los conteos finales: el estado
anterior, las alternativas descartadas y el inflado de filas del `JOIN`. Las tres se
midieron y aquí quedan los números, para que se puedan contrastar. El enunciado solo pide
explicar los conteos que obtuvimos; esta sección es respaldo.

**Las cuatro estrategias en los cuatro endpoints**, con 2000 pólizas y tres siniestros por
póliza. Cada columna es una corrida completa de `contar_consultas.py` sobre el servicio con
esa estrategia aplicada a los cuatro endpoints a la vez:

| Endpoint | `lazy` | `selectinload` | `joinedload` | `agregada` | Elegida |
|---|---|---|---|---|---|
| `/polizas` | 2001 · 1262 ms | 5 · 195 ms | 1 · 181 ms | no aplicable | `selectinload` |
| `/polizas/{id}` | 2 · 3,9 ms | 2 · 3,8 ms | 1 · 2,9 ms | no aplicable | `joinedload` |
| `/siniestros` | 2001 · 720 ms | 5 · 238 ms | 1 · 144 ms | no aplicable | `joinedload` |
| `/resumen` | 2001 · 1807 ms | 5 · 160 ms | 1 · 134 ms | 1 · 16 ms | `agregada` |

`agregada` no aplica a los tres primeros endpoints: el contrato exige devolver la lista de
siniestros de cada póliza, y una consulta de agregación devuelve recuentos, no listas.

Dos lecturas de esta tabla sostienen las decisiones:

- **En `/resumen`, `joinedload` y `agregada` emiten una sola consulta las dos, y difieren
  en un factor de ocho en tiempo**: 134 ms contra 16 ms. El conteo de consultas, por sí
  solo, no distingue la buena opción de la mala, porque `joinedload` trae los 6000
  siniestros a memoria para contarlos y `agregada` no trae ninguno. Es el caso que el
  enunciado anuncia como «seguirla da peor rendimiento».
- **En `/polizas`, `joinedload` gana en las dos columnas** —1 consulta contra 5 y 181 ms
  contra 195— y aun así no se eligió. El motivo está en el párrafo correspondiente y se
  apoya en el inflado de filas, medido justo abajo.

**El inflado de filas del `JOIN`**, contado sobre la base de datos que trae `v0-semilla`,
con 12 pólizas y 24 siniestros:

| Consulta | Filas que devuelve el `JOIN` | Filas que hacen falta | Factor |
|---|---|---|---|
| `/polizas` | 24 | 12 pólizas | ×2,0 |
| `/siniestros` | 24 | 24 siniestros | ×1,0 |

Ese factor es la razón por la que dos endpoints que devuelven los mismos datos eligen
estrategias distintas. En `/polizas` la relación va de una póliza a muchos siniestros y el
`JOIN` repite los datos de la póliza en cada fila, de modo que el factor sube con los
siniestros que tenga cada una. En `/siniestros` cada siniestro pertenece a una sola póliza
y el `JOIN` no multiplica nada: las filas que devuelve son las que hay que publicar.

**Cómo se reprodujo cada columna.** El estado `lazy` se reconstruyó retirando las tres
opciones de carga de `main.py` y devolviendo `resumen_cartera` a una versión que trae las
pólizas y cuenta sus siniestros en Python. Las columnas `selectinload` y `joinedload` se
obtuvieron aplicando esa misma estrategia a los cuatro endpoints, y en `/resumen` cargando
los siniestros de forma anticipada para contarlos en Python. Tras cada corrida `main.py` y
`servicios.py` se restauraron y se comprobó que quedaban idénticos; la batería completa
volvió a `37 passed, 1 xfailed`.

**Sobre los tiempos.** Los de esta sección y los de los párrafos siguientes salen de una
misma tanda de mediciones y **no son reproducibles**: entre corridas en esta misma máquina,
`/polizas` con `selectinload` ha dado entre 195 y 432 ms. Solo se citan para interpretar, y
lo que se compara entre estrategias es el orden de magnitud, no la cifra exacta. Lo que sí
se reproduce, y es lo que se califica, es la columna de consultas.

Por eso los tiempos de esta tabla no coinciden con los de `CONSULTAS.csv`: el CSV mide el
servicio final, con una estrategia distinta en cada endpoint, y las columnas de arriba salen
de corridas en las que una misma estrategia se aplicó a los cuatro a la vez. **Los conteos
de consultas sí coinciden** en los cuatro casos elegidos: 5, 1, 1 y 1 con 2000 pólizas, en
la tabla y en el CSV.

## `/polizas`

Antes emitía **11 consultas con 10 pólizas y 2001 con 2000**: una para traer las
pólizas y después una más por cada póliza, al pedir sus siniestros en el momento de
construir la respuesta. Es el problema N+1 en su forma más clara, y crece con la
cartera: con diez mil pólizas serían diez mil una consultas para una sola petición.

Con `selectinload` baja a **2 consultas con 10 pólizas y 5 con 2000**.

Las 5 sorprenden si uno espera 2, y la explicación es concreta: `selectinload` trae
los siniestros con un `IN` sobre los identificadores de las pólizas, y SQLAlchemy
parte esa lista en tandas de 500 para no emitir una consulta desmedida. Son 2000
pólizas, cuatro tandas, más la consulta inicial: 5. Es decir que el número ya no
depende de cuántos siniestros haya, sino que sube de a un escalón cada 500 pólizas.

También medimos la alternativa en este mismo endpoint: `joinedload` da **1 consulta
y 181 ms**, frente a 5 consultas y 195 ms de `selectinload`. Con tres siniestros por
póliza resultó incluso más rápido, así que la expectativa de que «traerlo todo de un
golpe» penalizaría aquí **no se cumplió**. Aun así dejamos `selectinload`, y el
criterio es el crecimiento: `joinedload` devuelve una fila por siniestro repitiendo
en cada una los datos de la póliza, de modo que la respuesta engorda con los
siniestros —con tres por póliza son 6000 filas; con cien serían 200 000—, mientras
que `selectinload` transporta cada dato una sola vez y su número de consultas
depende únicamente de cuántas pólizas hay.

## `/polizas/{id}`

Emitía **2 consultas con 10 pólizas y 2 con 2000**: una para la póliza y otra para
sus siniestros. Lo revelador es que el número **no cambia con el tamaño de la base**,
y por eso este es el caso que advierte el enunciado: el código incumplía la regla de
cargar todo de una vez y la medición dice que daba casi igual. Al pedir una sola
póliza no hay ningún N+1 que evitar, porque no hay un bucle sobre muchas filas.

Con `joinedload` baja a **1 consulta, con 10 y con 2000**. La mejora es pequeña y
constante, pero no cuesta nada: al tratarse de una sola póliza, el `JOIN` repite sus
datos solo tantas veces como siniestros tenga, que aquí son tres.

## `/siniestros`

Antes emitía **11 consultas con 10 pólizas y 2001 con 2000**: una para traer los
siniestros y después una por cada póliza distinta, al pedir su número. No es una
consulta por siniestro —son 6000 siniestros y no 6001 consultas— porque la sesión
recuerda las pólizas que ya trajo y no las vuelve a pedir.

Con `joinedload` baja a **1 consulta**, con los dos tamaños. Aquí la relación va al
revés que en `/polizas`: cada siniestro pertenece a **una sola** póliza, así que el
`JOIN` no multiplica filas y traerlo todo junto no tiene contrapartida.

## `/resumen`

Antes emitía **11 consultas con 10 pólizas y 2001 con 2000**, por el mismo motivo
que `/polizas`: traía todas las pólizas y, por cada una, todos sus siniestros, para
contarlos y sumarlos en Python.

Con la estrategia `agregada` baja a **1 consulta**, con los dos tamaños, y el tiempo
cae de 1807 ms a 16 ms.

Este es el otro caso que advierte el enunciado, y es el inverso del anterior: aquí
cargar todo de una vez **es la peor opción**, la use uno con `joinedload` o con
`selectinload`. El resumen no necesita los siniestros: necesita cuántos son y cuánto
suman. Pedirle eso a la base con `COUNT`, `SUM` y `GROUP BY` devuelve una fila por
póliza y no trae ni un solo siniestro a memoria, mientras que cualquier carga
anticipada tendría que mover 6000 filas para después descartarlas.

El `outerjoin` conserva las pólizas que no tienen siniestros, que con un `JOIN`
normal desaparecerían del resumen, y `coalesce` deja su total en cero en lugar de
nulo.
