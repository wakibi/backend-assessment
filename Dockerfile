FROM python:3.13-slim AS builder

ENV PYTHONUNBUFFERED=1
ENV POETRY_VERSION=2.1.1
ENV POETRY_HOME="/opt/poetry"
ENV VIRTUAL_ENV="/opt/pysetup/venv"

RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN apt-get update && apt-get install -y curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

ENV PATH="$POETRY_HOME/bin:$PATH"

COPY pyproject.toml poetry.lock ./
RUN poetry install --without dev --no-root


WORKDIR /code

RUN poetry install --only dev --no-root
COPY ./ /code/
CMD ["/bin/bash", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
