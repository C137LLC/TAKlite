FROM node:22-bookworm-slim AS frontend

WORKDIR /frontend
COPY frontend/package.json /frontend/package.json
COPY frontend/package-lock.json /frontend/package-lock.json
COPY frontend/index.html /frontend/index.html
COPY frontend/src /frontend/src
RUN npm ci --no-audit --no-fund \
    && npm run build

FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssl python3 qrencode \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY docker/taklite/taklite_service.py /app/taklite_service.py
COPY --from=frontend /frontend/dist /app/static

EXPOSE 8080 8443 58087 8089
ENTRYPOINT ["python3", "/app/taklite_service.py"]
