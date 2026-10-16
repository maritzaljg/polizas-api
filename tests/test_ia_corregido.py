"""Batería de la IA, corregida (Parte D).

    pytest tests/test_ia_corregido.py

La propuesta original (`ia_tests_propuesta.py`) está en verde y no demuestra
nada. Los tres defectos y su evidencia están en `DICTAMEN_IA.md`. En resumen:

1. **El aislamiento no aislaba.** Registraba el doble con una función local como
   clave, no con la dependencia que usa la aplicación, de modo que el reemplazo
   nunca se aplicaba y las pruebas escribían en la base real del servicio.
   Aquí se sustituye `database.get_db`, que es la dependencia de verdad, por una
   sesión sobre una base temporal.

2. **Las afirmaciones no podían fallar.** Aceptaban varios resultados a la vez
   (`in (200, 201, 422)`, `in (200, 404)`, `< 500`). Aquí cada afirmación exige
   un único resultado.

3. **Los datos eran aleatorios y sin semilla.** El resultado cambiaba de una
   corrida a otra y un fallo no se podía reproducir. Aquí los datos son fijos y
   explícitos; la variedad se consigue enumerando casos, no sorteándolos.

Las pruebas cubren a propósito las tres clases de rotura que el enunciado
anuncia: un 404 que deja de devolverse, un `commit` que se quita y un validador
que acepta lo que no debe.
"""
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

DB = RAIZ / ".test_ia_corregido.db"
DB.unlink(missing_ok=True)
URL = f"sqlite:///{DB}"
os.environ.setdefault("DATABASE_URL", URL)

import database  # noqa: E402
from main import app  # noqa: E402

_engine = create_engine(URL, connect_args={"check_same_thread": False})
database.Base.metadata.create_all(_engine)
_Sesion = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def _sesion_de_prueba():
    db = _Sesion()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _aislar():
    """Sustituye la dependencia real de la aplicación, no una función homónima."""
    previo = app.dependency_overrides.get(database.get_db)
    app.dependency_overrides[database.get_db] = _sesion_de_prueba
    yield
    if previo is None:
        app.dependency_overrides.pop(database.get_db, None)
    else:
        app.dependency_overrides[database.get_db] = previo


cliente = TestClient(app, raise_server_exceptions=False)

SINIESTRO = {"fecha": "2026-03-02", "monto": 850_000,
             "descripcion": "Choque leve", "estado": "abierto"}

# Datos fijos y explícitos: el mismo caso en cada corrida, de modo que un fallo
# se pueda reproducir. Los números son únicos entre sí porque la base temporal
# se borra al empezar.
POLIZA = {
    "numero": "POL-IA-000001",
    "asegurado": "Ana Rueda",
    "tipo": "auto",
    "prima": 1_250_000,
    "fecha_inicio": "2026-01-15",
    "fecha_fin": "2027-01-14",
}


def _poliza(numero: str, **extra):
    datos = {**POLIZA, "numero": numero}
    datos.update(extra)
    return datos


# --- Creación ---------------------------------------------------------------

def test_crear_poliza_devuelve_201_y_los_datos_enviados():
    r = cliente.post("/polizas", json=_poliza("POL-IA-000010"))
    assert r.status_code == 201, f"devolvió {r.status_code}"
    cuerpo = r.json()
    assert cuerpo["numero"] == "POL-IA-000010"
    assert cuerpo["asegurado"] == "Ana Rueda"
    assert cuerpo["tipo"] == "auto"
    assert cuerpo["prima"] == 1_250_000


@pytest.mark.parametrize("tipo,prima", [
    ("auto", 1_000_000),
    ("hogar", 2_500_000),
    ("vida", 4_750_000),
])
def test_cada_tipo_de_poliza_se_crea_igual(tipo, prima):
    """Reemplaza al sorteo de tipos y primas: los tres casos se prueban siempre,
    y si uno falla se sabe cuál."""
    numero = f"POL-IA-0001{tipo[:2].upper()}"
    r = cliente.post("/polizas", json=_poliza(numero, tipo=tipo, prima=prima))
    assert r.status_code == 201, f"el tipo {tipo} devolvió {r.status_code}"
    assert r.json()["tipo"] == tipo
    assert r.json()["prima"] == prima


def test_la_poliza_creada_persiste_en_una_peticion_posterior():
    """Vigila que la creación se confirme en la base.

    Si se quita el `commit` del handler, la respuesta de creación puede seguir
    pareciendo correcta y la póliza no quedar guardada. Por eso se consulta en
    una petición aparte, no en la misma.
    """
    creada = cliente.post("/polizas", json=_poliza("POL-IA-000020")).json()
    r = cliente.get(f"/polizas/{creada['id']}")
    assert r.status_code == 200, f"la póliza no quedó guardada: devolvió {r.status_code}"
    assert r.json()["numero"] == "POL-IA-000020"


def test_numero_repetido_da_409():
    cliente.post("/polizas", json=_poliza("POL-IA-000030"))
    r = cliente.post("/polizas", json=_poliza("POL-IA-000030"))
    assert r.status_code == 409, f"devolvió {r.status_code}"


# --- Consulta y errores -----------------------------------------------------

def test_consultar_poliza_inexistente_da_404():
    """La versión original aceptaba 200 o 404 y por eso pasaba contra el servicio
    roto y contra el corregido por igual."""
    r = cliente.get("/polizas/999999")
    assert r.status_code == 404, f"devolvió {r.status_code}"


def test_declarar_siniestro_sobre_poliza_inexistente_da_404():
    r = cliente.post("/polizas/999999/siniestros", json=SINIESTRO)
    assert r.status_code == 404, f"devolvió {r.status_code}"


def test_listar_polizas_devuelve_las_creadas():
    """La versión original solo exigía que no hubiera un error de servidor."""
    creada = cliente.post("/polizas", json=_poliza("POL-IA-000040")).json()
    r = cliente.get("/polizas")
    assert r.status_code == 200
    numeros = [p["numero"] for p in r.json()]
    assert creada["numero"] in numeros, "la póliza creada no aparece en el listado"


# --- Validación de entrada --------------------------------------------------

@pytest.mark.parametrize("caso,cambio", [
    ("prima cero", {"prima": 0}),
    ("prima negativa", {"prima": -1}),
    ("fechas invertidas", {"fecha_inicio": "2027-01-14", "fecha_fin": "2026-01-15"}),
    ("asegurado demasiado corto", {"asegurado": "A"}),
    ("siniestro anidado con monto negativo", {"siniestros": [{**SINIESTRO, "monto": -50}]}),
])
def test_las_entradas_invalidas_se_rechazan_con_422(caso, cambio):
    """Vigila que los validadores rechacen de verdad.

    Si uno de ellos deja de aplicarse, la creación respondería 201 y aquí se
    vería: cada caso exige exactamente 422.
    """
    r = cliente.post("/polizas", json=_poliza(f"POL-IA-00005{len(caso)}", **cambio))
    assert r.status_code == 422, f"«{caso}» devolvió {r.status_code} en vez de 422"


# --- Puntuación -------------------------------------------------------------

def test_score_devuelve_puntaje_y_registra_la_prediccion():
    """La versión original aceptaba que la respuesta trajera `puntaje` **o**
    `error`, de modo que pasaba también cuando el servicio no encontraba la
    póliza."""
    datos = _poliza("POL-IA-000060")
    assert cliente.post("/polizas", json=datos).status_code == 201

    r = cliente.post("/score", json={"numero": datos["numero"]})
    assert r.status_code == 200, f"devolvió {r.status_code}"
    cuerpo = r.json()
    assert cuerpo["numero"] == datos["numero"]
    assert 0.0 <= cuerpo["puntaje"] <= 1.0
    assert isinstance(cuerpo["alto_riesgo"], bool)

    registradas = cliente.get("/predicciones").json()
    assert any(p["numero"] == datos["numero"] for p in registradas), \
        "la predicción no quedó registrada"


def test_score_de_poliza_inexistente_da_404():
    r = cliente.post("/score", json={"numero": "POL-IA-999999"})
    assert r.status_code == 404, f"devolvió {r.status_code}"


# --- Resumen ----------------------------------------------------------------

def test_el_resumen_trae_los_numeros_de_la_poliza():
    """La versión original solo comprobaba que la respuesta fuera una lista."""
    datos = _poliza("POL-IA-000070", siniestros=[SINIESTRO, SINIESTRO])
    assert cliente.post("/polizas", json=datos).status_code == 201

    r = cliente.get("/resumen")
    assert r.status_code == 200
    fila = [f for f in r.json() if f["numero"] == datos["numero"]]
    assert fila, "la póliza no aparece en el resumen"
    assert fila[0]["n_siniestros"] == 2
    assert fila[0]["monto_total"] == 2 * SINIESTRO["monto"]
