#!/usr/bin/env bash
# Instala el Panel Caballito y Muñequita en un servidor Ubuntu/Debian y lo publica en sofige.online
# Uso (en el servidor, como root):
#   curl -fsSL https://raw.githubusercontent.com/sofiigentaa/donweb/main/deploy.sh | bash
set -euo pipefail

DOMINIO="sofige.online"
REPO="https://github.com/sofiigentaa/donweb.git"
CARPETA="/var/www/sofige"

echo "==> Instalando programas (nginx, git, certbot)..."
apt-get update -y
apt-get install -y nginx git certbot python3-certbot-nginx

echo "==> Descargando o actualizando el panel..."
if [ -d "$CARPETA/.git" ]; then
  git -C "$CARPETA" pull --ff-only
else
  rm -rf "$CARPETA"
  git clone --depth 1 "$REPO" "$CARPETA"
fi

echo "==> Configurando el sitio web..."
cat > /etc/nginx/sites-available/sofige <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMINIO} www.${DOMINIO};
    root ${CARPETA};
    index index.html;
    location ~ /\.git { deny all; }
    location / { try_files \$uri \$uri/ /index.html; }
}
EOF
ln -sf /etc/nginx/sites-available/sofige /etc/nginx/sites-enabled/sofige
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable --now nginx
systemctl reload nginx

if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 'Nginx Full' || true
fi

echo "==> Activando el candadito de seguridad (HTTPS)..."
if certbot --nginx -d "$DOMINIO" -d "www.$DOMINIO" --non-interactive --agree-tos --register-unsafely-without-email --redirect; then
  echo "Listo: https://${DOMINIO}"
else
  echo "El sitio ya funciona en http://${DOMINIO}"
  echo "No se pudo activar HTTPS todavía: seguramente el dominio aún no apunta a este servidor."
  echo "Cuando apunte, volvé a correr este mismo comando."
fi
