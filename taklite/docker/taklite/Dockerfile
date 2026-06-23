FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates openssl python3 qrencode \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY taklite_service.py /app/taklite_service.py

EXPOSE 8080 8443 58087 8089
ENTRYPOINT ["python3", "/app/taklite_service.py"]
