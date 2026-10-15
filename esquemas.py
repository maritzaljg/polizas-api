"""Esquemas de entrada y de salida (B6, B7).

Entrada: qué acepta el servicio y con qué restricciones.
Salida: qué devuelve. Están separados a propósito, porque hay campos que se
guardan pero no se publican, como `token_firma`.
"""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Entrada ---------------------------------------------------------------

class SiniestroEntrada(BaseModel):
    """Un siniestro declarado sobre una póliza."""

    fecha: date
    monto: float = Field(gt=0, description="Monto reclamado, en pesos")
    descripcion: str = Field(min_length=3, max_length=200)
    estado: str = "abierto"


class PolizaEntrada(BaseModel):
    """Datos para crear una póliza, con los siniestros que ya tenga."""

    numero: str = Field(min_length=8, max_length=20, description="Formato POL-AAAA-NNNNN")
    asegurado: str = Field(min_length=3, max_length=80)
    tipo: str = Field(description="auto, hogar o vida")
    prima: float = Field(gt=0, description="Prima anual, en pesos")
    fecha_inicio: date
    fecha_fin: date
    # Tipada como lista de SiniestroEntrada, no como list[dict]: así las
    # restricciones de cada siniestro anidado sí se aplican (B7).
    siniestros: list[SiniestroEntrada] = Field(default_factory=list)

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: str) -> str:
        """Quita espacios sobrantes y pone el nombre con mayúscula inicial.

        El valor final del campo es lo que retorna el validador: sin `return`
        el campo quedaba nulo.
        """
        return " ".join(v.split()).title()

    @model_validator(mode="after")
    def vigencia_coherente(self):
        """La vigencia no puede terminar antes de empezar (B7)."""
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("fecha_fin debe ser posterior a fecha_inicio")
        return self


class PolizaActualizacion(BaseModel):
    """Actualización parcial: solo viaja lo que se quiere cambiar."""

    asegurado: Optional[str] = Field(default=None, min_length=3, max_length=80)
    tipo: Optional[str] = None
    prima: Optional[float] = Field(default=None, gt=0)
    fecha_fin: Optional[date] = None

    @field_validator("asegurado")
    @classmethod
    def normalizar_asegurado(cls, v: Optional[str]) -> Optional[str]:
        return " ".join(v.split()).title() if v is not None else v


class PuntuacionEntrada(BaseModel):
    numero: str = Field(min_length=8, max_length=20)


# --- Salida ----------------------------------------------------------------

class SiniestroSalida(BaseModel):
    """Siniestro tal como se publica dentro de una póliza."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    fecha: date
    monto: float
    descripcion: str
    estado: str


class PolizaSalida(BaseModel):
    """Póliza publicada. No incluye `token_firma`, que es un campo interno."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: str
    asegurado: Optional[str] = None
    tipo: Optional[str] = None
    prima: float
    fecha_inicio: date
    fecha_fin: Optional[date] = None
    siniestros: list[SiniestroSalida] = Field(default_factory=list)


class SiniestroConPoliza(BaseModel):
    """Siniestro publicado junto al número de su póliza."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int
    numero_poliza: str
    fecha: date
    monto: float
    descripcion: str
    estado: str


class ResumenSalida(BaseModel):
    """Una fila del resumen de cartera."""

    numero: str
    n_siniestros: int
    monto_total: float


class PuntuacionSalida(BaseModel):
    numero: str
    puntaje: float = Field(ge=0.0, le=1.0)
    alto_riesgo: bool


class PrediccionSalida(BaseModel):
    """Predicción registrada, con el número de la póliza a la que pertenece."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    poliza_id: int
    numero: str
    puntaje: float
    alto_riesgo: bool
    creado_en: datetime


class SaludSalida(BaseModel):
    estado: str
    base_de_datos: str
