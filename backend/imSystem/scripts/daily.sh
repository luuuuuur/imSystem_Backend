#!/bin/bash
set -euo pipefail

# ==DETECCION DE USUARIO BASE==
if [ ! -f /etc/os-release ]; then
    echo "ERROR: No se puede detectar la distribución. /etc/os-release no existe."
    exit 1
fi

source /etc/os-release

case "$ID" in
    ubuntu|debian)
        BASE_USER="ubuntu"
        ;;
    rhel|centos|fedora|amzn|rocky|almalinux)
        BASE_USER="ec2-user"
        ;;
    *)
        case "${ID_LIKE:-}" in
            *debian*)               BASE_USER="ubuntu"   ;;
            *rhel*|*centos*|*fedora*) BASE_USER="ec2-user" ;;
            *)
                echo "ERROR: Distribución no soportada: $ID"
                exit 1
                ;;
        esac
        ;;
esac

BASE_DIR="/home/${BASE_USER}/product/imSystem_Backend/backend"
APP_DIR="${BASE_DIR}/imSystem"
PIP="/home/${BASE_USER}/product/env/bin/pip"
PYTHON="/home/${BASE_USER}/product/env/bin/python3"

# ==VALIDACIONES PREVIAS==
for path in "$BASE_DIR" "$APP_DIR" "${BASE_DIR}/install.txt" "${APP_DIR}/manage.py"; do
    if [ ! -e "$path" ]; then
        echo "ERROR: $path no existe. Abortando."
        exit 1
    fi
done

echo "=== [$(date)] INICIANDO DAILY === (distro: $ID, usuario: $BASE_USER)"

echo "=== ACTUALIZANDO DEPENDENCIAS ==="
"$PIP" install -r "${BASE_DIR}/install.txt" --quiet

echo "=== APLICANDO MIGRACIONES ==="
"$PYTHON" "${APP_DIR}/manage.py" makemigrations --noinput
"$PYTHON" "${APP_DIR}/manage.py" migrate --noinput

echo "=== REINICIANDO GUNICORN Y NGINX ==="
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl restart gunicorn

echo "=== STATUS ==="
sudo systemctl is-active nginx    && echo "nginx:    activo" || echo "ERROR: nginx no está activo"
sudo systemctl is-active gunicorn &