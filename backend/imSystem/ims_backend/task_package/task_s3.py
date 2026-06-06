from celery import shared_task
from ims_backend.aws_package.s3 import s3_client
from backend_config.settings import AWS_BUCKET_NAME
@shared_task(bind=True, max_retries=None, default_retry_delay=60)
def enviar_s3(self,json, hash_hex,signature):
    try:
        s3_client.put_object(
                            Bucket=AWS_BUCKET_NAME,
                            Key=f"documentos/{hash_hex}.json",
                            Body=json.encode('utf-8'),
                            ContentType='application/json'
                        )
        s3_client.put_object(
                            Bucket=AWS_BUCKET_NAME,
                            Key=f'documentos/{hash_hex}.sig',
                            Body=signature,
                            ContentType='application/octet-stream'
                        )
    except Exception as exc:
        raise self.retry(exc=exc)