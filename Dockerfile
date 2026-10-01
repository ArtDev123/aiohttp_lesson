FROM python:3.12-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV APP_HOST=0.0.0.0
ENV APP_PORT=8080

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh /docker-entrypoint.sh

RUN apt-get update && apt-get install -y dos2unix && \
    dos2unix /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh && \
    apt-get --purge remove -y dos2unix && rm -rf /var/lib/apt/lists/*

EXPOSE 8080
ENTRYPOINT ["/docker-entrypoint.sh"]