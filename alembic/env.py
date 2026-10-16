"""Entorno de Alembic (B5).

La dirección de la base no se escribe en `alembic.ini`: se toma de la variable
`DATABASE_URL`, que es la misma que honra la aplicación. Así `alembic upgrade
head` y el servicio apuntan siempre a la misma base, sin configurarlo dos veces.

Se consulta primero el entorno y, si no está, la configuración del servicio.
De ese modo aplicar una migración no exige tener cargados los secretos: para
crear tablas basta con saber dónde está la base.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Base  # noqa: E402
import modelos  # noqa: E402,F401  (al importarse, registra las tablas en Base)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def url_de_la_base() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    from config import obtener_settings
    return obtener_settings().DATABASE_URL


config.set_main_option("sqlalchemy.url", url_de_la_base())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # SQLite no sabe alterar columnas: `render_as_batch` hace que
            # Alembic recree la tabla cuando una migración futura lo necesite.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
