# Debe ir antes que cualquier otro import: parchea socket/ssl/threading para
# que el pool gevent sea cooperativo (boto3, firebase-admin, etc.), y luego
# parchea psycopg2 (no cubierto por monkey.patch_all, usa libpq en C) para
# que las queries de Django tampoco bloqueen el loop de gevent.
from gevent import monkey
monkey.patch_all()

from psycogreen.gevent import patch_psycopg
patch_psycopg()

import os
from celery import Celery
from celery.signals import worker_process_init

#modulo
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_config.settings')

app = Celery('IMS_CELERY')

# leer configuraciones que empiecen por "CELERY_"
app.config_from_object('django.conf:settings', namespace='CELERY')

#Tareas automatizadas
app.autodiscover_tasks()


@worker_process_init.connect
def _reinit_after_fork(**kwargs):
    # El pool prefork hace fork() del proceso master ya inicializado: las
    # conexiones a la DB y los clientes boto3 creados antes del fork quedan
    # heredados y pueden quedar colgados/corruptos en el hijo sin lanzar
    # ninguna excepcion. Se cierran/recrean aqui para que cada worker abra
    # los suyos propios.
    from django.db import connections
    connections.close_all()

    import boto3
    from botocore.config import Config
    from ims_backend.aws_package.secrets_manager import Secrets, Secrets_API
    from ims_backend.aws_package import s3 as s3_module

    Secrets._client = boto3.client('secretsmanager', region_name='us-east-1')
    Secrets_API._client = boto3.client('secretsmanager', region_name='us-east-1')
    Secrets_API._credentials = None
    s3_module.s3_client = boto3.client(
        's3', region_name=Secrets._secrets["AWS_S3_REGION"],
        config=Config(signature_version='s3v4'),
    )
