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
            # Fallback via ID_LIKE
            case "${ID_LIKE:-}" in
                *debian*)  echo "debian"  ;;
                *rhel*|*centos*|*fedora*)  echo "redhat"  ;;
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

BASE_DIR="/home/${BASE_USER}/backend"
APP_DIR="${BASE_DIR}/imSystem"

# ==VALIDACION DE DIRECTORIOS==
if [ ! -d "$BASE_DIR" ]; then
    echo "WARN: $BASE_DIR no existe. Creando..."
    mkdir "$BASE_DIR"
fi

if [ ! -d "$APP_DIR" ]; then
    echo "ERROR: $APP_DIR no existe. El repositorio debe estar clonado antes de ejecutar este script."
    exit 1
fi

if [ ! -f "${BASE_DIR}/install.txt" ]; then
    echo "ERROR: ${BASE_DIR}/install.txt no existe. No se pueden instalar dependencias."
    exit 1
fi

# ==FUNCIONES POR FAMILIA==

setup_debian() {
    echo "=== [Debian/Ubuntu] Actualizando repositorios ==="
    sudo apt-get update 

    echo "=== [Debian/Ubuntu] Configurando nginx ==="
    if [ ! -f /usr/sbin/nginx ]; then
        sudo apt-get install -y nginx

        echo "Ingresa la IP o DNS del servidor:"
        read -r SERVER_IP

        sudo tee /etc/nginx/sites-available/ims.conf > /dev/null <<EOF
server {
    listen 80;
    server_name ${SERVER_IP};
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
        sudo ln -sf /etc/nginx/sites-available/ims.conf /etc/nginx/sites-enabled/ims.conf
        sudo rm -f /etc/nginx/sites-enabled/default
        sudo rm -f /etc/nginx/sites-available/default
    fi

    echo "=== [Debian/Ubuntu] Instalando dependencias Python ==="
    sudo apt-get install -y python3-pip python3-venv git
}

setup_redhat() {
    echo "=== [RedHat/Amazon Linux] Actualizando repositorios ==="
    sudo dnf update -y 2>/dev/null || sudo yum update -y

    echo "=== [RedHat/Amazon Linux] Configurando nginx ==="
    if [ ! -f /usr/sbin/nginx ]; then
        sudo dnf install -y nginx 2>/dev/null || sudo yum install -y nginx

        echo "Ingresa la IP o DNS del servidor:"
        read -r SERVER_IP

        sudo tee /etc/nginx/conf.d/ims.conf > /dev/null <<EOF
server {
    listen 80;
    server_name ${SERVER_IP};
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
        # SELinux: necesario para que nginx pueda hacer proxy a procesos locales
        if command -v setsebool &>/dev/null; then
            echo "=== Habilitando SELinux boolean para nginx proxy ==="
            sudo setsebool -P httpd_can_network_connect 1
        fi
    fi

    echo "=== [RedHat/Amazon Linux] Instalando dependencias Python ==="
    sudo dnf install -y python3 python3-pip git 2>/dev/null || \
        sudo yum install -y python3 python3-pip git
}

# ==DISPATCH==
case "$DISTRO_FAMILY" in
    debian)  setup_debian  ;;
    redhat)  setup_redhat  ;;
esac

# ==NGINX ARRANQUE (común)==
sudo nginx -t
sudo systemctl daemon-reload
sudo systemctl enable nginx
sudo systemctl start nginx || sudo systemctl restart nginx
echo "=== Nginx status ==="
sudo systemctl is-active nginx && echo "nginx: activo" || echo "WARN: nginx no está activo"

# ==ENTORNO VIRTUAL Y DEPENDENCIAS==
echo "=== Configurando entorno virtual Python ==="
cd "$BASE_DIR"

if [ ! -d "${BASE_DIR}/env" ]; then
    python3 -m venv env
fi

echo "=== Instalando dependencias desde install.txt ==="
"${BASE_DIR}/env/bin/pip" install -r "${BASE_DIR}/install.txt"
# ==ENVIRONMENT FILE==
if [ ! -f "${APP_DIR}/.mikufile" ]; then
    echo "ERROR: ${APP_DIR}/.mikufile no existe. Crea el archivo de variables de entorno antes de correr este script."
    exit 1
fi

sudo mkdir -p /etc/gunicorn
sudo cp "${APP_DIR}/.mikufile" /etc/gunicorn/ims.env
sudo chown root:root /etc/gunicorn/ims.env
sudo chmod 640 /etc/gunicorn/ims.env
# ==GUNICORN SERVICE==
if [ ! -f /etc/systemd/system/gunicorn.service ]; then
    echo "=== Configurando gunicorn.service ==="
    sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<EOF
[Unit]
Description=Gunicorn IMS
After=network.target

[Service]
User=${BASE_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=/etc/gunicorn/ims.env
ExecStart=${BASE_DIR}/env/bin/gunicorn \\
    backend_config.wsgi:application \\
    --bind 127.0.0.1:8000 \\
    --workers 3
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
fi

echo "=== Iniciando gunicorn ==="
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn || sudo systemctl restart gunicorn

echo "=== Gunicorn status ==="
sudo systemctl is-active gunicorn && echo "gunicorn: activo" || echo "WARN: gunicorn no está activo"

echo "=== Deploy finalizado en $ID ($DISTRO_FAMILY) como usuario $BASE_USER ==="