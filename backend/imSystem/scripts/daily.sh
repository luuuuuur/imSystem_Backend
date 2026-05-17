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

# ==RUTAS==
BASE_DIR="/home/${BASE_USER}/product"
REPO_DIR="/home/${BASE_USER}/product/imSystem_Backend"
APP_DIR="${BASE_DIR}"
DJANGO_APP="${BASE_DIR}/imSystem"
INSTALL_FILE="${BASE_DIR}/install.txt"
PIP="${BASE_DIR}/env/bin/pip"
PYTHON="${BASE_DIR}/env/bin/python3"

# ==VALIDACIONES PREVIAS==
for path in "$BASE_DIR" "$REPO_DIR" "$APP_DIR" "$DJANGO_APP" "$INSTALL_FILE" "${DJANGO_APP}/manage.py"; do
    if [ ! -e "$path" ]; then
        echo "ERROR: $path no existe. Abortando."
        exit 1
    fi
done

echo "=== [$(date)] INICIANDO DAILY === (distro: $ID, usuario: $BASE_USER)"

echo "=== ACTUALIZANDO DEPENDENCIAS ==="
"$PIP" install -r "$INSTALL_FILE" --quiet

echo "=== APLICANDO MIGRACIONES ==="
"$PYTHON" "${DJANGO_APP}/manage.py" makemigrations --noinput
"$PYTHON" "${DJANGO_APP}/manage.py" migrate --noinput

echo "=== REINICIANDO GUNICORN Y NGINX ==="
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl restart gunicorn

echo "=== STATUS ==="
sudo systemctl is-active nginx    && echo "nginx:    activo" || echo "ERROR: nginx no está activo"
sudo systemctl is-active gunicorn && echo "gunicorn: activo" || echo "ERROR: gunicorn no está activo"
