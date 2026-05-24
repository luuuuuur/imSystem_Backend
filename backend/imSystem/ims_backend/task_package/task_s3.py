from celery import shared_task
from ims_backend.aws_package.s3 import s3_client
from backend_config.settings import AWS_BUCKET_NAME
@shared_task
def enviar_s3(json, hash_hex,signature):
        s3_client.put_object(
                            Bucket=AWS_BUCKET_NAME,
                            Key=f"documentos/{hash_hex}.json",
                            Body=json.encode('utf-8'),
                            ContentType='application/json'
                        )
        s3_client.put_object(
                            Bucket=AWS_BUCKET_NAME,
                            Key=f'documentos/{hash}.sig',
                            Body=signature,
                            ContentType='application/octet-stream'
                        )