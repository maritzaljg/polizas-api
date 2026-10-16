"""Lógica de negocio del servicio.

Vive aquí y no en `main.py` a propósito: las rutas se ocupan de HTTP —códigos
de estado, validación de entrada, forma de la respuesta— y el cálculo del
puntaje y del resumen de cartera se ocupa del negocio.
"""
import hashlib
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from modelos import Poliza, Siniestro


def firmar(numero: str, secreto: str) -> str:
    """Firma interna de la póliza. No se publica en ninguna respuesta."""
    return hashlib.sha256(f"{numero}:{secreto}".encode()).hexdigest()


def calcular_puntaje(poliza: Poliza, modelo) -> float:
    """Probabilidad de que la póliza resulte de alto riesgo, en [0, 1]."""
    rasgos = [[
        poliza.prima,
        len(poliza.siniestros),
        sum(s.monto for s in poliza.siniestros),
        (date.today() - poliza.fecha_inicio).days,
    ]]
    return float(modelo.predict_proba(rasgos)[0][1])


def resumen_cartera(db: Session) -> list[dict]:
    """Por cada póliza: cuántos siniestros tiene y cuánto suman.

    Estrategia `agregada` (Parte C): el resumen no necesita los siniestros, solo
    cuántos son y cuánto suman. En vez de traerlos todos a memoria para contarlos
    en Python, se le pide a la base que cuente y sume con `GROUP BY`. Una sola
    consulta devuelve una fila por póliza, sin cargar ningún siniestro.

    El `outerjoin` conserva las pólizas sin siniestros, que si no desaparecerían
    del resumen; `coalesce` deja su total en 0 en lugar de nulo.
    """
    filas = db.execute(
        select(
            Poliza.numero,
            func.count(Siniestro.id),
            func.coalesce(func.sum(Siniestro.monto), 0.0),
        )
        .outerjoin(Siniestro, Siniestro.poliza_id == Poliza.id)
        .group_by(Poliza.id)
        .order_by(Poliza.id)
    ).all()
    return [
        {"numero": numero, "n_siniestros": n, "monto_total": round(total, 2)}
        for numero, n, total in filas
    ]
