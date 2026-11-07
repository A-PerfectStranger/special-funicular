# syntax=docker/dockerfile:1
FROM python:3.12.14-slim-bookworm@sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    PIP_CERT=$(if [ -f /run/secrets/proxy_ca ]; then echo /run/secrets/proxy_ca; else echo /etc/ssl/certs/ca-certificates.crt; fi) \
    pip install --no-cache-dir --require-hashes -r requirements.txt \
    && useradd --no-create-home --uid 10001 app
COPY --chown=10001:10001 apps/backend/ /app/
ARG RELEASE_SHA
LABEL org.opencontainers.image.revision=$RELEASE_SHA
ENV RELEASE_SHA=$RELEASE_SHA
USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--error-logfile", "-"]
