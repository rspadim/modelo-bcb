# Modelo BCB — réplica do MPP
FROM python:3.12-slim

WORKDIR /app

# dependências primeiro (camada de cache no build)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código
COPY . .

# pipeline e dashboard
ENTRYPOINT ["bash", "entrypoint.sh"]
