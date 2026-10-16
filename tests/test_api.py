"""Pruebas propias del servicio (B8).

    pytest tests/test_api.py

Qué cambia respecto de la versión del semilla, y por qué:

1. **Aislamiento.** La versión anterior escribía en `app.db`, la base real de la
   aplicación: correr los tests ensuciaba los datos del servicio. Aquí la sesión
   se sustituye con `app.dependency_overrides` por una sobre `.test_api.db`, una
   base temporal que se borra al empezar.
2. **Repetibilidad.** La versión anterior usaba siempre el mismo número de
   póliza, así que la segunda ejecución seguida fallaba con un conflicto. Aquí
   cada póliza lleva un número único.
3. **Cobertura de un punto ciego.** La batería visible comprueba que *crear* una
   póliza no filtre `token_firma`, pero no comprueba lo mismo al *consultarla*.
   Al quitar el `response_model` de `GET /polizas/{id}` los doce tests del
   contrato seguían en verde y el servicio volvía a filtrar el campo. Los dos
   primeros tests de aquí tapan ese hueco.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

RAIZ = Path(__file__).parent.parent
sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)

DB = RAIZ / ".test_api.db"
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
    """Sustituye la sesión antes de cada test y la devuelve al terminar."""
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


def _poliza(**extra):
    """Una póliza válida con número único, para poder correr los tests dos veces."""
    base = {
        "numero": f"POL-MJ-{uuid.uuid4().hex[:6].upper()}",
        "asegurado": "Ana Rueda",
        "tipo": "auto",
        "prima": 1_250_000,
        "fecha_inicio": "2026-01-15",
        "fecha_fin": "2027-01-14",
    }
    base.update(extra)
    return base


# --- El punto ciego: consultar tampoco debe filtrar campos internos ---------

def test_consultar_una_poliza_no_filtra_campos_internos():
    creada = cliente.post("/polizas", json=_poliza()).json()
    r = cliente.get(f"/polizas/{creada['id']}")
    assert r.status_code == 200
    assert "token_firma" not in r.json(), "consultar una póliza expone token_firma"


def test_listar_polizas_no_filtra_campos_internos():
    cliente.post("/polizas", json=_poliza())
    r = cliente.get("/polizas")
    assert r.status_code == 200
    assert all("token_firma" not in p for p in r.json()), \
        "el listado de pólizas expone token_firma"


# --- Contrato de creación y relaciones --------------------------------------

def test_crear_poliza_devuelve_201_con_su_numero():
    datos = _poliza()
    r = cliente.post("/polizas", json=datos)
    assert r.status_code == 201
    assert r.json()["numero"] == datos["numero"]


def test_el_siniestro_queda_asociado_a_su_poliza():
    creada = cliente.post("/polizas", json=_poliza()).json()
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201

    listado = cliente.get("/siniestros").json()
    mio = [s for s in listado if s["id"] == r.json()["id"]]
    assert mio and mio[0]["numero_poliza"] == creada["numero"], \
        "el siniestro no trae el número de su póliza"


def test_el_resumen_cuenta_y_suma_los_siniestros():
    creada = cliente.post("/polizas", json=_poliza(siniestros=[SINIESTRO, SINIESTRO])).json()
    fila = [f for f in cliente.get("/resumen").json() if f["numero"] == creada["numero"]]
    assert fila, "la póliza no aparece en el resumen"
    assert fila[0]["n_siniestros"] == 2
    assert fila[0]["monto_total"] == 2 * SINIESTRO["monto"]


def test_la_prediccion_queda_registrada_con_el_numero():
    datos = _poliza()
    cliente.post("/polizas", json=datos)
    r = cliente.post("/score", json={"numero": datos["numero"]})
    assert r.status_code == 200
    assert 0.0 <= r.json()["puntaje"] <= 1.0

    registradas = cliente.get("/predicciones").json()
    assert any(p["numero"] == datos["numero"] for p in registradas)


def test_health_informa_el_estado_de_la_base():
    cuerpo = cliente.get("/health").json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["base_de_datos"] == "ok"
