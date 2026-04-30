#!/bin/bash

set -e

#==IF SECTION==
if [ ! -d "/home/ubuntu/backend" ]; then
    echo "ERROR: carpeta /home/ubuntu/backend no existe"
    echo "CREATING: carpeta /home/ubuntu/backend"
    mkdir backend
fi

if [ ! -d "/home/ubuntu/backend/imSystem" ]; then
    echo "ERROR: carpeta /home/ubuntu/backend/imSystem no existe"
    exit 1
fi

#==SECCION INSTALLS===
echo "===UPDATING REPOSITORIES==="
sudo apt update

echo "===SETING UP NGINX==="
if [ ! -f "/usr/sbin/nginx" ]; then
    sudo apt install nginx -y
    echo "Ingresa la IP o DNS del servidor:"
    read SERVER_IP
    sudo tee /etc/nginx/conf.d/ims.conf > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo rm -f /etc/nginx/sites-available/default
fi

sudo systemctl daemon-reload
sudo systemctl start nginx
sudo systemctl status nginx
echo "===FINISHED SETTING UP NGINX==="

echo "===INSTALLING DEPENDENCIES AND SETTING UP GUNICORN==="
sudo apt install python3-pip python3-venv git -y
cd /home/ubuntu/backend

if [ ! -d "/home/ubuntu/backend/env" ]; then
    python3 -m venv env
fi

echo "===UPDATING DEPENDENCIES==="
/home/ubuntu/backend/env/bin/pip install -r /home/ubuntu/backend/install.txt

if [ ! -f "/etc/systemd/system/gunicorn.service" ]; then
    echo "===SETTING UP GUNICORN==="
    sudo tee /etc/systemd/system/gunicorn.service > /dev/null <<EOF
[Unit]
Description=Gunicorn IMS
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/backend/imSystem
EnvironmentFile=/home/ubuntu/backend/imSystem/.mikufile
ExecStart=/home/ubuntu/backend/env/bin/gunicorn \\
    backend_config.wsgi:application \\
    --bind 127.0.0.1:8000 \\
    --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
EOF
fi

echo "===STARTING GUNICORN==="
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn
