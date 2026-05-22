import os
from celery import Celery

#modulo
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_config.settings')

app = Celery('mi_proyecto')

# leer configuraciones que empiecen por "CELERY_"
app.config_from_object('django.conf:settings', namespace='CELERY')

#Tareas automatizadas
app.autodiscover_tasks()
