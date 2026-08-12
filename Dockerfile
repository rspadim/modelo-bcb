# Modelo BCB — réplica do MPP
FROM python:3.12-slim

WORKDIR /app

# compilador C (g++) para o PyTensor/PyMC (NUTS em C) e utilitários
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ && rm -rf /var/lib/apt/lists/*

# dependências primeiro (camada de cache no build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código
COPY . .

# pipeline e dashboard
ENTRYPOINT ["bash", "entrypoint.sh"]
