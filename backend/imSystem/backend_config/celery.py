from celery import Celery
from backend_config import settings

app = Celery('IMS_CELERY')
app.config_from_object(settings, namespace='CELERY')
app.autodiscover_tasks()
from celery.signals import worker_init

@worker_init.connect
def worker(**kwargs):
    import django
    django.setup()

    import boto3
    from botocore.config import Config
    from ims_backend.aws_package.secrets_manager import Secrets, Secrets_API
    from ims_backend.aws_package import s3 as s3_module

    Secrets._client = boto3.client('secretsmanager', region_name='us-east-1')
    Secrets_API._client = boto3.client('secretsmanager', region_name='us-east-1')
    Secrets_API._credentials = None
    s3_module.s3_client = boto3.client(
        's3',
        region_name=Secrets._secrets["AWS_S3_REGION"],
        config=Config(signature_version='s3v4'),
    )