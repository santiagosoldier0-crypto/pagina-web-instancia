#!/usr/bin/env bash
# Ejecutar en una instancia dedicada Ubuntu 22.04/24.04 o Amazon Linux 2023.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'Ejecuta: sudo bash deploy/setup.sh'
  exit 1
fi
SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR=/opt/panaderia
if [[ "$SOURCE_DIR" == "$APP_DIR" ]]; then
  echo 'Ejecuta este instalador desde el repositorio clonado en tu carpeta personal.'
  exit 1
fi
if command -v apt-get >/dev/null; then
  apt-get update
  apt-get install -y python3 python3-venv python3-pip nginx curl
elif command -v dnf >/dev/null; then
  dnf install -y python3 python3-pip nginx curl-minimal
else
  echo 'Sistema no compatible. Usa Ubuntu 22.04/24.04 o Amazon Linux 2023.'
  exit 1
fi
id panaderia &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin panaderia
install -d -m 755 "$APP_DIR" "$APP_DIR/instance"
# Copia solo código; conserva la base de datos entre actualizaciones.
cp "$SOURCE_DIR/app.py" "$SOURCE_DIR/wsgi.py" "$SOURCE_DIR/requirements.txt" "$APP_DIR/"
cp -R "$SOURCE_DIR/static" "$SOURCE_DIR/templates" "$APP_DIR/"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
chown -R panaderia:panaderia "$APP_DIR"
cat > /etc/systemd/system/panaderia.service <<'SERVICE'
[Unit]
Description=Horno y Miga - Flask y Gunicorn
After=network.target

[Service]
User=panaderia
Group=panaderia
WorkingDirectory=/opt/panaderia
Environment=DATABASE_PATH=/opt/panaderia/instance/panaderia.sqlite3
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/panaderia/.venv/bin/gunicorn --workers 2 --bind 127.0.0.1:8000 --access-logfile - --error-logfile - wsgi:app
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/panaderia/instance
UMask=0077

[Install]
WantedBy=multi-user.target
SERVICE
# Servidor dedicado: el bloque default de la distribución puede permanecer.
# El nombre regex captura IP/dominio aunque exista el default de Amazon Linux.
cat > /etc/nginx/conf.d/panaderia.conf <<'NGINX'
server {
    listen 0.0.0.0:80;
    server_name ~^.*$;
    client_max_body_size 32k;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
NGINX
# Ubuntu incluye un sitio por defecto; deshabilitar solo su enlace de fábrica.
if [[ -L /etc/nginx/sites-enabled/default ]]; then
  unlink /etc/nginx/sites-enabled/default
fi
if command -v getenforce >/dev/null && [[ "$(getenforce)" != Disabled ]]; then
  setsebool -P httpd_can_network_connect 1
fi
systemctl daemon-reload
systemctl enable --now panaderia
systemctl restart panaderia
nginx -t
systemctl enable --now nginx
systemctl reload nginx
for attempt in {1..15}; do
  if curl --fail --silent http://127.0.0.1:8000/api/health; then
    echo
    echo 'Aplicación lista. Abre http://IP_PUBLICA de tu instancia.'
    exit 0
  fi
  sleep 1
done
journalctl -u panaderia -n 30 --no-pager
exit 1
