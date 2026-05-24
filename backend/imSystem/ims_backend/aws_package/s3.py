# s3.py
import boto3
from botocore.config import Config
from backend_config.settings import secrets
s3_client = boto3.client('s3', region_name=secrets["AWS_S3_REGION"], config=Config(signature_version='s3v4'))