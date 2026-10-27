# Hallazgos — Parte A

**Grupo:** individual · **Integrante:** Maritza Liliana Jiménez Gómez

Este documento reúne los **31 defectos** encontrados en el servicio polizas-api-v0
antes de las correcciones. Cada fila declara el comando que reproduce el defecto y la
salida literal obtenida al ejecutarlo sobre el commit `v0-semilla`, en una copia del
repositorio parada en ese commit y con la base de datos original intacta. Las 31
salidas se volvieron a comprobar una por una antes de entregar.

Los hallazgos están agrupados por el tipo de problema. Dentro de cada grupo, las filas
se ordenan dejando de último el comando de H14 —el número de póliza duplicado—, porque
ese defecto deja la sesión compartida inservible y cualquier petición posterior responde
500 aunque sea correcta: ejecutarlo antes contaminaría la evidencia de los demás.

> **Sobre el número de hallazgos.** El enunciado publicado pedía entre 8 y 14, y
> `verificar_entrega.py` comprueba ese rango, de modo que marcará esta tabla como fuera
> de rango. Se documentan los 31 porque el docente autorizó después documentarlos todos
> y porque el nivel máximo del criterio C3 se describe como «todos los defectos
> hallados». Ninguna fila se incluyó sin un comando que la reproduzca.

**Índice**

1. **Configuración, secretos y reproducibilidad** — 5 hallazgos: H1, H2, H15, H16, H17
2. **Persistencia e inyección de dependencias** — 5 hallazgos: H3, H4, H18, H19, H20
3. **Validación de la entrada** — 3 hallazgos: H10, H11, H12
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

# Parte C — Interpretación de las consultas

Los conteos salen de `contar_consultas.py`, que **no se modificó**. Cada cifra se
reprodujo dos veces con el mismo resultado: el número de consultas es determinista.
Los tiempos solo se citan para interpretar, porque cambian de una máquina a otra.

La medición «antes» corresponde al código tal como quedó al terminar la Parte B, es
decir con todas las relaciones cargándose de forma perezosa.

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
y 367 ms**, frente a 5 consultas y 432 ms de `selectinload`. Con tres siniestros por
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
cae de 1368 ms a 15–23 ms.

Este es el otro caso que advierte el enunciado, y es el inverso del anterior: aquí
cargar todo de una vez **es la peor opción**, la use uno con `joinedload` o con
`selectinload`. El resumen no necesita los siniestros: necesita cuántos son y cuánto
suman. Pedirle eso a la base con `COUNT`, `SUM` y `GROUP BY` devuelve una fila por
póliza y no trae ni un solo siniestro a memoria, mientras que cualquier carga
anticipada tendría que mover 6000 filas para después descartarlas.

El `outerjoin` conserva las pólizas que no tienen siniestros, que con un `JOIN`
normal desaparecerían del resumen, y `coalesce` deja su total en cero en lugar de
nulo.
