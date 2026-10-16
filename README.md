# polizas-api-v0

Servicio de gestión de pólizas de la Aseguradora Santo Tomás. Registra pólizas
y los siniestros que se les declaran, resume la cartera y puntúa el riesgo de
cada póliza con un modelo, guardando cada predicción.

**Autora:** Maritza Liliana Jiménez Gómez · Trabajo individual · Taller del Corte II

## Requisitos

- Python **3.11.9**
- Docker, solo si se va a levantar en contenedor

## Instalación y arranque local

```bash
# 1 · Entorno virtual
python3.11 -m venv venv          # en Windows:  py -3.11 -m venv venv
source venv/bin/activate         # en Windows:  .\venv\Scripts\Activate.ps1

# 2 · Dependencias, con sus versiones fijadas
pip install -r requirements.txt

# 3 · Configuración: copiar la plantilla y ajustar los valores
cp .env.example .env             # en Windows:  copy .env.example .env

# 4 · Crear el esquema de la base de datos
alembic upgrade head

# 5 · Levantar el servicio
uvicorn main:app --host 0.0.0.0 --port 8000
```

El servicio queda en <http://localhost:8000>, con la documentación interactiva en
<http://localhost:8000/docs>.

> **Los pasos 3 y 4 no son opcionales.**
> Sin `.env` el servicio no arranca: `SECRETO_FIRMA` y `CLAVE_API_REASEGURO` no
> tienen valor por defecto a propósito, para que falten de forma evidente si
> alguien despliega sin configurarlas.
> Sin `alembic upgrade head` el servicio arranca pero la base no tiene tablas, y
> cualquier consulta responde 500. El esquema lo crea la migración, no el
> arranque de la aplicación.

> **Sobre `--reload`:** es cómodo mientras se programa, porque recoge los cambios
> sin reiniciar a mano, pero **no se usa en producción**: vigila los archivos de
> forma permanente y reinicia el proceso en caliente. El comando de arriba es el
> de producción.

## En contenedor

```bash
docker build -t polizas-api .
docker run -p 8000:8000 polizas-api
```

El contenedor aplica la migración y después levanta el servicio, así que no hace
falta ningún paso previo. Responde en <http://localhost:8000/health>.

La imagen **no lleva dentro** ni el archivo `.env` ni ninguna base de datos. Los
valores de configuración vienen como variables de entorno con marcadores
evidentes; en un despliegue real se sustituyen al arrancar:

```bash
docker run -p 8000:8000 \
  -e SECRETO_FIRMA="la-firma-de-verdad" \
  -e CLAVE_API_REASEGURO="la-clave-de-verdad" \
  polizas-api
```

> **Dónde viven los datos.** La base de datos se crea dentro del contenedor, en
> `/app/datos`. Eso significa que `docker restart` conserva los datos —es el
> mismo contenedor— pero borrar el contenedor y levantar otro desde la misma
> imagen empieza de cero, porque la imagen es solo la receta y no guarda nada de
> lo ocurrido mientras corría. Para conservarlos habría que montar un volumen.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/polizas` | Crea una póliza, con sus siniestros si ya tiene · **201** |
| GET | `/polizas` | Lista las pólizas con sus siniestros |
| GET | `/polizas/{id}` | Consulta una póliza · **404** si no existe |
| PUT | `/polizas/{id}` | Actualiza una póliza; solo cambia lo que se envía |
| POST | `/polizas/{id}/siniestros` | Declara un siniestro · **404** si la póliza no existe |
| GET | `/siniestros` | Lista los siniestros con el número de su póliza |
| GET | `/resumen` | Siniestros y monto total por póliza |
| POST | `/score` | Puntúa el riesgo de una póliza y guarda la predicción |
| GET | `/predicciones` | Histórico de predicciones |
| GET | `/health` | Estado del servicio y de la base de datos |

Un número de póliza repetido responde **409**, y una entrada inválida, **422**.

## Ejemplo de uso

```bash
curl -s -X POST localhost:8000/polizas \
  -H "Content-Type: application/json" \
  -d '{"numero":"POL-2026-00100","asegurado":"Ana Rueda","tipo":"auto",
       "prima":1250000,"fecha_inicio":"2026-01-15","fecha_fin":"2027-01-14"}'
```

```json
{"id": 1, "numero": "POL-2026-00100", "asegurado": "Ana Rueda", "tipo": "auto",
 "prima": 1250000.0, "fecha_inicio": "2026-01-15", "fecha_fin": "2027-01-14",
 "siniestros": []}
```

## Pruebas

```bash
pytest tests/ -q
```

Son dos baterías: `tests/test_contrato.py`, que llega intacta del repositorio
semilla, y `tests/test_api.py`, propia. Ambas se aíslan en bases temporales y no
tocan la base de datos de la aplicación. Hay además un test marcado como fallo
esperado, que documenta un hueco de negocio sin corregirlo: está explicado en
`HALLAZGOS.md`.

```bash
pytest tests/test_ia_corregido.py -q
```

La batería corregida de la Parte D, con el dictamen en `DICTAMEN_IA.md`.

## Estructura

```
polizas-api/
├── main.py                     rutas y contrato HTTP
├── esquemas.py                 entrada y salida, con sus validaciones
├── modelos.py                  tablas y relaciones
├── servicios.py                lógica de negocio: firma, puntaje y resumen
├── database.py                 motor y sesión por petición
├── config.py                   configuración leída del entorno
├── alembic/                    migraciones del esquema
├── tests/                      baterías de pruebas
├── Dockerfile · .dockerignore  imagen del servicio
├── .env.example                plantilla de configuración
├── HALLAZGOS.md                Parte A y Parte C
├── CONSULTAS.csv               conteos de consultas SQL
├── DICTAMEN_IA.md              Parte D
├── BITACORA_IA.md              Parte E
└── EQUIPO.md                   integrantes e identidades git
```

## Documentación adicional

- **[HALLAZGOS.md](HALLAZGOS.md)** — los catorce defectos del servicio original, cada uno con su comando de evidencia y la salida obtenida sobre `v0-semilla`, más la interpretación del conteo de consultas.
- **[CONSULTAS.csv](CONSULTAS.csv)** — cuatro endpoints por dos tamaños, con la estrategia de carga elegida y las consultas SQL medidas.
- **[DICTAMEN_IA.md](DICTAMEN_IA.md)** — auditoría de la batería de pruebas generada por IA: tres defectos, cada uno demostrado con una mutación.
- **[BITACORA_IA.md](BITACORA_IA.md)** — registro del uso de IA: prompts, qué se aceptó y qué se rechazó con su argumento.
