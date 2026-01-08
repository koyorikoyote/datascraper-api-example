FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy worker requirements first for better caching
COPY worker/requirements.txt /app/worker/
RUN pip install --no-cache-dir -r worker/requirements.txt

# Copy main requirements for shared dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY worker/ /app/worker/
COPY alembic.ini /app/
COPY alembic/ /app/alembic/

# Make the main script executable
RUN chmod +x /app/worker/main.py

# Set Python path
ENV PYTHONPATH=/app:$PYTHONPATH
ENV PYTHONUNBUFFERED=1

# Run the worker
CMD ["python", "/app/worker/main.py"]