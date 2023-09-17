FROM python:3.11-slim

ARG API_URL
ARG HOSTNAME_OVERRIDE
ARG LOGURU_LEVEL=INFO
ENV API_URL=${API_URL}
ENV HOSTNAME_OVERRIDE=${HOSTNAME_OVERRIDE}
ENV LOGURU_LEVEL=${LOGURU_LEVEL}

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        mkvtoolnix \
        ffmpeg \
        handbrake-cli

RUN pip install poetry

WORKDIR /app

COPY client.py pyproject.toml /app/
COPY app app
COPY modules modules

RUN poetry install

ENTRYPOINT ["poetry", "run", "python", "client.py"]
