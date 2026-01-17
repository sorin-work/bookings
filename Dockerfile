# Build stage: install dependencies into a virtualenv and collect static files.
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
RUN python -m venv /venv
COPY requirements.txt ./
RUN /venv/bin/pip install -r requirements.txt
COPY . .
RUN /venv/bin/python manage.py collectstatic --noinput

# Runtime stage: just the virtualenv, the code and the collected static files.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app
RUN useradd --system --no-create-home --shell /usr/sbin/nologin app
COPY --from=build /venv /venv
COPY --from=build /app /app
USER app

EXPOSE 8000
CMD ["gunicorn", "config.wsgi", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
