# Custos Energy — TOU tariff publisher
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY custos_energy/ ./custos_energy/

# Timezone MUST match your billing locale (tariffs are wall-clock).
ENV TZ=America/Los_Angeles

CMD ["python", "-m", "custos_energy.publisher"]
