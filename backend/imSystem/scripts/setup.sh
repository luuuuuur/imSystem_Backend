#!/bin/bash
set -euo pipefail

# ==DETECCION DE DISTRO==
if [ ! -f /etc/os-release ]; then
    echo "ERROR: No se puede detectar la distribución. /etc/os-release no existe."
    exit 1
fi

source /etc/os-release

detect_distro_family() {
    case "$ID" in
        ubuntu|debian)
            echo "debian"
            ;;
        rhel|centos|fedora|amzn|rocky|almalinux)
            echo "redhat"
            ;;
        *)
            case "${ID_LIKE:-}" in
                *debian*)               echo "debian"  ;;
                *rhel*|*centos*|*fedora*) echo "redhat"  ;;
                *)
                    echo "ERROR: Distribución no soportada: $ID"
                    exit 1
                    ;;
            esac
            ;;
    esac
}

DISTRO_FAMILY=$(detect_distro_family)
echo "=== Distribución detectada: $ID ($DISTRO_FAMILY) ==="

# ==USUARIO BASE SEGUN DISTRO==
case "$DISTRO_FAMILY" in
    debian)  BASE_USER="ubuntu"    ;;
    redhat)  BASE_USER="ec2-user"  ;;
esac

# ==RUTAS==
# BASE_DIR   → ~/product           (contiene env/)
# REPO_DIR   → ~/product/imSystem_Backend
# APP_DIR    → ~/product/imSystem_Backend/backend  (contiene install.txt)
# DJANGO_APP → ~/product/imSystem_Backend/backend/imSystem  (contiene manage.py y .mikufile)
BASE_DIR="/home/${BASE_USER}/product"
REPO_DIR="${BASE_DIR}/imSystem_Backend"
APP_DIR="${REPO_DIR}/backend"
DJANGO_APP="${APP_DIR}/imSystem"
INSTALL_FILE="${APP_DIR}/install.txt"
MIKUFILE="${DJANGO_APP}/.mikufile"

# ==VALIDACION DE DIRECTORIOS==
if [ ! -d "$BASE_DIR" ]; then
    echo "WARN: $BASE_DIR no existe. Creando..."
    mkdir -p "$BASE_DIR"
fi

if [ ! -d "$REPO_DIR" ]; then
    echo "ERROR: $REPO_DIR no existe. El repositorio debe estar clonado antes de ejecutar este script."
    exit 1
fi

if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: $APP_DIR no existe. Abortando."
    exit 1
fi

if [ ! -f "$INSTALL_FILE" ]; then
    echo "ERROR: $INSTALL_FILE no existe. No se pueden instalar dependencias."
    exit 1
fi

if [ ! -f "$MIKUFILE" ]; then
    echo "ERROR: $MIKUFILE no existe. Crea el archivo de variables de entorno antes de correr este script."
    exit 1
fi

# ==FUNCIONES POR FAMILIA==

setup_debian() {
    echo "=== [Debian/Ubuntu] Actualizando repositorios ==="
    sudo apt-get update

    echo "=== [Debian/Ubuntu] Configurando nginx ==="
    if [ ! -f /usr/sbin/nginx ]; then
        sudo apt-get install -y nginx
        sudo tee /etc/nginx/sites-available/ims.conf > /dev/null <<NGINX
# Rate limiting — definido fuera del bloque server
limit_req_zone \$binary_remote_addr zone=login:10m rate=5r/m;

server {
    server_name 956.duckdns.org;

    # Ocultar versión de Nginx
    server_tokens off;

    # Headers de seguridad
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    location /static/ {
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self';" always;
        alias /home/ubuntu/product/imSystem_Backend/backend/imSystem/staticfiles/;

    }
# Rate limiting solo en login

    location /ims/api/login/ {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

    }

    location / {

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    listen 443 ssl;
    http2 on; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/956.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/956.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if (\$host = 956.duckdns.org) {
        return 301 https://\$host\$request_uri;
    } # managed by Certbot


    listen 80;
    server_name 956.duckdns.org;
    return 404; # managed by Certbot


}

NGINX
        sudo ln -sf /etc/nginx/sites-available/ims.conf /etc/nginx/sites-enabled/ims.conf
        sudo rm -f /etc/nginx/sites-enabled/default
        sudo rm -f /etc/nginx/sites-available/default
    fi

    echo "=== [Debian/Ubuntu] Instalando dependencias Python ==="
    sudo apt-get install -y python3-pip python3-venv git
    echo "=== INSTALANDO CELERY==="
    sudo apt install redis -y
    sudo tee /etc/systemd/system/celery.service > /dev/null <<EOF
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
User=${BASE_USER}
WorkingDirectory=${DJANGO_APP}
ExecStart=${BASE_DIR}/env/bin/celery -A backend_config worker --loglevel=info
Restart=always

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl enable redis
    sudo systemctl start redis
    redis-cli ping
}

setup_redhat() {
    echo "=== [RedHat/Amazon Linux] Actualizando repositorios ==="
    sudo dnf update -y 2>/dev/null || sudo yum update -y

    echo "=== [RedHat/Amazon Linux] Configurando nginx ==="
    if [ ! -f /usr/sbin/nginx ]; then
        sudo dnf install -y nginx 2>/dev/null || sudo yum install -y nginx
        sudo tee /etc/nginx/conf.d/ims.conf > /dev/null <<NGINX
# Rate limiting — definido fuera del bloque server
limit_req_zone \$binary_remote_addr zone=login:10m rate=5r/m;

server {
    server_name 956.duckdns.org;

    # Ocultar versión de Nginx
    server_tokens off;

    # Headers de seguridad
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    location /static/ {
        add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self';" always;
        alias /home/ubuntu/product/imSystem_Backend/backend/imSystem/staticfiles/;

    }
# Rate limiting solo en login

    location /ims/api/login/ {
        limit_req zone=login burst=3 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;

        proxy_set_header X-Forwarded-Proto \$scheme;

    }

    location / {

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    listen 443 ssl;
    http2 on; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/956.duckdns.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/956.duckdns.org/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}
server {
    if (\$host = 956.duckdns.org) {
        return 301 https://\$host\$request_uri;
    } # managed by Certbot


    listen 80;
    server_name 956.duckdns.org;
    return 404; # managed by Certbot


}

NGINX
        if command -v setsebool &>/dev/null; then
            echo "=== Habilitando SELinux boolean para nginx proxy ==="
            sudo setsebool -P httpd_can_network_connect 1
        fi
    fi

    echo "=== [RedHat/Amazon Linux] Instalando dependencias Python ==="
    sudo dnf install -y python3 python3-pip git 2>/dev/null || \
    sudo yum install -y python3 python3-pip git
    echo "===INSTALANDO CELERY==="
    sudo dnf install redis -y
    sudo tee /etc/systemd/system/celery.service > /dev/null<<EOF
[Unit]
Description=Celery Worker
After=network.target redis.service

[Service]
User=${BASE_USER}
WorkingDirectory=${DJANGO_APP}
ExecStart=${BASE_DIR}/env/bin/celery -A backend_config worker --loglevel=info
Restart=always
 
[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl enable redis
    sudo systemctl start redis
    redis-cli ping
}   

# ==DISPATCH==
case "$DISTRO_FAMILY" in
    debian)  setup_debian  ;;
    redhat)  setup_redhat  ;;
esac

# ==NGINX ARRANQUE==
cp ~/product/imSystem_Backend/backend/ims_test_client.html ~/product/imSystem_Backend/backend/imSystem/staticfiles/
chmod o+r ~/product/imSystem_Backend/backend/imSystem/staticfiles/ims_test_client.html
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable nginx
sudo systemctl start nginx || sudo systemctl restart nginx
echo "=== Nginx status ==="
sudo systemctl is-active nginx && echo "nginx: activo" || echo "WARN: nginx no está activo"

# ==PERMISOS STATIC FILES==
chmod o+x /home/${BASE_USER}
chmod o+x /home/${BASE_USER}/product
chmod o+x /home/${BASE_USER}/product/imSystem_Backend
chmod o+x /home/${BASE_USER}/product/imSystem_Backend/backend
chmod o+x /home/${BASE_USER}/product/imSystem_Backend/backend/imSystem
chmod o+x /home/${BASE_USER}/product/imSystem_Backend/backend/imSystem/staticfiles 2>/dev/null || true

# ==ENTORNO VIRTUAL Y DEPENDENCIAS==
echo "=== Configurando entorno virtual Python ==="
cd "$BASE_DIR"

if [ ! -d "${BASE_DIR}/env" ]; then
    python3 -m venv env
fi

echo "=== Instalando dependencias ==="
"${BASE_DIR}/env/bin/pip" install -r "$INSTALL_FILE"
"${BASE_DIR}/env/bin/pip" install "${APP_DIR}"/wheels/rustjson-*.whl
echo "=== Generando archivos estáticos ==="
"${BASE_DIR}/env/bin/python" "${DJANGO_APP}/manage.py" collectstatic --noinput

chmod -R o+r "${DJANGO_APP}/staticfiles"

# ==ENVIRONMENT FILE==
sudo mkdir -p /etc/gunicorn
sudo cp "$MIKUFILE" /etc/gunicorn/ims.env
sudo chown root:root /etc/gunicorn/ims.env
sudo chmod 640 /etc/gunicorn/ims.env

# ==GUNICORN SERVICE==
if [ ! -f /etc/systemd/system/gunicorn.service ]; then
    echo "=== Configurando gunicorn.service ==="
    sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<SYSTEMD
[Unit]
Description=Gunicorn IMS
After=network.target

[Service]
User=${BASE_USER}
WorkingDirectory=${DJANGO_APP}
ExecStart=${BASE_DIR}/env/bin/gunicorn \\
    backend_config.wsgi:application \\
    --bind 127.0.0.1:8000 \\
    --workers 3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SYSTEMD
fi

echo "=== Iniciando gunicorn ==="
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn || sudo systemctl restart gunicorn
echo "===STATUS CELERY==="
sudo systemctl enable celery
sudo systemctl start celery
sudo systemctl is-active celery && echo "celery: activo" || echo "WARN: celery no está activo"
echo "=== Gunicorn status ==="
sudo systemctl is-active gunicorn && echo "gunicorn: activo" || echo "WARN: gunicorn no está activo"
echo "=== Deploy finalizado en $ID ($DISTRO_FAMILY) como usuario $BASE_USER ==="
