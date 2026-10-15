"""
polizas-api-v0 — Gestión de pólizas y siniestros.
Aseguradora Santo Tomás · prototipo interno.

Las rutas solo se ocupan del contrato HTTP: validan la entrada, piden la sesión
de base de datos con `Depends` y devuelven la forma declarada en `response_model`.
El esquema de la base lo crea Alembic, no el arranque del servicio.
"""
import pickle

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import servicios
from config import obtener_settings
from database import get_db
from esquemas import (
    PolizaActualizacion,
    PolizaEntrada,
    PolizaSalida,
    PrediccionSalida,
    PuntuacionEntrada,
    PuntuacionSalida,
    ResumenSalida,
    SaludSalida,
    SiniestroConPoliza,
    SiniestroEntrada,
    SiniestroSalida,
)
from modelos import Poliza, Prediccion, Siniestro

settings = obtener_settings()

with open(settings.RUTA_MODELO, "rb") as fh:
    modelo = pickle.load(fh)

app = FastAPI(title="Pólizas API", version="0.1.0")


@app.get("/health", response_model=SaludSalida)
def salud(db: Session = Depends(get_db)):
    """Sonda de salud: responde 200 e informa si la base de datos contesta."""
    try:
        db.execute(text("SELECT 1"))
        base = "ok"
    except Exception:
        base = "sin respuesta"
    return {"estado": "ok", "base_de_datos": base}


@app.post("/polizas", response_model=PolizaSalida, status_code=status.HTTP_201_CREATED)
def crear_poliza(datos: PolizaEntrada, db: Session = Depends(get_db)):
    """Crea una póliza con los siniestros que ya traiga declarados."""
    if db.scalar(select(Poliza).where(Poliza.numero == datos.numero)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"ya existe una póliza con el número {datos.numero}")

    poliza = Poliza(
        numero=datos.numero,
        asegurado=datos.asegurado,
        tipo=datos.tipo,
        prima=datos.prima,
        fecha_inicio=datos.fecha_inicio,
        fecha_fin=datos.fecha_fin,
        token_firma=servicios.firmar(datos.numero, settings.SECRETO_FIRMA),
    )
    for s in datos.siniestros:
        poliza.siniestros.append(Siniestro(
            fecha=s.fecha, monto=s.monto, descripcion=s.descripcion, estado=s.estado))

    db.add(poliza)
    try:
        db.commit()
    except IntegrityError:
        # Carrera entre la comprobación y la inserción: la base tiene la última
        # palabra. Se deshace la transacción para que la sesión siga usable.
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f"ya existe una póliza con el número {datos.numero}")
    db.refresh(poliza)
    return poliza


@app.get("/polizas", response_model=list[PolizaSalida])
def listar_polizas(db: Session = Depends(get_db)):
    """Todas las pólizas, cada una con la lista de sus siniestros."""
    return db.scalars(select(Poliza).order_by(Poliza.id)).all()


@app.get("/polizas/{id_poliza}", response_model=PolizaSalida)
def obtener_poliza(id_poliza: int, db: Session = Depends(get_db)):
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {id_poliza}")
    return poliza


@app.put("/polizas/{id_poliza}", response_model=PolizaSalida)
def actualizar_poliza(id_poliza: int, datos: PolizaActualizacion, db: Session = Depends(get_db)):
    """Actualización parcial: solo se tocan los campos que vinieron."""
    poliza = db.get(Poliza, id_poliza)
    if poliza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {id_poliza}")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(poliza, campo, valor)
    db.commit()
    db.refresh(poliza)
    return poliza


@app.post("/polizas/{id_poliza}/siniestros", response_model=SiniestroSalida,
          status_code=status.HTTP_201_CREATED)
def declarar_siniestro(id_poliza: int, datos: SiniestroEntrada, db: Session = Depends(get_db)):
    if db.get(Poliza, id_poliza) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {id_poliza}")
    siniestro = Siniestro(poliza_id=id_poliza, fecha=datos.fecha, monto=datos.monto,
                          descripcion=datos.descripcion, estado=datos.estado)
    db.add(siniestro)
    db.commit()
    db.refresh(siniestro)
    return siniestro


@app.get("/siniestros", response_model=list[SiniestroConPoliza])
def listar_siniestros(db: Session = Depends(get_db)):
    """Todos los siniestros, cada uno con el número de su póliza."""
    siniestros = db.scalars(select(Siniestro).order_by(Siniestro.id)).all()
    return [
        {
            "id": s.id, "poliza_id": s.poliza_id, "numero_poliza": s.poliza.numero,
            "fecha": s.fecha, "monto": s.monto,
            "descripcion": s.descripcion, "estado": s.estado,
        }
        for s in siniestros
    ]


@app.get("/resumen", response_model=list[ResumenSalida])
def resumen(db: Session = Depends(get_db)):
    """Por póliza: cuántos siniestros tiene y cuánto suman."""
    return servicios.resumen_cartera(db)


@app.post("/score", response_model=PuntuacionSalida)
def puntuar(datos: PuntuacionEntrada, db: Session = Depends(get_db)):
    """Puntúa una póliza y deja registrada la predicción."""
    poliza = db.scalar(select(Poliza).where(Poliza.numero == datos.numero))
    if poliza is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"no existe la póliza {datos.numero}")

    puntaje = servicios.calcular_puntaje(poliza, modelo)
    prediccion = Prediccion(poliza_id=poliza.id, puntaje=puntaje,
                            alto_riesgo=puntaje > settings.UMBRAL_ALTO_RIESGO)
    db.add(prediccion)
    db.commit()
    return {"numero": poliza.numero, "puntaje": round(puntaje, 4),
            "alto_riesgo": prediccion.alto_riesgo}


@app.get("/predicciones", response_model=list[PrediccionSalida])
def listar_predicciones(db: Session = Depends(get_db)):
    """Histórico de predicciones, cada una con el número de su póliza."""
    predicciones = db.scalars(select(Prediccion).order_by(Prediccion.id)).all()
    return [
        {
            "id": p.id, "poliza_id": p.poliza_id, "numero": p.poliza.numero,
            "puntaje": p.puntaje, "alto_riesgo": p.alto_riesgo, "creado_en": p.creado_en,
        }
        for p in predicciones
    ]
