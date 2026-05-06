FROM python:3.11-slim-bookworm

# System deps: node for Rivet workflows, plus libs for matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    nodejs npm \
    ca-certificates \
    libfreetype6 \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Node deps (Rivet runner)
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Install Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Ensure runtime-writable outputs dir exists
RUN mkdir -p outputs

ENV PYTHONUNBUFFERED=1

# Render (and most hosts) set PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn api_server:app --host 0.0.0.0 --port ${PORT:-8000}"]
