# Imagen del servicio de pólizas (B9).
#
# Construcción en dos etapas: la primera instala las dependencias, la segunda se
# queda solo con el resultado. Así la imagen final no arrastra las herramientas
# de compilación ni la caché de pip.
#
#   docker build -t polizas-api .
#   docker run -p 8000:8000 polizas-api

# --- Etapa 1: se instalan las dependencias ---------------------------------
# La base va fijada a una versión exacta. Con `python:latest` la imagen cambiaría
# sola de un día para otro y dejaría de ser reproducible.
FROM python:3.11.9-slim-bookworm AS dependencias

WORKDIR /app

# Solo se copia requirements.txt: así, mientras no cambien las dependencias,
# Docker reutiliza esta capa y no vuelve a instalarlas en cada construcción.
COPY requirements.txt .
RUN python -m venv /opt/entorno \
    && /opt/entorno/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/entorno/bin/pip install --no-cache-dir -r requirements.txt

# --- Etapa 2: la imagen que se publica -------------------------------------
FROM python:3.11.9-slim-bookworm

# curl es lo único que se añade al sistema, y es para el HEALTHCHECK de abajo.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Un usuario sin privilegios: si alguien entra por una vulnerabilidad del
# servicio, no entra como administrador de la máquina (B9).
RUN useradd --create-home --uid 1000 servicio

WORKDIR /app

# Se trae el entorno ya instalado de la etapa anterior y se pone por delante en
# el PATH, de modo que `python`, `uvicorn` y `alembic` sean los de ese entorno.
COPY --from=dependencias /opt/entorno /opt/entorno
ENV PATH="/opt/entorno/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Valores de configuración por defecto, para que `docker run -p 8000:8000`
# levante sin más. NO son secretos reales: en un despliegue de verdad se
# sustituyen al arrancar, con `docker run -e SECRETO_FIRMA=...`.
ENV SECRETO_FIRMA="cambiar-esta-firma-en-produccion" \
    CLAVE_API_REASEGURO="cambiar-esta-clave-en-produccion" \
    DATABASE_URL="sqlite:////app/datos/polizas.db"

# El código, con el usuario sin privilegios como dueño.
COPY --chown=servicio:servicio . .

# Carpeta para la base de datos. La imagen no lleva ninguna base dentro: el
# esquema lo crea la migración al arrancar el contenedor.
RUN mkdir -p /app/datos && chown servicio:servicio /app/datos

USER servicio

EXPOSE 8000

# Docker consulta /health cada 30 segundos y marca el contenedor como enfermo si
# deja de responder tres veces seguidas. Es la ruta que pide la regla B10.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Primero se aplica la migración, que crea el esquema sobre la base vacía, y
# después arranca el servicio.
#   · sin --reload, que es de desarrollo
#   · con --host 0.0.0.0, para que responda desde fuera del contenedor y no
#     solo desde dentro, que es lo que hacía 127.0.0.1
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
