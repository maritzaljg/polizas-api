"""Conexión a la base de datos y sesión por petición (B3, B4)."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import obtener_settings


class Base(DeclarativeBase):
    pass


settings = obtener_settings()

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False)


@event.listens_for(engine, "connect")
def _activar_claves_foraneas(conexion, _registro):
    """SQLite ignora las claves foráneas salvo que se pidan en cada conexión (B4).

    Sin esto se pueden insertar siniestros que apuntan a pólizas inexistentes:
    la fila queda huérfana y la base no se queja.
    """
    cursor = conexion.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Session:
    """Entrega una sesión por petición y la cierra al terminar (B3).

    Antes había una única sesión de módulo compartida por todo el servicio: si
    una petición la dejaba en estado de error, las siguientes fallaban también.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
