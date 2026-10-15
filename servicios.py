"""Lógica de negocio del servicio.

Vive aquí y no en `main.py` a propósito: las rutas se ocupan de HTTP —códigos
de estado, validación de entrada, forma de la respuesta— y el cálculo del
puntaje y del resumen de cartera se ocupa del negocio.
"""
import hashlib
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from modelos import Poliza


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
    """Por cada póliza: cuántos siniestros tiene y cuánto suman."""
    polizas = db.scalars(select(Poliza).order_by(Poliza.id)).all()
    return [
        {
            "numero": p.numero,
            "n_siniestros": len(p.siniestros),
            "monto_total": round(sum(s.monto for s in p.siniestros), 2),
        }
        for p in polizas
    ]
