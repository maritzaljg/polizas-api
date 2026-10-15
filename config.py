"""Configuración del servicio, leída del entorno (B1, B2).

Los valores sensibles ya no viven en el código: se leen de variables de entorno
o del archivo `.env`, que no se versiona. `.env.example` documenta cuáles hacen
falta y con qué valores arranca el servicio.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración completa del servicio."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Secretos: sin valor por defecto a propósito, para que falte explícitamente
    # si alguien despliega sin configurarlos.
    SECRETO_FIRMA: str
    CLAVE_API_REASEGURO: str

    # La ruta de la base se honra desde la variable DATABASE_URL (B2).
    DATABASE_URL: str = "sqlite:///app.db"

    RUTA_MODELO: str = "modelo.pkl"
    UMBRAL_ALTO_RIESGO: float = 0.6


@lru_cache
def obtener_settings() -> Settings:
    """Devuelve la configuración una sola vez.

    `lru_cache` evita releer el archivo `.env` en cada petición, y permite
    inyectar esta función con `Depends` allí donde haga falta la configuración.
    """
    return Settings()
