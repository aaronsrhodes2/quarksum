#!/bin/bash
set -euxo pipefail
exec > >(tee /var/log/startup-script.log) 2>&1

export DEBIAN_FRONTEND=noninteractive

# --- Install packages ---
apt-get update -y
apt-get install -y docker.io docker-compose nginx openssl

systemctl enable --now docker

# --- Create working directory ---
mkdir -p /opt/artifactory
cd /opt/artifactory

# --- Docker Compose: Artifactory + PostgreSQL ---
cat > docker-compose.yml <<'EOF'
version: "3.8"
services:
  postgres:
    image: postgres:15
    container_name: artifactory-postgres
    restart: always
    environment:
      POSTGRES_DB: artifactory
      POSTGRES_USER: artifactory
      POSTGRES_PASSWORD: Art1fact0ry!
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U artifactory"]
      interval: 10s
      timeout: 5s
      retries: 5

  artifactory:
    image: releases-docker.jfrog.io/jfrog/artifactory-oss:latest
    container_name: artifactory
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "8081:8081"
      - "8082:8082"
    environment:
      EXTRA_JAVA_OPTIONS: "-Xmx6g -Xms4g"
      JF_SHARED_DATABASE_TYPE: postgresql
      JF_SHARED_DATABASE_DRIVER: org.postgresql.Driver
      JF_SHARED_DATABASE_URL: jdbc:postgresql://postgres:5432/artifactory
      JF_SHARED_DATABASE_USERNAME: artifactory
      JF_SHARED_DATABASE_PASSWORD: Art1fact0ry!
    volumes:
      - artifactory_data:/var/opt/jfrog/artifactory
    ulimits:
      nproc: 65535
      nofile:
        soft: 32000
        hard: 40000

volumes:
  pgdata:
  artifactory_data:
EOF

# --- Pull images then start ---
docker-compose pull
docker-compose up -d

# --- Configure nginx with self-signed TLS proxying to 8081 ---
mkdir -p /etc/nginx/ssl
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout /etc/nginx/ssl/artifactory.key \
  -out /etc/nginx/ssl/artifactory.crt \
  -subj "/CN=artifactory/O=JFrog/C=US"

cat > /etc/nginx/sites-available/artifactory <<'NGINX'
ssl_certificate /etc/nginx/ssl/artifactory.crt;
ssl_certificate_key /etc/nginx/ssl/artifactory.key;

upstream artifactory_backend {
    server 127.0.0.1:8081;
    keepalive 32;
}

server {
    listen 80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;

    client_max_body_size 0;
    proxy_read_timeout 2400s;
    proxy_pass_header Server;

    location / {
        proxy_pass          http://artifactory_backend/artifactory/;
        proxy_set_header    Host              $http_host;
        proxy_set_header    X-Real-IP         $remote_addr;
        proxy_set_header    X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header    X-Forwarded-Proto $scheme;
        proxy_set_header    X-JFrog-Override-Base-Url https://$http_host;
        proxy_http_version  1.1;
        proxy_set_header    Connection "";
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/artifactory /etc/nginx/sites-enabled/artifactory
nginx -t && systemctl restart nginx

echo "=== STARTUP SCRIPT COMPLETE. Waiting for Artifactory on port 8081... ==="
for i in $(seq 1 60); do
  STATUS=$(curl -sf http://localhost:8081/artifactory/api/system/ping 2>/dev/null || echo "NOT_READY")
  echo "Health check $i/60: $STATUS"
  if [ "$STATUS" = "OK" ]; then
    echo "=== ARTIFACTORY IS HEALTHY ==="
    exit 0
  fi
  sleep 10
done

echo "=== Artifactory did not respond healthy in 10 minutes ==="
docker logs --tail 80 artifactory 2>&1 || true
echo "=== POSTGRES LOGS ==="
docker logs --tail 20 artifactory-postgres 2>&1 || true
