# s3.py
import boto3
from django.conf import settings
from botocore.config import Config

s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME, config=Config(signature_version='s3v4'))