# Dockerfile optimizado para FastAPI VoIP Backend
# Etapa 1: Construcción y descarga de dependencias
FROM python:3.11-slim AS builder

WORKDIR /app

# Instalar herramientas básicas de compilación (si se necesitan para empaquetar)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Crear entorno virtual interno
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Instalar dependencias del archivo requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Etapa 2: Imagen de ejecución (ligera y segura)
FROM python:3.11-slim AS runner

WORKDIR /app

# Copiar el entorno virtual completo desde la etapa anterior
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copiar únicamente los archivos necesarios del proyecto
COPY main.py .
COPY index.html .

# Crear un usuario no privilegiado por seguridad (evitar ejecutar como root)
RUN useradd -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

# Exponer el puerto donde corre la aplicación
EXPOSE 8000

# Comando de inicio del servidor Uvicorn en modo producción
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
