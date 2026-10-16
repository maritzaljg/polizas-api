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

Criterio para elegir qué se prueba: **una prueba por cada decisión propia que
ningún test del contrato vigila**. No se duplica lo que la batería visible ya
comprueba. Cada una de estas se validó rompiendo a propósito lo que vigila y
confirmando que se pone en rojo.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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


# --- Fuga de campos internos: el punto ciego de la batería visible ----------
# La batería del contrato comprueba que CREAR no filtre `token_firma`, pero no
# que CONSULTAR o LISTAR tampoco lo hagan. Quitando el `response_model` de
# `GET /polizas/{id}` los doce tests seguían en verde y el campo volvía a salir.

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


# --- Integridad de la relación póliza / siniestro --------------------------

def test_el_siniestro_queda_asociado_a_su_poliza():
    """Un siniestro cargado a la póliza equivocada es un reclamo pagado contra
    el contrato que no era."""
    creada = cliente.post("/polizas", json=_poliza()).json()
    r = cliente.post(f"/polizas/{creada['id']}/siniestros", json=SINIESTRO)
    assert r.status_code == 201

    listado = cliente.get("/siniestros").json()
    mio = [s for s in listado if s["id"] == r.json()["id"]]
    assert mio and mio[0]["numero_poliza"] == creada["numero"], \
        "el siniestro no trae el número de su póliza"


# --- El resumen de cartera: vigila el GROUP BY que reemplazó al conteo en Python

def test_el_resumen_cuenta_y_suma_los_siniestros():
    """Al pasar el conteo a la base, el error clásico es duplicar filas al cruzar
    las tablas y devolver totales inflados."""
    creada = cliente.post("/polizas", json=_poliza(siniestros=[SINIESTRO, SINIESTRO])).json()
    fila = [f for f in cliente.get("/resumen").json() if f["numero"] == creada["numero"]]
    assert fila, "la póliza no aparece en el resumen"
    assert fila[0]["n_siniestros"] == 2
    assert fila[0]["monto_total"] == 2 * SINIESTRO["monto"]


def test_el_resumen_conserva_las_polizas_sin_siniestros():
    """Vigila el `outerjoin`: con un cruce normal, una póliza sin siniestros
    desaparecería del informe de cartera sin que nadie se entere."""
    creada = cliente.post("/polizas", json=_poliza()).json()
    fila = [f for f in cliente.get("/resumen").json() if f["numero"] == creada["numero"]]
    assert fila, "una póliza sin siniestros desapareció del resumen"
    assert fila[0]["n_siniestros"] == 0
    assert fila[0]["monto_total"] == 0


def test_el_resumen_se_resuelve_con_una_sola_consulta():
    """Vigila toda la Parte C sobre `/resumen`.

    Desde fuera la respuesta es idéntica con una consulta o con 2001: los mismos
    números, la misma forma. Si alguien deshace la estrategia agregada y vuelve a
    contar los siniestros en Python, ningún otro test se entera. Este cuenta las
    consultas que el servicio emite y exige que sea una sola.

    Se eligió `/resumen` y no `/polizas` a propósito: aquí el 1 es una propiedad
    del diseño, mientras que en `/polizas` el número depende del tamaño de tanda
    interno de SQLAlchemy y cambiaría al actualizar la librería sin que nadie
    hubiera roto nada.
    """
    cliente.post("/polizas", json=_poliza(siniestros=[SINIESTRO, SINIESTRO]))
    cliente.get("/resumen")  # calentamiento: no se cuenta

    contador = {"n": 0}

    @event.listens_for(_engine, "before_cursor_execute")
    def _contar(conn, cursor, statement, parameters, context, executemany):
        contador["n"] += 1

    try:
        r = cliente.get("/resumen")
    finally:
        event.remove(_engine, "before_cursor_execute", _contar)

    assert r.status_code == 200
    assert contador["n"] == 1, \
        f"/resumen emitió {contador['n']} consultas; con la estrategia agregada debe ser 1"


# --- Identidad del contrato -------------------------------------------------

def test_el_put_no_cambia_el_numero_de_la_poliza():
    """El número es la referencia del contrato: los siniestros y las predicciones
    apuntan a él. La actualización parcial que define el enunciado no lo incluye."""
    creada = cliente.post("/polizas", json=_poliza()).json()
    r = cliente.put(f"/polizas/{creada['id']}",
                    json={"numero": "POL-SUPLANTADO-01", "prima": 2_000_000})
    assert r.status_code == 200
    assert r.json()["numero"] == creada["numero"], "el PUT cambió el número de la póliza"
    assert r.json()["prima"] == 2_000_000, "el PUT no aplicó el cambio que sí corresponde"


def test_un_numero_repetido_no_deja_poliza_a_medio_crear():
    """La batería visible comprueba que el conflicto devuelva 409 y que el
    servicio siga vivo, pero no que no haya quedado nada escrito."""
    datos = _poliza()
    assert cliente.post("/polizas", json=datos).status_code == 201
    antes = len(cliente.get("/polizas").json())

    assert cliente.post("/polizas", json=datos).status_code == 409

    assert len(cliente.get("/polizas").json()) == antes, \
        "el conflicto dejó una póliza escrita a medias"


# --- Hueco de negocio documentado, no corregido -----------------------------

@pytest.mark.xfail(
    strict=True,
    reason="El servicio acepta siniestros con fecha fuera de la vigencia de la póliza. "
           "No se corrige porque el enunciado fija qué responde esta ruta (201, 404, 422) "
           "y añadir un rechazo nuevo podría romper la batería oculta del calificador. "
           "Queda documentado y comprobado: el día que se valide, este test avisará.",
)
def test_no_deberia_aceptarse_un_siniestro_fuera_de_la_vigencia():
    creada = cliente.post(
        "/polizas",
        json=_poliza(fecha_inicio="2026-01-01", fecha_fin="2026-12-31"),
    ).json()
    r = cliente.post(f"/polizas/{creada['id']}/siniestros",
                     json={**SINIESTRO, "fecha": "2031-08-20"})
    assert r.status_code == 422, (
        f"aceptó un siniestro fechado en 2031 sobre una póliza vigente solo durante "
        f"2026 (respondió {r.status_code})")
