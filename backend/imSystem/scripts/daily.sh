#!/bin/bash
set -e

echo "=== [$(date)] INICIANDO DAILY ==="

echo "=== ACTUALIZANDO DEPENDENCIAS ==="
/home/ubuntu/backend/env/bin/pip install -r /home/ubuntu/backend/install.txt --quiet

echo "=== APLICANDO MIGRACIONES ==="
/home/ubuntu/backend/env/bin/python3 /home/ubuntu/backend/imSystem/manage.py makemigrations --noinput
/home/ubuntu/backend/env/bin/python3 /home/ubuntu/backend/imSystem/manage.py migrate --noinput

echo "=== REINICIANDO GUNICORN Y NGINX ==="
sudo systemctl daemon-reload
sudo systemctl restart nginx
sudo systemctl restart gunicorn

echo "=== STATUS ==="
sudo systemctl status gunicorn --no-pager
sudo systemctl status nginx --no-pager

echo "=== [$(date)] DAILY COMPLETADO ==="