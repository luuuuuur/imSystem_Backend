# s3.py
import boto3
from botocore.config import Config
from ims_backend.aws_package.secrets_manager import secrets_aws
s3_client = boto3.client('s3', region_name=secrets_aws["AWS_S3_REGION"], config=Config(signature_version='s3v4'))