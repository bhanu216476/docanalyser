# ==============================================================================
# DocAnalyser Python RAG Service - Production Dockerfile
# ==============================================================================

FROM python:3.12-slim

# Prevent python from writing pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Create non-root application user
RUN useradd -m -u 1000 appuser

# Install build dependencies if needed and Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=appuser:appuser . .

USER appuser

# Expose FastAPI port
EXPOSE 8000

# Healthcheck using Python standard library (no external curl/wget required)
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=15s \
  CMD python -c "import urllib.request; res = urllib.request.urlopen('http://localhost:8000/health'); exit(0 if res.status == 200 else 1)" || exit 1

# Start FastAPI server using Uvicorn bound to 0.0.0.0
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
