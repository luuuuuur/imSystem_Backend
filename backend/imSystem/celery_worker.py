# celery_worker.py - punto de entrada para el worker
from gevent import monkey
monkey.patch_all()
from psycogreen.gevent import patch_psycopg
patch_psycopg()

from backend_config.celery import app