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
BASE_DIR="/home/${BASE_USER}/product"
REPO_DIR="${BASE_DIR}/imSystem_Backend"
APP_DIR="${REPO_DIR}/backend"
DJANGO_APP="${APP_DIR}/imSystem"
INSTALL_FILE="${APP_DIR}/install.txt"
PIP="${BASE_DIR}/env/bin/pip"

echo "=== [$(date)] INICIANDO DAILY CELERY ==="

echo "=== ACTUALIZANDO REPO ==="
cd "$REPO_DIR"
git pull origin main

echo "=== ACTUALIZANDO DEPENDENCIAS ==="
"$PIP" install -r "$INSTALL_FILE" --quiet
"$PIP" install psycogreen --quiet

echo "=== REINICIANDO CELERY ==="
sudo systemctl daemon-reload
sudo systemctl restart celery

echo "=== STATUS ==="
sudo systemctl is-active celery && echo "celery: activo" || echo "ERROR: celery no está activo"